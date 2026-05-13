"""
Fase 2 - Datos electorales 2026 por centro poblado
Fuente: encanada_centros_2026 shapefile (12 IEs con porcentajes por partido)
Estrategia: asignar a cada centro poblado los datos del local de votacion mas cercano
Resultado: data/processed/electoral_centros_poblados.json
"""

import os
import sqlite3
import geopandas as gpd
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CENTROS_SHP = os.path.join(BASE, "encanada_centros_2026", "encanada_centros_2026.shp")
CP_GEOJSON  = os.path.join(BASE, "data", "geo", "centros_poblados_la_encanada.geojson")
DB_PATH     = r"C:\Users\frank\Desktop\ESTRATEGIA\Actas\onpe_resultados.db"
OUT_FILE    = os.path.join(BASE, "data", "processed", "electoral_centros_poblados.json")

# Mapeo codigo → nombre de partido
PARTIDOS = {
    "pct_an":    "Ahora Nacion",
    "pct_app":   "Alianza Para el Progreso",
    "pct_fp":    "Fuerza Popular",
    "pct_jxp":   "Juntos por el Peru",
    "pct_lp":    "Libertad Popular",
    "pct_obra":  "Partido Civico Obras",
    "pct_pbg":   "Peru Bienestar Grande",
    "pct_pl":    "Partido Libertario",
    "pct_pp":    "Podemos Peru",
    "pct_ppt":   "Partido Patriotico del Peru",
    "pct_rp":    "Renovacion Popular",
    "pct_sp":    "Somos Peru",
    "pct_otros": "Otros",
}
PCT_COLS = list(PARTIDOS.keys())

# -- 1. Cargar locales de votacion (IEs) con porcentajes ----------------------
print("Cargando centros de votacion 2026...")
ies = gpd.read_file(CENTROS_SHP)
print(f"  IEs cargadas: {len(ies)}")
print(f"  Columnas: {list(ies.columns)}")

# -- 2. Enriquecer con electores habiles desde SQLite -------------------------
print("\nConsultando electores habiles por local desde SQLite...")
con = sqlite3.connect(DB_PATH)
query = """
    SELECT local_votacion,
           SUM(electores_hab) / COUNT(DISTINCT candidato) AS electores_hab,
           SUM(total_votantes) / COUNT(DISTINCT candidato) AS total_votantes,
           COUNT(DISTINCT num_mesa) AS num_mesas
    FROM resultados_2026
    WHERE (distrito LIKE '%ENCA%') AND tipo_eleccion = 'PRESIDENCIAL'
    GROUP BY local_votacion
"""
df_elec = pd.read_sql_query(query, con)
con.close()
print(f"  Locales encontrados en SQLite: {len(df_elec)}")
print(df_elec[["local_votacion", "electores_hab", "total_votantes"]].to_string())

# Merge con el shapefile por nombre del local (normalizar para el join)
ies["local_key"] = ies["local_vot"].str.strip().str.upper()
df_elec["local_key"] = df_elec["local_votacion"].str.strip().str.upper()
ies = ies.merge(df_elec[["local_key", "electores_hab", "total_votantes", "num_mesas"]],
                on="local_key", how="left")

# Calcular participacion (%) por IE
ies["participacion"] = (ies["total_votantes"] / ies["electores_hab"] * 100).round(1)
print(f"\n  IEs con datos de participacion: {ies['participacion'].notna().sum()} / {len(ies)}")

# -- 3. Cargar centros poblados (poligonos Voronoi de Fase 1) -----------------
print("\nCargando centros poblados (GeoJSON Fase 1)...")
cp = gpd.read_file(CP_GEOJSON)
print(f"  Centros poblados: {len(cp)}")

# Añadir ID unico por fila para poder hacer merge posterior
cp["cp_id"] = cp.index.astype(str)

# Usar centroides de cada poligono para el join de proximidad
cp_pts = cp.copy()
cp_pts["geometry"] = cp.geometry.centroid

# -- 4. Spatial join por proximidad: cada CP hereda datos del IE mas cercano --
print("\nAsignando datos electorales por proximidad...")

# sjoin_nearest requiere mismo CRS
if ies.crs != cp_pts.crs:
    ies = ies.to_crs(cp_pts.crs)

# Proyectar a UTM zona 17S (EPSG:32717) para calcular distancias en metros
cp_utm  = cp_pts.to_crs("EPSG:32717")
ies_utm = ies.to_crs("EPSG:32717")

joined = gpd.sjoin_nearest(
    cp_utm[["cp_id", "UBIGEO", "DESCRIPCIO", "CATEGORIA", "POBLACION", "ALTITUD", "geometry"]],
    ies_utm[["local_vot", "total_vot", "mesas", "participacion", "electores_hab",
              "total_votantes"] + PCT_COLS + ["geometry"]],
    how="left",
    distance_col="dist_m"
)
joined = joined.reset_index(drop=True)

print(f"  Join completado: {len(joined)} filas")
print(f"  Distancia maxima a IE mas cercana: {joined['dist_m'].max():.0f} m")
print(f"  Distancia promedio: {joined['dist_m'].mean():.0f} m")

# -- 5. Calcular partido ganador por centro poblado ---------------------------
print("\nCalculando partido ganador por centro poblado...")

def partido_ganador(row):
    vals = {col: row[col] for col in PCT_COLS if pd.notna(row[col])}
    if not vals:
        return None, None
    ganador_col = max(vals, key=vals.get)
    return PARTIDOS[ganador_col], round(vals[ganador_col], 2)

joined[["partido_ganador", "pct_ganador"]] = joined.apply(
    lambda r: pd.Series(partido_ganador(r)), axis=1
)

print(f"  Distribucion de partido ganador:")
print(joined["partido_ganador"].value_counts().to_string())

# -- 6. Preparar output JSON --------------------------------------------------
cols_out = (
    ["cp_id", "UBIGEO", "DESCRIPCIO", "CATEGORIA", "POBLACION", "ALTITUD",
     "local_vot", "electores_hab", "total_votantes", "mesas",
     "participacion", "partido_ganador", "pct_ganador"]
    + PCT_COLS
)
# Renombrar para claridad
resultado = joined[cols_out].copy()
resultado = resultado.rename(columns={
    "UBIGEO":       "ubigeo",
    "DESCRIPCIO":   "nombre",
    "CATEGORIA":    "categoria",
    "POBLACION":    "poblacion",
    "ALTITUD":      "altitud",
    "local_vot":    "local_votacion",
    "electores_hab":"electores_hab",
    "total_votantes":"total_votantes",
    "mesas":        "mesas",
})

# Redondear porcentajes
for col in PCT_COLS:
    resultado[col] = resultado[col].round(2)

os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
resultado.to_json(OUT_FILE, orient="records", indent=2, force_ascii=False)

size_kb = os.path.getsize(OUT_FILE) / 1e3
print(f"\nExportado: {OUT_FILE}")
print(f"Tamanio: {size_kb:.1f} KB")
print(f"Registros: {len(resultado)}")
print("Fase 2 completada.")
