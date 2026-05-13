"""
Exportar capas para QGIS
Genera la carpeta qgis_export/ con shapefiles listos para editar en QGIS.

Capas exportadas:
  1. manzanas_encanada.shp    — 110 CPs Encañada (Voronoi + datos electorales)
  2. manzanas_sorochuco.shp   — 80 CPs Sorochuco (Voronoi + datos electorales)
  3. distritos.shp            — Limites distritales (Encañada + Sorochuco)
  4. catastro_minero.shp      — Concesiones mineras en Encañada
  5. centros_poblados_pts.shp — Puntos originales de CPs (sin Voronoi)
"""

import os, zipfile, warnings
import geopandas as gpd
import pandas as pd
warnings.filterwarnings("ignore")

BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR       = os.path.join(BASE, "qgis_export")
CP_ZIP        = r"C:\Users\frank\Desktop\ESTRATEGIA\CP_CAJAMARCA.zip"
DISTRITOS_SHP = r"C:\Users\frank\Desktop\ESTRATEGIA\Actas\geo\cajamarca_rs_2026\cajamarca_rs_2026.shp"

GEOJSONS = {
    "manzanas_encanada":  os.path.join(BASE, "frontend", "public", "mapa_final.geojson"),
    "manzanas_sorochuco": os.path.join(BASE, "frontend", "public", "mapa_final_sorochuco.geojson"),
    "catastro_minero":    os.path.join(BASE, "frontend", "public", "catastro_minero.geojson"),
}

os.makedirs(OUT_DIR, exist_ok=True)
print(f"Exportando shapefiles a: {OUT_DIR}\n")

# ── 1. GeoJSONs → Shapefile ──────────────────────────────────────────────────
for name, path in GEOJSONS.items():
    if not os.path.exists(path):
        print(f"  OMITIDO (no existe): {path}")
        continue

    gdf = gpd.read_file(path)
    out_path = os.path.join(OUT_DIR, f"{name}.shp")

    # Shapefiles tienen limite de 10 chars para nombres de columna
    # Acortar columnas largas
    rename_for_shp = {
        # Campos generales
        "partido_ganador":   "pty_ganador",
        "margen_victoria":   "margen_vic",
        "densidad_hab_km2":  "dens_habkm",
        "local_votacion":    "local_vot",
        "electores_hab":     "elect_hab",
        "total_votantes":    "tot_vot",
        "participacion":     "particip",
        "ausentismo":        "ausent",
        "pct_ganador":       "pct_gan",
        "longitud_cp":       "lon_cp",
        "latitud_cp":        "lat_cp",
        "region_nat":        "reg_nat",
        "cod_grupo":         "cod_grupo",
        "flag_tipo":         "flag_tipo",
        "departamento":      "depto",
        "area_km2":          "area_km2",
        # Preferencias diputados — votos absolutos (ya ≤10 chars algunos)
        "pref_yenifer":      "pref_yen",
        "pref_gabriel":      "pref_gab",
        "pref_jessica":      "pref_jes",
        "pref_juan":         "pref_juan",
        "pref_jibaja":       "pref_jib",
        "pref_ticlla":       "pref_tic",
        # Preferencias diputados — porcentajes
        "pref_yenifer_pct":  "pref_yen_p",
        "pref_gabriel_pct":  "pref_gab_p",
        "pref_jessica_pct":  "pref_jes_p",
        "pref_juan_pct":     "pref_jua_p",
        "pref_jibaja_pct":   "pref_jib_p",
        "pref_ticlla_pct":   "pref_tic_p",
        "diputado_dom":      "diput_dom",
    }
    gdf = gdf.rename(columns={k: v for k, v in rename_for_shp.items() if k in gdf.columns})
    gdf.to_file(out_path, driver="ESRI Shapefile", encoding="utf-8")
    size_kb = os.path.getsize(out_path) / 1e3
    print(f"  OK  {name}.shp  ({len(gdf)} filas, {size_kb:.0f} KB)")

# ── 2. Limites distritales (Encañada + Sorochuco) ────────────────────────────
print()
distritos = gpd.read_file(DISTRITOS_SHP)
distritos_filtrado = distritos[
    distritos["distrito"].str.upper().str.contains("SOROCHUCO|ENCA")
].copy()

# Asegurar campo que identifique cada distrito
out_path = os.path.join(OUT_DIR, "distritos.shp")
distritos_filtrado.to_file(out_path, driver="ESRI Shapefile", encoding="utf-8")
size_kb = os.path.getsize(out_path) / 1e3
print(f"  OK  distritos.shp  ({len(distritos_filtrado)} filas, {size_kb:.0f} KB)")
print(f"      Distritos incluidos: {distritos_filtrado['distrito'].tolist()}")

# ── 3. Puntos originales de centros poblados ─────────────────────────────────
print()

def find_shp_in_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        shps = [n for n in z.namelist() if n.endswith(".shp")]
    return shps[0] if shps else None

shp_name = find_shp_in_zip(CP_ZIP)
cp_all = gpd.read_file(f"zip://{CP_ZIP}!{shp_name}")
cp_filtrado = cp_all[
    cp_all["UBIGEO"].astype(str).str.startswith("060105") |
    cp_all["UBIGEO"].astype(str).str.startswith("060309")
].copy()

out_path = os.path.join(OUT_DIR, "centros_poblados_pts.shp")
cp_filtrado.to_file(out_path, driver="ESRI Shapefile", encoding="utf-8")
size_kb = os.path.getsize(out_path) / 1e3
print(f"  OK  centros_poblados_pts.shp  ({len(cp_filtrado)} puntos, {size_kb:.0f} KB)")
print(f"      Encañada: {(cp_filtrado['UBIGEO'].str.startswith('060105')).sum()} CPs")
print(f"      Sorochuco: {(cp_filtrado['UBIGEO'].str.startswith('060309')).sum()} CPs")

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
print("Exportacion completa. Archivos en:")
print(f"  {OUT_DIR}")
print()
print("Para abrir en QGIS:")
print("  1. Abrir QGIS > Proyecto > Nuevo")
print("  2. Arrastrar los .shp de qgis_export/ al panel de capas")
print("  3. Para editar colores: doble click en la capa > Simbologia")
print("  4. CRS recomendado para visualizar: EPSG:4326 (WGS84)")
print("  5. CRS para medir areas/distancias: EPSG:32717 (UTM 17S)")
print()

# Listar todos los archivos generados
total_kb = 0
for f in sorted(os.listdir(OUT_DIR)):
    path = os.path.join(OUT_DIR, f)
    kb = os.path.getsize(path) / 1e3
    total_kb += kb
    print(f"  {f:<40} {kb:>6.0f} KB")
print(f"\n  Total: {total_kb/1e3:.1f} MB")
