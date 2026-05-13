"""
Pipeline Sorochuco — fases 1+2+3 en un solo script
Genera: frontend/public/mapa_final_sorochuco.geojson
Estrategia:
  · Limite distrital → cajamarca_rs_2026.shp (filtrar SOROCHUCO)
  · CPs (80 puntos) → Voronoi recortado al distrito
  · Datos electorales → onpe_resultados.db (tabla resultados_2026)
  · IE geocoding → fuzzy match entre nombre IE y nombre CP
  · sjoin_nearest → cada CP hereda datos del IE mas cercano
"""

import os, sqlite3, warnings
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.ops import voronoi_diagram
from shapely.geometry import MultiPoint, Point
from difflib import SequenceMatcher
import zipfile
warnings.filterwarnings("ignore")

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CP_ZIP        = r"C:\Users\frank\Desktop\ESTRATEGIA\CP_CAJAMARCA.zip"
DISTRITOS_SHP = r"C:\Users\frank\Desktop\ESTRATEGIA\Actas\geo\cajamarca_rs_2026\cajamarca_rs_2026.shp"
DB_PATH       = r"C:\Users\frank\Desktop\ESTRATEGIA\Actas\onpe_resultados.db"
OUT_FILE      = os.path.join(BASE, "frontend", "public", "mapa_final_sorochuco.geojson")

UBIGEO = "060309"
PARTIDOS = {
    "pct_an":   "Ahora Nacion",        "pct_app": "Alianza Para el Progreso",
    "pct_fp":   "Fuerza Popular",      "pct_jxp": "Juntos por el Peru",
    "pct_lp":   "Libertad Popular",    "pct_obra": "Partido Civico Obras",
    "pct_pbg":  "Peru Bienestar Grande","pct_pl":  "Partido Libertario",
    "pct_pp":   "Podemos Peru",        "pct_ppt": "Partido Patriotico del Peru",
    "pct_rp":   "Renovacion Popular",  "pct_sp":  "Somos Peru",
    "pct_otros":"Otros",
}
PCT_COLS = list(PARTIDOS.keys())

# Mapeo por substring: el candidato en la BD trae nombre completo + partido
# Ej: "JUNTOS POR EL PERÚ — ROBERTO HELBERT SANCHEZ PALOMINO"
CANDIDATO_PATTERNS = [
    ("JUNTOS POR EL PER",         "pct_jxp"),
    ("FUERZA POPULAR",            "pct_fp"),
    ("OBRAS",                     "pct_obra"),   # PARTIDO CÍVICO OBRAS
    ("ALIANZA PARA EL PROGRESO",  "pct_app"),
    ("PODEMOS PER",               "pct_pp"),
    ("RENOVACI",                  "pct_rp"),     # RENOVACIÓN POPULAR
    ("AHORA NACI",                "pct_an"),     # AHORA NACIÓN
    ("LIBERTAD POPULAR",          "pct_lp"),
    ("BUEN GOBIERNO",             "pct_pbg"),    # PARTIDO DEL BUEN GOBIERNO ~ Bienestar
    ("PARTIDO LIBERTARIO",        "pct_pl"),
    ("PATRI",                     "pct_ppt"),    # PARTIDO PATRIÓTICO DEL PERÚ
    ("SOMOS PER",                 "pct_sp"),     # PARTIDO DEMOCRÁTICO SOMOS PERÚ
]

def get_pct_key(candidato):
    """Mapea nombre completo de candidato a clave de partido por substring."""
    c = candidato.upper()
    for pattern, key in CANDIDATO_PATTERNS:
        if pattern.upper() in c:
            return key
    return None  # irá a pct_otros


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 1 — GEOGRAFÍA: centros poblados + Voronoi
# ═══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("FASE 1 — GEOGRAFÍA")
print("=" * 60)

# 1a. Limite distrital Sorochuco
print("Cargando limite distrital Sorochuco...")
distritos = gpd.read_file(DISTRITOS_SHP)
sorochuco_row = distritos[distritos["distrito"].str.upper().str.contains("SOROCHUCO")]
print(f"  Filas encontradas: {len(sorochuco_row)}")
if len(sorochuco_row) == 0:
    raise ValueError("No se encontro SOROCHUCO en cajamarca_rs_2026.shp")
