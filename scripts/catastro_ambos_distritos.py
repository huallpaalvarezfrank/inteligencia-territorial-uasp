"""
Catastro minero para La Encañada Y Sorochuco
Genera un solo GeoJSON combinado con campo 'distrito_id' para filtrar en el frontend.
Fuente: CATASTROMINERO/CMI_WGS84_17S.zip (GEOCATMIN - MINEM, mayo 2024)
Resultado: frontend/public/catastro_minero.geojson
"""

import os, zipfile, warnings
import geopandas as gpd
import pandas as pd
warnings.filterwarnings("ignore")

BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATASTRO_ZIP  = os.path.join(BASE, "CATASTROMINERO", "CMI_WGS84_17S.zip")
ENCANADA_ZIP  = os.path.join(BASE, "encanada.zip")
DISTRITOS_SHP = r"C:\Users\frank\Desktop\ESTRATEGIA\Actas\geo\cajamarca_rs_2026\cajamarca_rs_2026.shp"
OUT_FILE      = os.path.join(BASE, "frontend", "public", "catastro_minero.geojson")

def find_shp_in_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        shps = [n for n in z.namelist() if n.endswith(".shp")]
    return shps[0] if shps else None

def clasificar_estado(estado):
    if not isinstance(estado, str): return "otro"
    e = estado.upper()
    if "TITULADO" in e:            return "titulado"
    if "TRAMITE" in e or "TRÁMITE" in e: return "tramite"
    if "EXTING" in e:              return "extinguido"
    if "CANTERA" in e:             return "cantera"
    return "otro"

rename = {
    "CODIGOU":    "codigo",       "FEC_DENU":   "fecha_denuncia",
    "CONCESION":  "concesion",    "TIT_CONCES": "titular",
    "D_ESTADO":   "estado",       "CARTA":      "carta",
    "ZONA":       "zona_utm",     "LEYENDA":    "leyenda",
    "SUSTANCIA":  "sustancia",    "DEPA":       "departamento",
    "PROVI":      "provincia",    "DISTRI":     "distrito_catastro",
    "HASDATUM":   "has_datum",
}

# ── 1. Cargar límites distritales ─────────────────────────────────────────────
print("Cargando limites distritales...")
shp_enc = find_shp_in_zip(ENCANADA_ZIP)
enc_gdf = gpd.read_file(f"zip://{ENCANADA_ZIP}!{shp_enc}").to_crs("EPSG:4326")
limite_enc = enc_gdf.union_all()

distritos = gpd.read_file(DISTRITOS_SHP)
soro_row  = distritos[distritos["distrito"].str.upper().str.contains("SOROCHUCO")]
limite_soro = soro_row.geometry.union_all()
soro_gdf  = gpd.GeoDataFrame(geometry=[limite_soro], crs=distritos.crs)

print(f"  Encañada OK  | Sorochuco OK")

# ── 2. Cargar catastro (una sola lectura, recortar a bbox combinado) ──────────
print("Cargando catastro minero Zona 17S...")
shp_cat = find_shp_in_zip(CATASTRO_ZIP)
catastro_raw = gpd.read_file(f"zip://{CATASTRO_ZIP}!{shp_cat}")
print(f"  Total concesiones 17S: {len(catastro_raw):,}")

catastro_raw = catastro_raw.to_crs("EPSG:4326")

# Pre-filtrar por bounding box unido de ambos distritos
import shapely.ops
bbox_union = limite_enc.union(limite_soro).bounds
catastro_bbox = catastro_raw.cx[bbox_union[0]:bbox_union[2], bbox_union[1]:bbox_union[3]]
print(f"  En bbox combinado: {len(catastro_bbox):,}")

# ── 3. Clip por cada distrito ─────────────────────────────────────────────────
resultados = []

for distrito_id, limite, limite_gdf_obj in [
    ("encanada",  limite_enc,  enc_gdf),
    ("sorochuco", limite_soro, soro_gdf),
]:
    print(f"\nProcesando {distrito_id}...")
    clipped = gpd.clip(catastro_bbox, limite_gdf_obj)
    clipped = clipped[~clipped.geometry.is_empty].reset_index(drop=True)
    print(f"  Concesiones: {len(clipped)}")

    # Renombrar
    clipped = clipped.rename(columns={k: v for k, v in rename.items() if k in clipped.columns})

    # Campos calculados
    if "sustancia" in clipped.columns:
        clipped["sustancia_txt"] = clipped["sustancia"].map(
            {"M": "Metalica", "N": "No metalica"}
        ).fillna("Otra")

    clipped["estado_cat"]  = clipped["estado"].apply(clasificar_estado) if "estado" in clipped.columns else "otro"
    clipped["distrito_id"] = distrito_id

    print(f"  Estados: {clipped['estado_cat'].value_counts().to_dict()}")
    resultados.append(clipped)

# ── 4. Combinar y exportar ────────────────────────────────────────────────────
print("\nCombinando y exportando...")
combined = gpd.GeoDataFrame(pd.concat(resultados, ignore_index=True), crs="EPSG:4326")
print(f"  Total concesiones (ambos distritos): {len(combined)}")
print(f"  Encañada:  {(combined['distrito_id']=='encanada').sum()}")
print(f"  Sorochuco: {(combined['distrito_id']=='sorochuco').sum()}")

os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
combined.to_file(OUT_FILE, driver="GeoJSON")
print(f"\nExportado: {OUT_FILE}")
print(f"Tamanio: {os.path.getsize(OUT_FILE)/1e3:.1f} KB")
print("Catastro ambos distritos completado.")
