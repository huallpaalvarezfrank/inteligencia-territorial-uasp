"""
Extracción del catastro minero para La Encañada
Fuente: CATASTROMINERO/CMI_WGS84_17S.zip (GEOCATMIN - MINEM, mayo 2024)
Resultado: data/geo/catastro_minero_encanada.geojson
"""

import os
import zipfile
import geopandas as gpd
import warnings
warnings.filterwarnings("ignore")

BASE         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATASTRO_ZIP = os.path.join(BASE, "CATASTROMINERO", "CMI_WGS84_17S.zip")
DISTRITO_ZIP = os.path.join(BASE, "encanada.zip")
OUT_FILE     = os.path.join(BASE, "data", "geo", "catastro_minero_encanada.geojson")
FRONTEND_OUT = os.path.join(BASE, "frontend", "public", "catastro_minero_encanada.geojson")


def find_shp_in_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        shps = [n for n in z.namelist() if n.endswith(".shp")]
    if not shps:
        raise FileNotFoundError(f"No .shp en {zip_path}")
    return shps[0]


# -- 1. Cargar limite distrital -----------------------------------------------
print("Cargando limite distrital...")
shp_dist = find_shp_in_zip(DISTRITO_ZIP)
distrito = gpd.read_file(f"zip://{DISTRITO_ZIP}!{shp_dist}")
distrito_4326 = distrito.to_crs("EPSG:4326")
limite = distrito_4326.union_all()

# -- 2. Cargar catastro minero Zona 17S ---------------------------------------
print("Cargando catastro minero Zona 17S (puede tardar)...")
shp_cat = find_shp_in_zip(CATASTRO_ZIP)
catastro = gpd.read_file(f"zip://{CATASTRO_ZIP}!{shp_cat}")
print(f"  Total concesiones 17S: {len(catastro):,}")
print(f"  CRS original: {catastro.crs}")

# -- 3. Reproyectar a WGS84 ---------------------------------------------------
print("Reproyectando a EPSG:4326...")
catastro = catastro.to_crs("EPSG:4326")

# -- 4. Filtro previo por bounding box (rápido) para recortar carga -----------
bbox = limite.bounds
catastro = catastro.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
print(f"  Concesiones en bounding box de La Encañada: {len(catastro):,}")

# -- 5. Clip espacial al limite del distrito ----------------------------------
print("Recortando al limite distrital...")
catastro_enc = gpd.clip(catastro, distrito_4326)
catastro_enc = catastro_enc[~catastro_enc.geometry.is_empty].reset_index(drop=True)
print(f"  Concesiones dentro de La Encañada: {len(catastro_enc)}")

# -- 6. Limpiar y preparar campos ---------------------------------------------
print("\nCampos disponibles:", list(catastro_enc.columns))

# Renombrar para claridad en el frontend
rename = {
    "CODIGOU":   "codigo",
    "FEC_DENU":  "fecha_denuncia",
    "CONCESION": "concesion",
    "TIT_CONCES":"titular",
    "D_ESTADO":  "estado",
    "CARTA":     "carta",
    "ZONA":      "zona_utm",
    "LEYENDA":   "leyenda",
    "SUSTANCIA": "sustancia",
    "DEPA":      "departamento",
    "PROVI":     "provincia",
    "DISTRI":    "distrito_catastro",
    "HASDATUM":  "has_datum",
}
catastro_enc = catastro_enc.rename(columns={k: v for k, v in rename.items() if k in catastro_enc.columns})

# Normalizar SUSTANCIA a texto legible
if "sustancia" in catastro_enc.columns:
    catastro_enc["sustancia_txt"] = catastro_enc["sustancia"].map(
        {"M": "Metalica", "N": "No metalica"}
    ).fillna("Otra")

# Categorizar estado para colores en el frontend
def clasificar_estado(estado):
    if not isinstance(estado, str):
        return "otro"
    e = estado.upper()
    if "TITULADO" in e:
        return "titulado"
    if "TRAMITE" in e or "TRÁMITE" in e:
        return "tramite"
    if "EXTING" in e or "EXTINGUID" in e:
        return "extinguido"
    if "CANTERA" in e:
        return "cantera"
    return "otro"

catastro_enc["estado_cat"] = catastro_enc["estado"].apply(clasificar_estado)

print("\n  Estados:")
print(catastro_enc["estado_cat"].value_counts().to_string())
print("\n  Sustancia:")
print(catastro_enc["sustancia_txt"].value_counts().to_string())

# -- 7. Exportar --------------------------------------------------------------
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
catastro_enc.to_file(OUT_FILE, driver="GeoJSON")
catastro_enc.to_file(FRONTEND_OUT, driver="GeoJSON")

size_kb = os.path.getsize(OUT_FILE) / 1e3
print(f"\nExportado: {OUT_FILE}")
print(f"Tamanio: {size_kb:.1f} KB")
print("Catastro minero exportado correctamente.")