limite = sorochuco_row.geometry.union_all()
limite_gdf = gpd.GeoDataFrame(geometry=[limite], crs=distritos.crs)
print(f"  Area distrito: {limite.area:.6f} grados2")

# 1b. Cargar CPs Sorochuco
print("\nCargando centros poblados Sorochuco...")
def find_shp_in_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        shps = [n for n in z.namelist() if n.endswith(".shp")]
    return shps[0] if shps else None

shp_name = find_shp_in_zip(CP_ZIP)
cp_all = gpd.read_file(f"zip://{CP_ZIP}!{shp_name}")
cp = cp_all[cp_all["UBIGEO"].astype(str).str.startswith(UBIGEO)].copy()
cp = cp.reset_index(drop=True)
if cp.crs != limite_gdf.crs:
    cp = cp.to_crs(limite_gdf.crs)
print(f"  CPs Sorochuco: {len(cp)}")
print(f"  Categorias: {cp['CATEGORIA'].value_counts().to_dict()}")
print(f"  Poblacion total: {cp['POBLACION'].sum():,.0f} hab")

# 1c. Generar Voronoi
print("\nGenerando Voronoi...")
puntos = cp.geometry.values.tolist()
multi  = MultiPoint(puntos)
envelope = limite.buffer(0.05)
regions  = voronoi_diagram(multi, envelope=envelope)
voronoi_polys = list(regions.geoms)
print(f"  Regiones Voronoi: {len(voronoi_polys)}")

# Asignar cada region al CP mas cercano (por centroide de la region)
print("Asignando regiones a centros poblados...")
rows = []
for vp in voronoi_polys:
    idx = cp.geometry.distance(vp.centroid).idxmin()
    row = cp.loc[idx].to_dict()
    row["geometry"] = vp
    rows.append(row)

voronoi_gdf = gpd.GeoDataFrame(rows, crs=cp.crs)

# Recortar al limite
print("Recortando Voronoi al limite distrital...")
cp_voronoi = gpd.clip(voronoi_gdf, limite_gdf)
cp_voronoi = cp_voronoi.reset_index(drop=True)
print(f"  Poligonos tras clip: {len(cp_voronoi)}")

union_res = cp_voronoi.union_all()
cobertura = union_res.area / limite.area
print(f"  Cobertura: {cobertura:.2%}")


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2 — ELECTORAL: porcentajes por IE desde SQLite
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("FASE 2 — DATOS ELECTORALES")
print("=" * 60)

con = sqlite3.connect(DB_PATH)

# Votos por candidato y local
q_votos = """
    SELECT local_votacion, candidato,
           SUM(votos)         AS votos_total,
           MAX(votos_validos) AS votos_validos
    FROM resultados_2026
    WHERE distrito LIKE '%SOROCHUCO%'
      AND tipo_eleccion = 'PRESIDENCIAL'
    GROUP BY local_votacion, candidato
"""
df_votos = pd.read_sql_query(q_votos, con)

# Electores y participacion por IE
q_part = """
    SELECT local_votacion,
           SUM(electores_hab)  / COUNT(DISTINCT candidato) AS electores_hab,
           SUM(total_votantes) / COUNT(DISTINCT candidato) AS total_votantes,
           COUNT(DISTINCT num_mesa)                         AS mesas
    FROM resultados_2026
    WHERE distrito LIKE '%SOROCHUCO%'
      AND tipo_eleccion = 'PRESIDENCIAL'
    GROUP BY local_votacion
"""
df_part = pd.read_sql_query(q_part, con)
con.close()

print(f"  IEs encontradas: {df_part['local_votacion'].nunique()}")
print(df_part[["local_votacion", "electores_hab", "total_votantes", "mesas"]].to_string())

