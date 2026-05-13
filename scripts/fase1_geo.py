"""
Fase 1 - Preparacion geografica: Centros poblados de La Encañada
Estrategia Opcion A: CCPP (puntos) + Voronoi recortado al limite distrital
Resultado: data/geo/centros_poblados_la_encanada.geojson (110 poligonos, 100% cobertura)
"""

import os
import zipfile
import geopandas as gpd
import pandas as pd
from shapely.ops import voronoi_diagram
from shapely.geometry import MultiPoint
import warnings
warnings.filterwarnings("ignore")

BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCPP_ZIP    = r"C:\Users\frank\Desktop\ESTRATEGIA\CP_CAJAMARCA.zip"
DISTRITO_ZIP = os.path.join(BASE, "encanada.zip")
OUT_FILE    = os.path.join(BASE, "data", "geo", "centros_poblados_la_encanada.geojson")
UBIGEO_ENCANADA = "060105"


def find_shp_in_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        shps = [n for n in z.namelist() if n.endswith(".shp")]
    if not shps:
        raise FileNotFoundError(f"No .shp en {zip_path}")
    return shps[0]


# -- 1. Cargar limite distrital ------------------------------------------------
print("Cargando limite distrital...")
shp_dist = find_shp_in_zip(DISTRITO_ZIP)
distrito = gpd.read_file(f"zip://{DISTRITO_ZIP}!{shp_dist}")
limite   = distrito.union_all()
print(f"  Distrito cargado: {distrito['distrito'].values}")

# -- 2. Cargar centros poblados, filtrar La Encañada --------------------------
print("\nCargando centros poblados...")
shp_ccpp = find_shp_in_zip(CCPP_ZIP)
ccpp_all = gpd.read_file(f"zip://{CCPP_ZIP}!{shp_ccpp}")
ccpp = ccpp_all[ccpp_all["UBIGEO"].astype(str).str.startswith(UBIGEO_ENCANADA)].copy()
ccpp = ccpp.reset_index(drop=True)
print(f"  Centros poblados en La Encañada: {len(ccpp)}")
print(f"  Categorias: {ccpp['CATEGORIA'].value_counts().to_dict()}")
print(f"  Poblacion total: {ccpp['POBLACION'].sum():,.0f} hab")

# Asegurar mismo CRS
if ccpp.crs != distrito.crs:
    ccpp = ccpp.to_crs(distrito.crs)

# Verificar que todos los puntos caen dentro del limite (algunos pueden estar fuera)
dentro = ccpp[ccpp.within(limite.buffer(0.01))]
print(f"  Puntos dentro del distrito: {len(dentro)} / {len(ccpp)}")

# -- 3. Generar Voronoi -------------------------------------------------------
print("\nGenerando poligonos Voronoi...")
puntos = ccpp.geometry.values.tolist()
multi  = MultiPoint(puntos)

# voronoi_diagram usa el bounding box del envelope; ampliar para no perder bordes
envelope = limite.buffer(0.05)
regions  = voronoi_diagram(multi, envelope=envelope)
voronoi_polys = list(regions.geoms)
print(f"  Regiones Voronoi generadas: {len(voronoi_polys)}")

# -- 4. Asignar cada region Voronoi a su centro poblado mas cercano -----------
print("Asignando regiones a centros poblados...")
rows = []
for vp in voronoi_polys:
    # El punto generador de cada celda Voronoi esta dentro de ella
    idx = ccpp.geometry.distance(vp.centroid).idxmin()
    row = ccpp.loc[idx].to_dict()
    row["geometry"] = vp
    rows.append(row)

voronoi_gdf = gpd.GeoDataFrame(rows, crs=ccpp.crs)

# -- 5. Recortar al limite distrital ------------------------------------------
print("Recortando Voronoi al limite distrital...")
resultado = gpd.clip(voronoi_gdf, distrito)
resultado = resultado.reset_index(drop=True)

# -- 6. Verificacion ----------------------------------------------------------
print("\n--- Verificacion ---")
print(f"  Poligonos finales: {len(resultado)}")
print(f"  Tipos geometria: {resultado.geom_type.value_counts().to_dict()}")

union_res  = resultado.union_all()
cobertura  = union_res.area / limite.area
huecos     = limite.difference(union_res)
print(f"  Cobertura del distrito: {cobertura:.2%}")

if huecos.is_empty or huecos.area < 1e-10:
    print("  Sin huecos detectados OK")
else:
    print(f"  ADVERTENCIA huecos: area = {huecos.area:.8f} grados2")

# Verificar superposiciones (interseccion entre vecinos no debe ser area significativa)
overlaps = 0
geoms = resultado.geometry.values
for i in range(len(geoms)):
    for j in range(i+1, len(geoms)):
        inter = geoms[i].intersection(geoms[j])
        if inter.area > 1e-10:
            overlaps += 1
print(f"  Superposiciones detectadas: {overlaps}")

# -- 7. Exportar --------------------------------------------------------------
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
resultado.to_file(OUT_FILE, driver="GeoJSON")

size_mb = os.path.getsize(OUT_FILE) / 1e6
print(f"\nExportado: {OUT_FILE}")
print(f"Tamaño: {size_mb:.2f} MB")
print("Fase 1 completada.")
