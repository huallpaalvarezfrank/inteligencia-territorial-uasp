"""
Fase 3 - Merge final: GeoJSON + datos electorales + censo
Une el GeoJSON de centros poblados (Fase 1) con los datos electorales (Fase 2)
por UBIGEO. Añade campos calculados y exporta el GeoJSON listo para el frontend.
Resultado: data/processed/mapa_final.geojson
"""

import os
import json
import geopandas as gpd
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

BASE       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CP_GEOJSON = os.path.join(BASE, "data", "geo", "centros_poblados_la_encanada.geojson")
ELEC_JSON  = os.path.join(BASE, "data", "processed", "electoral_centros_poblados.json")
OUT_FILE   = os.path.join(BASE, "data", "processed", "mapa_final.geojson")

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

# -- 1. Cargar GeoJSON de centros poblados (geometrias) -----------------------
print("Cargando GeoJSON de centros poblados...")
cp = gpd.read_file(CP_GEOJSON)
print(f"  Registros: {len(cp)}")
print(f"  Columnas: {list(cp.columns)}")

# -- 2. Cargar datos electorales (Fase 2) -------------------------------------
print("\nCargando datos electorales...")
elec = pd.read_json(ELEC_JSON, dtype={"ubigeo": str})
print(f"  Registros: {len(elec)}")

# -- 3. Merge por cp_id (indice unico generado en Fase 2) --------------------
print("\nUniendo por cp_id...")
cp["cp_id"] = cp.index.astype(str)
elec["cp_id"] = elec["cp_id"].astype(str)

# Columnas del electoral que no duplican las del GeoJSON
cols_elec = ["cp_id", "local_votacion", "electores_hab", "total_votantes", "mesas",
             "participacion", "partido_ganador", "pct_ganador"] + PCT_COLS

merged = cp.merge(
    elec[cols_elec],
    on="cp_id",
    how="left"
)
print(f"  Registros tras merge: {len(merged)}")
print(f"  Con datos electorales: {merged['pct_jxp'].notna().sum()} / {len(merged)}")

# -- 4. Campos calculados adicionales -----------------------------------------
print("\nCalculando campos adicionales...")

# Ausentismo
merged["ausentismo"] = (100 - merged["participacion"]).round(1)

# Margen de victoria JxP vs segundo (FP en casi todos los casos)
def margen_victoria(row):
    vals = {col: row[col] for col in PCT_COLS if pd.notna(row.get(col))}
    if len(vals) < 2:
        return None
    sorted_vals = sorted(vals.values(), reverse=True)
    return round(sorted_vals[0] - sorted_vals[1], 2)

merged["margen_victoria"] = merged.apply(margen_victoria, axis=1)

# Densidad poblacional aproximada (pob / area en km2)
merged_utm = merged.to_crs("EPSG:32717")
merged["area_km2"] = (merged_utm.geometry.area / 1e6).round(3)
merged["densidad_hab_km2"] = (merged["POBLACION"] / merged["area_km2"]).round(1)

# -- 5. Limpiar y seleccionar columnas finales --------------------------------
# Renombrar columnas del shapefile CCPP a minusculas
rename_map = {
    "UBIGEO":    "ubigeo",
    "DESCRIPCIO":"nombre",
    "CATEGORIA": "categoria",
    "POBLACION": "poblacion",
    "ALTITUD":   "altitud",
    "OBJECTID":  "objectid",
    "PROVINCIA": "provincia",
    "DISTRITO":  "distrito",
    "REGION_NAT":"region_nat",
    "LONGITUD":  "longitud_cp",
    "LATITUD":   "latitud_cp",
    "CODIGO":    "codigo",
    "CPV2017_GI":"cpv2017_gi",
    "ORIGEN":    "origen",
    "CCDD":      "ccdd",
    "CCPP":      "ccpp",
    "CCDI":      "ccdi",
    "COD_GRUPO": "cod_grupo",
    "FLAG_TIPO_":"flag_tipo",
    "descargar": "descargar",
    "contacto":  "contacto",
    "ARCHIVO":   "archivo",
    "DEPARTAMEN":"departamento",
}
merged = merged.rename(columns=rename_map)

# Columnas a incluir en el output final
cols_finales = [
    # Identificacion
    "ubigeo", "nombre", "categoria", "provincia", "distrito",
    # Geografico
    "altitud", "area_km2", "densidad_hab_km2",
    # Censal
    "poblacion",
    # Electoral - resumen
    "local_votacion", "electores_hab", "total_votantes", "mesas",
    "participacion", "ausentismo", "partido_ganador", "pct_ganador", "margen_victoria",
    # Electoral - por partido
    *PCT_COLS,
    # Geometria
    "geometry",
]
# Filtrar solo las que existen
cols_finales = [c for c in cols_finales if c in merged.columns]
final = gpd.GeoDataFrame(merged[cols_finales], crs=cp.crs)

print(f"\n  Columnas en output final: {len(cols_finales)-1} atributos + geometry")
print(f"  Resumen estadistico:")
print(f"    Poblacion total:      {final['poblacion'].sum():,.0f} hab")
print(f"    Participacion media:  {final['participacion'].mean():.1f}%")
print(f"    Ausentismo medio:     {final['ausentismo'].mean():.1f}%")
print(f"    Margen victoria med:  {final['margen_victoria'].mean():.1f}pp")
print(f"    JxP maximo:          {final['pct_jxp'].max():.1f}%")
print(f"    JxP minimo:          {final['pct_jxp'].min():.1f}%")

# -- 6. Verificar tamanio y simplificar si es necesario ----------------------
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
final.to_file(OUT_FILE, driver="GeoJSON")
size_mb = os.path.getsize(OUT_FILE) / 1e6
print(f"\nTamanio inicial: {size_mb:.2f} MB")

if size_mb > 5:
    print("Superando 5 MB, simplificando geometrias...")
    final["geometry"] = final.geometry.simplify(tolerance=0.0001, preserve_topology=True)
    final.to_file(OUT_FILE, driver="GeoJSON")
    size_mb = os.path.getsize(OUT_FILE) / 1e6
    print(f"Tamanio tras simplificacion: {size_mb:.2f} MB")

print(f"Exportado: {OUT_FILE}")
print(f"Registros: {len(final)}")
print("Fase 3 completada.")