# Calcular total de votos validos por IE para los pcts
ie_total = df_votos.groupby("local_votacion")["votos_total"].sum().reset_index()
ie_total.columns = ["local_votacion", "votos_ie_total"]
df_votos = df_votos.merge(ie_total, on="local_votacion")
df_votos["pct"] = (df_votos["votos_total"] / df_votos["votos_ie_total"] * 100).round(2)
df_votos["pct_key"] = df_votos["candidato"].apply(get_pct_key)

# Pivotar: una fila por IE, columnas = pct_xxx
pivot = (
    df_votos[df_votos["pct_key"].notna()]
    .pivot_table(index="local_votacion", columns="pct_key", values="pct", aggfunc="sum")
    .reset_index()
)

# pct_otros = votos de partidos no mapeados + redondeo
pct_otros_por_ie = (
    df_votos[df_votos["pct_key"].isna()]
    .groupby("local_votacion")["pct"].sum()
)
pivot["pct_otros"] = pivot["local_votacion"].map(pct_otros_por_ie).fillna(0.0).round(2)

# Asegurar todas las columnas PCT_COLS
for col in PCT_COLS:
    if col not in pivot.columns:
        pivot[col] = 0.0

# Merge con participacion
ies = pivot.merge(df_part, on="local_votacion")
ies["electores_hab"]  = ies["electores_hab"].round(0).astype(int)
ies["total_votantes"] = ies["total_votantes"].round(0).astype(int)
ies["participacion"]  = (ies["total_votantes"] / ies["electores_hab"] * 100).round(1)
print(f"\n  IEs con datos electorales: {len(ies)}")


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2b — GEOCODIFICAR IEs por fuzzy matching con nombres de CPs
# ═══════════════════════════════════════════════════════════════════════════════

print("\nGeocodificando IEs por nombre...")

cp_names    = cp_voronoi["DESCRIPCIO"].fillna("").tolist()
cp_centroids = [geom.centroid for geom in cp_voronoi.geometry]
district_centroid = limite.centroid

def clean_name(s):
    """Normalizar nombre para comparacion fuzzy."""
    s = s.upper()
    for token in ["I.E.", "I.E", "IE ", "IE.", "INSTITUCION EDUCATIVA",
                  "NO.", "N°", "N°.", "NRO.", "#", "-"]:
        s = s.replace(token, " ")
    return " ".join(s.split())

ie_points = []
for ie_name in ies["local_votacion"]:
    clean_ie = clean_name(ie_name)
    best_score, best_pt = 0.0, district_centroid
    best_cp  = "(sin match)"

    for cp_name, cp_pt in zip(cp_names, cp_centroids):
        score = SequenceMatcher(None, clean_ie, cp_name.upper().strip()).ratio()
        if score > best_score:
            best_score, best_pt, best_cp = score, cp_pt, cp_name

    if best_score < 0.25:
        best_pt = district_centroid
        best_cp = "(fallback centroide)"

    print(f"  '{ie_name}' -> '{best_cp}' (score={best_score:.2f})")
    ie_points.append(best_pt)

ies["geometry"] = [Point(pt.x, pt.y) for pt in ie_points]
ies_gdf = gpd.GeoDataFrame(ies, geometry="geometry", crs="EPSG:4326")


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 3 — MERGE: asignar IE a cada CP, calcular campos, exportar
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("FASE 3 — MERGE")
print("=" * 60)

# Usar centroides de Voronoi para asignacion de IE
cp_centroids_gdf = cp_voronoi.copy()
cp_centroids_gdf["geometry"] = cp_voronoi.geometry.centroid

# Proyectar a UTM 17S para calcular distancias en metros
cp_utm  = cp_centroids_gdf.to_crs("EPSG:32717")
ies_utm = ies_gdf.to_crs("EPSG:32717")

ie_cols = ["local_votacion", "electores_hab", "total_votantes", "mesas",
           "participacion"] + PCT_COLS + ["geometry"]

joined = gpd.sjoin_nearest(
    cp_utm[["UBIGEO","DESCRIPCIO","CATEGORIA","POBLACION","ALTITUD",
            "PROVINCIA","DISTRITO","REGION_NAT","LONGITUD","LATITUD","CODIGO","geometry"]],
    ies_utm[ie_cols],
    how="left",
    distance_col="dist_m"
)
# sjoin_nearest puede devolver duplicados por empate de distancia → conservar solo el primero
joined = joined[~joined.index.duplicated(keep="first")]
print(f"  Join completado: {len(joined)} filas")
print(f"  Dist. max a IE mas cercana: {joined['dist_m'].max()/1000:.1f} km")
print(f"  Dist. media: {joined['dist_m'].mean()/1000:.1f} km")

# Restaurar geometrias Voronoi originales (alinear por posición, no por índice)
joined = joined.reset_index(drop=True)
joined["geometry"] = cp_voronoi.geometry.values
joined = gpd.GeoDataFrame(joined, geometry="geometry", crs="EPSG:4326")

# Calculos adicionales
print("Calculando campos adicionales...")
joined["ausentismo"] = (100 - joined["participacion"]).round(1)

joined_utm = joined.to_crs("EPSG:32717")
joined["area_km2"] = (joined_utm.geometry.area / 1e6).round(3)
joined["densidad_hab_km2"] = (
    joined["POBLACION"] / joined["area_km2"].replace(0, np.nan)
).round(1)

def partido_ganador(row):
    vals = {c: row[c] for c in PCT_COLS if pd.notna(row.get(c)) and row.get(c, 0) > 0}
    if not vals:
        return None, None
    g = max(vals, key=vals.get)
    return PARTIDOS[g], round(vals[g], 2)

joined[["partido_ganador", "pct_ganador"]] = joined.apply(
    lambda r: pd.Series(partido_ganador(r)), axis=1
)

def margen_victoria(row):
    vals = sorted(
        [row[c] for c in PCT_COLS if pd.notna(row.get(c)) and row.get(c, 0) > 0],
        reverse=True
    )
    return round(vals[0] - vals[1], 2) if len(vals) >= 2 else None

joined["margen_victoria"] = joined.apply(margen_victoria, axis=1)

# Renombrar columnas
rename_map = {
    "UBIGEO":    "ubigeo",    "DESCRIPCIO": "nombre",   "CATEGORIA":  "categoria",
    "POBLACION": "poblacion", "ALTITUD":    "altitud",   "PROVINCIA":  "provincia",
    "DISTRITO":  "distrito",  "REGION_NAT": "region_nat","LONGITUD":   "longitud_cp",
    "LATITUD":   "latitud_cp","CODIGO":     "codigo",
}
joined = joined.rename(columns=rename_map)

# Columnas finales
cols_finales = [
    "ubigeo", "nombre", "categoria", "provincia", "distrito",
    "altitud", "area_km2", "densidad_hab_km2", "poblacion",
    "local_votacion", "electores_hab", "total_votantes", "mesas",
    "participacion", "ausentismo", "partido_ganador", "pct_ganador", "margen_victoria",
    *PCT_COLS,
    "geometry",
]
cols_finales = [c for c in cols_finales if c in joined.columns]
final = gpd.GeoDataFrame(joined[cols_finales], crs="EPSG:4326")

print(f"\n  Columnas: {len(cols_finales)-1} atributos + geometry")
print(f"  Poblacion total:      {final['poblacion'].sum():,.0f} hab")
print(f"  Participacion media:  {final['participacion'].mean():.1f}%")
print(f"  JxP max/min:         {final['pct_jxp'].max():.1f}% / {final['pct_jxp'].min():.1f}%")
print(f"  Partido ganador:")
print(final["partido_ganador"].value_counts().to_string())

# Exportar
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
final.to_file(OUT_FILE, driver="GeoJSON")
size_mb = os.path.getsize(OUT_FILE) / 1e6
print(f"\nTamanio: {size_mb:.2f} MB")

if size_mb > 5:
    print("Simplificando geometrias (>5 MB)...")
    final["geometry"] = final.geometry.simplify(0.0001, preserve_topology=True)
    final.to_file(OUT_FILE, driver="GeoJSON")
    print(f"Tamanio tras simplificacion: {os.path.getsize(OUT_FILE)/1e6:.2f} MB")

print(f"\nExportado: {OUT_FILE}")
print(f"Registros: {len(final)}")
print("Pipeline Sorochuco completado.")
