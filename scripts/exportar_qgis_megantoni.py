"""
Exportar capas QGIS — Megantoni (La Convención, Cusco)
Misma logica que Puno/Encañada/Sorochuco:
  - Centros Poblados INEI (CP_CUSCO.zip) como unidad geografica base
  - Voronoi generado desde los puntos de CPs
  - sjoin_nearest: cada CP hereda datos del local de votacion mas cercano
  - Datos electorales: PRESIDENCIAL, SENADORES_DEM, DIPUTADOS
  - Preferencias: JxP candidatos en Cusco (Diputados + Senadores DEM)

INEI ubigeo Megantoni: 080914 (Cusco dept=08, La Convencion prov=09, Megantoni=14)
ONPE ubigeo Megantoni: 070915

Capas exportadas:
  1. centros_poblados.shp — Voronoi de 29 CPs con datos electorales
  2. locales_pts.shp      — 12 locales de votacion geocodificados
  3. distritos.shp        — Limite del distrito Megantoni
"""

import os, json, time, sqlite3, re, zipfile, warnings, requests
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.ops import voronoi_diagram
from shapely.geometry import MultiPoint, Point
from difflib import SequenceMatcher
warnings.filterwarnings("ignore")

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = r"C:\Users\frank\Desktop\ESTRATEGIA\ACTAS\onpe_resultados.db"
GADM_PATH = r"C:\Users\frank\Desktop\ESTRATEGIA\ACTAS\geo\gadm41_PER_3.json"
CP_ZIP    = os.path.join(BASE, "qgis_export", "Megantoni", "CP_CUSCO.zip")
OUT_DIR   = os.path.join(BASE, "qgis_export", "Megantoni")
OSM_CACHE = r"C:\Users\frank\Desktop\ESTRATEGIA\ACTAS\geo\megantoni_osm_places.json"
GEO_CACHE = r"C:\Users\frank\Desktop\ESTRATEGIA\ACTAS\geo\megantoni_geocode.json"

HEADERS = {"User-Agent": "InteligenciaTerritorial/1.0 frank.huallpa.alvarez@gmail.com"}

os.makedirs(OUT_DIR, exist_ok=True)
print(f"Exportando a: {OUT_DIR}\n")

# ── Coordenadas manuales para locales remotos (Amazon jungle) ─────────────────
# Coordenadas aproximadas basadas en ubicacion geografica de las comunidades
MANUAL_COORDS = {
    "IE JUAN SANTOS ATAHUALPA":              (-11.874, -73.013),  # Nuevo Mundo
    "IE 64443 CAMISEA":                      (-11.917, -72.659),  # Camisea
    "IEI 375 CAMISEA":                       (-11.917, -72.659),  # Camisea
    "IE 64450 PUERTO HUALLANA":              (-11.493, -72.779),  # Puerto Huallana
    "IE 64446 PRIMARIA":                     (-11.780, -72.770),  # Kirigueti area
    "IE CARLOS RIOS RIOS":                   (-11.780, -72.770),  # Kirigueti
    "IE 64553 TICUMPINIA":                   (-12.087, -72.765),  # Ticumpinia
    "IE 64449 PRIMARIA NUEVA LUZ":           (-11.690, -72.870),  # Nueva Luz
    "IE 50294 MONSENOR JAVIER ARIZ HUARTE PRIMARIA": (-11.917, -72.659),  # Camisea area
    "IEI 373 SHIVANKORENI":                  (-11.803, -72.777),  # Shivankoreni
    "IEI 331 TANGOSHIARI":                   (-11.540, -72.848),  # Tangoshiari
    "IE 64125 FRAY JULIAN MACEGOZA":         (-11.780, -72.770),  # Kirigueti area
}

import unicodedata as _ud
def _strip(s):
    return ''.join(c for c in _ud.normalize('NFD', str(s)) if _ud.category(c) != 'Mn').upper().replace(' ', '')


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CENTROS POBLADOS — Megantoni (INEI ubigeo 080914)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("FASE 1 — CENTROS POBLADOS")
print("=" * 60)

shp_name = "CUSCO_CCPP_geogpsperu_SuyoPomalia.shp"
cp_all = gpd.read_file(f"zip://{CP_ZIP}!{shp_name}")

MEGANTONI_UBIGEO = "080914"   # INEI: Cusco=08, LaConvencion=09, Megantoni=14
cp = cp_all[cp_all["UBIGEO"].astype(str).str.startswith(MEGANTONI_UBIGEO)].copy().reset_index(drop=True)

print(f"CPs totales Cusco: {len(cp_all)}")
print(f"CPs en Megantoni: {len(cp)}")
if len(cp) > 0:
    print(f"  Poblacion total: {cp['POBLACION'].sum():,.0f} hab")
    print(cp[["UBIGEO","DESCRIPCIO","POBLACION","LATITUD","LONGITUD"]].to_string())


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LIMITES DISTRITALES — GADM
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("FASE 2 — LIMITE DISTRITAL")
print("=" * 60)

gadm = gpd.read_file(GADM_PATH)
gadm_cusco = gadm[gadm["NAME_1"].apply(_strip).str.contains("CUSCO")].copy()

mask_meg = gadm_cusco["NAME_3"].apply(_strip).str.contains("MEGANTONI")
distritos_gdf = gadm_cusco[mask_meg].copy()

if len(distritos_gdf) == 0:
    # Intentar por provincia La Convencion y distrito Megantoni
    mask_prov = gadm_cusco["NAME_2"].apply(_strip).str.contains("CONVENCION")
    mask_dist = gadm_cusco["NAME_3"].apply(_strip).str.contains("MEGANTONI")
    distritos_gdf = gadm_cusco[mask_prov & mask_dist].copy()

print(f"Distritos GADM encontrados: {len(distritos_gdf)}")
if len(distritos_gdf) > 0:
    print(f"  {distritos_gdf[['NAME_1','NAME_2','NAME_3']].to_string()}")

# Si GADM no tiene Megantoni, construir limite desde convex hull de CPs
if len(distritos_gdf) == 0:
    print("  ADVERTENCIA: Megantoni no en GADM — usando convex hull de CPs")
    limite = MultiPoint(cp.geometry.values.tolist()).convex_hull.buffer(0.03)
    distritos_gdf = gpd.GeoDataFrame(
        {"NAME_1": ["Cusco"], "NAME_2": ["La Convencion"], "NAME_3": ["Megantoni"]},
        geometry=[limite], crs="EPSG:4326"
    )

limite_distrito = distritos_gdf.to_crs("EPSG:4326").union_all()

# Exportar distritos.shp
distritos_out = distritos_gdf[["NAME_1","NAME_2","NAME_3","geometry"]].copy()
distritos_out = distritos_out.rename(columns={"NAME_1":"depto","NAME_2":"provincia","NAME_3":"distrito"})
distritos_out.to_file(os.path.join(OUT_DIR, "distritos.shp"), driver="ESRI Shapefile", encoding="utf-8")
print(f"  OK distritos.shp ({len(distritos_out)} poligono)")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. VORONOI desde puntos de centros poblados
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("FASE 3 — VORONOI DE CENTROS POBLADOS")
print("=" * 60)

# Verificar cobertura CP vs limite GADM
pts_en_limite = cp.geometry.within(limite_distrito).sum()
cobertura_pct = pts_en_limite / len(cp) if len(cp) > 0 else 0
print(f"  {pts_en_limite}/{len(cp)} CPs dentro del limite GADM ({cobertura_pct:.0%})")
if cobertura_pct < 0.5:
    print(f"  Baja cobertura — usando convex hull de CPs como limite")
    limite_distrito = MultiPoint(cp.geometry.values.tolist()).convex_hull.buffer(0.03)

# Eliminar duplicados geograficos
cp["_ck"] = cp["LATITUD"].round(5).astype(str) + "," + cp["LONGITUD"].round(5).astype(str)
cp = cp.drop_duplicates(subset="_ck").drop(columns="_ck").reset_index(drop=True)
puntos = cp.geometry.values.tolist()

print(f"  CPs unicos: {len(cp)}")

if len(puntos) == 0:
    raise ValueError("Sin centros poblados para Megantoni. Verificar ubigeo INEI.")
elif len(puntos) == 1:
    voronoi_frames = [dict(cp.iloc[0].to_dict(), geometry=limite_distrito)]
    print("  1 CP -> area completa")
else:
    multi    = MultiPoint(puntos)
    envelope = limite_distrito.buffer(0.08)
    regions  = voronoi_diagram(multi, envelope=envelope)
    voronoi_polys = list(regions.geoms)

    voronoi_frames = []
    for vp in voronoi_polys:
        clipped = vp.intersection(limite_distrito)
        if clipped.is_empty:
            continue
        idx = cp.geometry.distance(vp.centroid).idxmin()
        row = cp.loc[idx].to_dict()
        row["geometry"] = clipped
        voronoi_frames.append(row)

    print(f"  {len(cp)} CPs -> {len(voronoi_frames)} celdas Voronoi")

cp_voronoi = gpd.GeoDataFrame(voronoi_frames, crs="EPSG:4326").reset_index(drop=True)
print(f"  CPs con poblacion: {(cp_voronoi['POBLACION'] > 0).sum()}")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DATOS ELECTORALES — desde SQLite
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("FASE 4 — DATOS ELECTORALES")
print("=" * 60)

con = sqlite3.connect(DB_PATH)

# Presidencial
df_p = pd.read_sql_query("""
    SELECT distrito, provincia, local_votacion,
           SUM(CASE WHEN candidato LIKE '%JUNTOS%'    THEN votos ELSE 0 END) AS votos_jxp_p,
           SUM(CASE WHEN candidato LIKE '%AHORA%'     THEN votos ELSE 0 END) AS votos_an_p,
           SUM(CASE WHEN candidato LIKE '%FUERZA%'    THEN votos ELSE 0 END) AS votos_fp_p,
           SUM(CASE WHEN candidato LIKE '%OBRAS%'     THEN votos ELSE 0 END) AS votos_obras_p,
           SUM(CASE WHEN candidato LIKE '%RENOVACI%'  THEN votos ELSE 0 END) AS votos_rp_p,
           SUM(CASE WHEN candidato LIKE '%PODEMOS%'   THEN votos ELSE 0 END) AS votos_pp_p,
           SUM(votos_validos) / COUNT(DISTINCT candidato) AS votos_val_p,
           SUM(total_votantes) / COUNT(DISTINCT candidato) AS total_vot,
           SUM(electores_hab)  / COUNT(DISTINCT candidato) AS electores,
           COUNT(DISTINCT num_mesa) AS mesas
    FROM resultados_2026
    WHERE departamento LIKE '%CUSCO%' AND distrito = 'MEGANTONI'
      AND tipo_eleccion = 'PRESIDENCIAL'
      AND local_votacion IS NOT NULL AND local_votacion != ''
    GROUP BY distrito, provincia, local_votacion
""", con)

# Senadores DEM (circunscripcion Cusco)
df_s = pd.read_sql_query("""
    SELECT distrito, local_votacion,
           SUM(CASE WHEN candidato LIKE '%JUNTOS%'   THEN votos ELSE 0 END) AS votos_jxp_d,
           SUM(CASE WHEN candidato LIKE '%AHORA%'    THEN votos ELSE 0 END) AS votos_an_d,
           SUM(CASE WHEN candidato LIKE '%FUERZA%'   THEN votos ELSE 0 END) AS votos_fp_d,
           SUM(CASE WHEN candidato LIKE '%OBRAS%'    THEN votos ELSE 0 END) AS votos_obras_d,
           SUM(votos_validos) / COUNT(DISTINCT candidato) AS votos_val_d
    FROM resultados_2026
    WHERE departamento LIKE '%CUSCO%' AND distrito = 'MEGANTONI'
      AND tipo_eleccion = 'SENADORES_DEM'
      AND local_votacion IS NOT NULL AND local_votacion != ''
    GROUP BY distrito, local_votacion
""", con)

# Diputados (circunscripcion Cusco)
df_d = pd.read_sql_query("""
    SELECT distrito, local_votacion,
           SUM(CASE WHEN candidato LIKE '%JUNTOS%'  THEN votos ELSE 0 END) AS votos_jxp_dip,
           SUM(CASE WHEN candidato LIKE '%AHORA%'   THEN votos ELSE 0 END) AS votos_an_dip,
           SUM(votos_validos) / COUNT(DISTINCT candidato) AS votos_val_dip
    FROM resultados_2026
    WHERE departamento LIKE '%CUSCO%' AND distrito = 'MEGANTONI'
      AND tipo_eleccion = 'DIPUTADOS'
      AND local_votacion IS NOT NULL AND local_votacion != ''
    GROUP BY distrito, local_votacion
""", con)

df_elec = df_p.merge(df_s, on=["distrito","local_votacion"], how="left")
df_elec = df_elec.merge(df_d, on=["distrito","local_votacion"], how="left")

# Preferencias Diputados — top 4 JxP Cusco
df_pref_d = pd.read_sql_query("""
    SELECT r.distrito, r.local_votacion,
           SUM(CASE WHEN p.nombre_cand LIKE '%HUACAC%'    THEN p.votos_pref ELSE 0 END) AS pref_huacac,
           SUM(CASE WHEN p.nombre_cand LIKE '%MARQUEZ%'   THEN p.votos_pref ELSE 0 END) AS pref_marq,
           SUM(CASE WHEN p.nombre_cand LIKE '%PEREZ%MALLQUI%' OR p.nombre_cand LIKE '%MALLQUI%'
                    THEN p.votos_pref ELSE 0 END) AS pref_mallq,
           SUM(CASE WHEN p.nombre_cand LIKE '%MAMANI%CARDONA%' OR p.nombre_cand LIKE '%SIMON%MAMANI%'
                    THEN p.votos_pref ELSE 0 END) AS pref_maman
    FROM preferencias_2026 p
    INNER JOIN (
        SELECT DISTINCT num_mesa, local_votacion, distrito
        FROM resultados_2026
        WHERE departamento LIKE '%CUSCO%' AND distrito='MEGANTONI'
          AND tipo_eleccion='DIPUTADOS'
    ) r ON p.num_mesa = r.num_mesa AND p.distrito = r.distrito
    WHERE p.departamento LIKE '%CUSCO%' AND p.tipo_eleccion = 'DIPUTADOS'
    GROUP BY r.distrito, r.local_votacion
""", con)

# Preferencias Senadores DEM — top 2 JxP Cusco
df_pref_s = pd.read_sql_query("""
    SELECT r.distrito, r.local_votacion,
           SUM(CASE WHEN p.nombre_cand LIKE '%JANCCO%'  THEN p.votos_pref ELSE 0 END) AS pref_jancc,
           SUM(CASE WHEN p.nombre_cand LIKE '%VERANO%'  THEN p.votos_pref ELSE 0 END) AS pref_veran
    FROM preferencias_2026 p
    INNER JOIN (
        SELECT DISTINCT num_mesa, local_votacion, distrito
        FROM resultados_2026
        WHERE departamento LIKE '%CUSCO%' AND distrito='MEGANTONI'
          AND tipo_eleccion='SENADORES_DEM'
    ) r ON p.num_mesa = r.num_mesa AND p.distrito = r.distrito
    WHERE p.departamento LIKE '%CUSCO%' AND p.tipo_eleccion = 'SENADORES_DEM'
    GROUP BY r.distrito, r.local_votacion
""", con)

con.close()

df_elec = df_elec.merge(df_pref_d, on=["distrito","local_votacion"], how="left")
df_elec = df_elec.merge(df_pref_s, on=["distrito","local_votacion"], how="left")
df_elec = df_elec.fillna(0)

# Calcular porcentajes
df_elec["pct_jxp_p"]   = (df_elec["votos_jxp_p"]  / df_elec["votos_val_p"].replace(0,1) * 100).round(2)
df_elec["pct_an_p"]    = (df_elec["votos_an_p"]   / df_elec["votos_val_p"].replace(0,1) * 100).round(2)
df_elec["pct_fp_p"]    = (df_elec["votos_fp_p"]   / df_elec["votos_val_p"].replace(0,1) * 100).round(2)
df_elec["pct_obras_p"] = (df_elec["votos_obras_p"] / df_elec["votos_val_p"].replace(0,1) * 100).round(2)
df_elec["pct_rp_p"]    = (df_elec["votos_rp_p"]   / df_elec["votos_val_p"].replace(0,1) * 100).round(2)
df_elec["pct_jxp_d"]   = (df_elec["votos_jxp_d"]  / df_elec["votos_val_d"].replace(0,1) * 100).round(2)
df_elec["pct_jxp_dip"] = (df_elec["votos_jxp_dip"]/ df_elec["votos_val_dip"].replace(0,1) * 100).round(2)
df_elec["particip"]    = (df_elec["total_vot"]     / df_elec["electores"].replace(0,1) * 100).round(2)
df_elec["pct_huacac"]  = (df_elec["pref_huacac"] / df_elec["total_vot"].replace(0,1) * 100).round(2)
df_elec["pct_marq"]    = (df_elec["pref_marq"]   / df_elec["total_vot"].replace(0,1) * 100).round(2)
df_elec["pct_mallq"]   = (df_elec["pref_mallq"]  / df_elec["total_vot"].replace(0,1) * 100).round(2)
df_elec["pct_maman"]   = (df_elec["pref_maman"]  / df_elec["total_vot"].replace(0,1) * 100).round(2)
df_elec["pct_jancc"]   = (df_elec["pref_jancc"]  / df_elec["total_vot"].replace(0,1) * 100).round(2)
df_elec["pct_veran"]   = (df_elec["pref_veran"]  / df_elec["total_vot"].replace(0,1) * 100).round(2)

print(f"Locales de votacion en DB: {len(df_elec)}")
print(df_elec[["local_votacion","mesas","pct_jxp_p","pct_an_p","pct_fp_p","pct_obras_p"]].to_string(index=False))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. GEOCODIFICAR LOCALES — zona amazonica, usar coords manuales + CP match
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("FASE 5 — GEOCODIFICACION DE LOCALES")
print("=" * 60)

def clean(s):
    s = str(s).upper()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

import unicodedata

def best_osm_match(nombre, candidates, threshold=0.45):
    cn = clean(nombre)
    best_score, best_place = 0, None
    for place in candidates:
        cp_name = clean(place["name"])
        score = SequenceMatcher(None, cn, cp_name).ratio()
        nums_n = set(re.findall(r'\d{4,}', cn))
        nums_p = set(re.findall(r'\d{4,}', cp_name))
        if nums_n and nums_n & nums_p:
            score = max(score, 0.8)
        if score > best_score:
            best_score, best_place = score, place
    return (best_place, best_score) if best_score >= threshold else (None, best_score)

def match_cp(nombre_local, cp_gdf):
    """Busca el CP mas parecido al nombre del local de votacion."""
    cn = clean(nombre_local)
    best_score, best_idx = 0, None
    for idx, row in cp_gdf.iterrows():
        cp_name = clean(str(row.get("DESCRIPCIO", "")))
        score = SequenceMatcher(None, cn, cp_name).ratio()
        # Extra score si los numeros coinciden
        nums_n = set(re.findall(r'\d{4,}', cn))
        nums_p = set(re.findall(r'\d{4,}', cp_name))
        if nums_n and nums_n & nums_p:
            score = max(score, 0.7)
        if score > best_score:
            best_score, best_idx = score, idx
    if best_score >= 0.35 and best_idx is not None:
        r = cp_gdf.loc[best_idx]
        return (float(r["LATITUD"]), float(r["LONGITUD"]), best_score)
    return (None, None, best_score)

# Cargar cache OSM (puede estar vacio para zona amazonica)
if os.path.exists(OSM_CACHE):
    with open(OSM_CACHE, encoding="utf-8") as f:
        osm_places = json.load(f)
    print(f"OSM cache: {len(osm_places)} lugares")
else:
    print("Sin cache OSM — descargando para area amazonica de Cusco...")
    query = ("[out:json][timeout:90];("
             "node['amenity'~'school|university|college|community_centre']"
             "(-13.5,-74.5,-11.0,-72.0);"
             "way['amenity'~'school|university|college']"
             "(-13.5,-74.5,-11.0,-72.0);"
             ");out center;")
    try:
        url = f"https://overpass-api.de/api/interpreter?data={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=120)
        data = r.json()
        osm_places = []
        for el in data.get("elements", []):
            name = el.get("tags", {}).get("name", "")
            if not name: continue
            lat = el["lat"] if el["type"] == "node" else el.get("center", {}).get("lat")
            lon = el["lon"] if el["type"] == "node" else el.get("center", {}).get("lon")
            if lat and lon:
                osm_places.append({"name": name, "lat": lat, "lon": lon})
        with open(OSM_CACHE, "w", encoding="utf-8") as f:
            json.dump(osm_places, f, ensure_ascii=False)
        print(f"Descargados: {len(osm_places)} lugares OSM")
    except Exception as e:
        print(f"  OSM error: {e} — usando solo coords manuales")
        osm_places = []
        with open(OSM_CACHE, "w", encoding="utf-8") as f:
            json.dump(osm_places, f)

geo_cache = json.load(open(GEO_CACHE, encoding="utf-8")) if os.path.exists(GEO_CACHE) else {}

coords = []
for _, row in df_elec.iterrows():
    key       = f"{row['local_votacion']}|MEGANTONI"
    local_key = clean(row['local_votacion'])

    # Prioridad 1: cache
    if key in geo_cache and geo_cache[key]:
        coords.append(tuple(geo_cache[key]))
        print(f"  CACHE {row['local_votacion'][:50]}")
        continue

    # Prioridad 2: coordenadas manuales
    found = False
    for mk, mc in MANUAL_COORDS.items():
        if clean(mk) in local_key or local_key in clean(mk):
            coords.append(mc)
            geo_cache[key] = list(mc)
            print(f"  MANUAL {row['local_votacion'][:50]} -> {mc}")
            found = True; break
    if found: continue

    # Prioridad 3: match nombre de CP en shapefile INEI
    lat_cp, lon_cp, score_cp = match_cp(row['local_votacion'], cp)
    if lat_cp:
        coords.append((lat_cp, lon_cp))
        geo_cache[key] = [lat_cp, lon_cp]
        print(f"  CP({score_cp:.2f}) {row['local_votacion'][:50]} -> {lat_cp:.4f},{lon_cp:.4f}")
        continue

    # Prioridad 4: OSM
    if osm_places:
        match, score = best_osm_match(row["local_votacion"], osm_places)
        if match:
            coords.append((match["lat"], match["lon"]))
            geo_cache[key] = [match["lat"], match["lon"]]
            print(f"  OSM({score:.2f}) {row['local_votacion'][:50]} -> {match['name'][:40]}")
            continue

    # Prioridad 5: Nominatim
    nom_found = False
    for q in [f"{row['local_votacion']}, Megantoni, La Convencion, Cusco, Peru",
               f"Megantoni, La Convencion, Cusco, Peru"]:
        try:
            r2 = requests.get("https://nominatim.openstreetmap.org/search",
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "pe"},
                headers=HEADERS, timeout=10)
            results = r2.json()
            time.sleep(1.1)
            if results:
                lat2, lon2 = float(results[0]["lat"]), float(results[0]["lon"])
                if -14.0 <= lat2 <= -10.0 and -75.0 <= lon2 <= -71.0:
                    coords.append((lat2, lon2))
                    geo_cache[key] = [lat2, lon2]
                    print(f"  NOM {row['local_votacion'][:50]} -> {lat2:.4f},{lon2:.4f}")
                    nom_found = True; break
        except:
            time.sleep(1)
    if nom_found: continue

    coords.append(None)
    geo_cache[key] = None
    print(f"  ??  {row['local_votacion'][:50]}")

with open(GEO_CACHE, "w", encoding="utf-8") as f:
    json.dump(geo_cache, f, ensure_ascii=False)

df_elec["lat"] = [c[0] if c else None for c in coords]
df_elec["lon"] = [c[1] if c else None for c in coords]

# Fallback: centroide del distrito
centroide = distritos_gdf.iloc[0].geometry.centroid
for i, row in df_elec.iterrows():
    if pd.isna(df_elec.at[i, "lat"]):
        df_elec.at[i, "lat"] = centroide.y
        df_elec.at[i, "lon"] = centroide.x
        print(f"  Fallback centroide: {row['local_votacion'][:45]}")

df_elec = df_elec.dropna(subset=["lat","lon"])
print(f"\nLocales geocodificados: {len(df_elec)}")

# GeoDataFrame de locales
ies_gdf = gpd.GeoDataFrame(
    df_elec.copy(),
    geometry=gpd.points_from_xy(df_elec["lon"], df_elec["lat"]),
    crs="EPSG:4326"
)

# Exportar locales_pts.shp
rename_pts = {
    "local_votacion": "local_vot",
    "votos_jxp_p":    "v_jxp_p",
    "votos_an_p":     "v_an_p",
    "votos_fp_p":     "v_fp_p",
    "votos_obras_p":  "v_obras_p",
    "votos_rp_p":     "v_rp_p",
    "votos_jxp_d":    "v_jxp_d",
    "votos_jxp_dip":  "v_jxp_dip",
    "total_vot":      "tot_vot",
    "electores":      "electores",
    "pct_jxp_p":      "pct_jxp_p",
    "pct_an_p":       "pct_an_p",
    "pct_fp_p":       "pct_fp_p",
    "pct_obras_p":    "pct_obras_",
    "pct_rp_p":       "pct_rp_p",
    "pct_jxp_d":      "pct_jxp_d",
    "pct_jxp_dip":    "pct_jxp_di",
    "particip":       "particip",
    "pref_huacac":    "pref_huac",
    "pref_marq":      "pref_marq",
    "pref_mallq":     "pref_mallq",
    "pref_maman":     "pref_maman",
    "pref_jancc":     "pref_jancc",
    "pref_veran":     "pref_veran",
    "pct_huacac":     "pct_huac",
    "pct_marq":       "pct_marq",
    "pct_mallq":      "pct_mallq",
    "pct_maman":      "pct_maman",
    "pct_jancc":      "pct_jancc",
    "pct_veran":      "pct_veran",
}
pts_out = ies_gdf.rename(columns={k:v for k,v in rename_pts.items() if k in ies_gdf.columns})
pts_out.to_file(os.path.join(OUT_DIR, "locales_pts.shp"), driver="ESRI Shapefile", encoding="utf-8")
print(f"  OK locales_pts.shp ({len(pts_out)} puntos)")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. SJOIN NEAREST — cada CP hereda datos del local mas cercano
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("FASE 6 — ASIGNAR ELECTORAL A CENTROS POBLADOS")
print("=" * 60)

cp_centroids = cp_voronoi.copy()
cp_centroids["geometry"] = cp_voronoi.geometry.centroid

# UTM zona 18S (Peru central/sur)
cp_utm  = cp_centroids.to_crs("EPSG:32718")
ies_utm = ies_gdf.to_crs("EPSG:32718")

elec_cols = [
    "local_votacion", "mesas", "total_vot", "electores",
    "votos_jxp_p", "votos_an_p", "votos_fp_p", "votos_obras_p", "votos_rp_p", "votos_val_p",
    "votos_jxp_d", "votos_an_d", "votos_val_d",
    "votos_jxp_dip", "votos_an_dip", "votos_val_dip",
    "pref_huacac", "pref_marq", "pref_mallq", "pref_maman",
    "pref_jancc", "pref_veran",
    "pct_jxp_p", "pct_an_p", "pct_fp_p", "pct_obras_p", "pct_rp_p",
    "pct_jxp_d", "pct_jxp_dip", "particip",
    "pct_huacac", "pct_marq", "pct_mallq", "pct_maman",
    "pct_jancc", "pct_veran",
    "geometry",
]
elec_cols_clean = [c for c in elec_cols if c in ies_utm.columns]

joined = gpd.sjoin_nearest(
    cp_utm[["UBIGEO","DESCRIPCIO","CATEGORIA","POBLACION","ALTITUD",
            "PROVINCIA","DISTRITO","REGION_NAT","LONGITUD","LATITUD","CODIGO","geometry"]],
    ies_utm[elec_cols_clean],
    how="left",
    distance_col="dist_m"
)
joined = joined[~joined.index.duplicated(keep="first")].reset_index(drop=True)

print(f"  Join completado: {len(joined)} CPs")
print(f"  Distancia max al local mas cercano: {joined['dist_m'].max()/1000:.1f} km")
print(f"  Distancia media: {joined['dist_m'].mean()/1000:.1f} km")

# Restaurar geometrias Voronoi
joined["geometry"] = cp_voronoi.geometry.values
joined = gpd.GeoDataFrame(joined, geometry="geometry", crs="EPSG:4326")

# Partido ganador presidencial
def partido_ganador_row(row):
    candidatos = {
        "JxP":   row.get("pct_jxp_p", 0),
        "AhoraN": row.get("pct_an_p",  0),
        "FP":    row.get("pct_fp_p",  0),
        "Obras":  row.get("pct_obras_p", 0),
        "RP":    row.get("pct_rp_p",  0),
    }
    candidatos = {k: v for k, v in candidatos.items() if v and v > 0}
    if not candidatos:
        return None
    return max(candidatos, key=candidatos.get)

joined["pty_gan"]  = joined.apply(partido_ganador_row, axis=1)
joined_utm         = joined.to_crs("EPSG:32718")
joined["area_km2"] = (joined_utm.geometry.area / 1e6).round(3)
joined["dens_hab"] = (joined["POBLACION"] / joined["area_km2"].replace(0, np.nan)).round(1)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. EXPORTAR centros_poblados.shp
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("FASE 7 — EXPORTAR centros_poblados.shp")
print("=" * 60)

rename_cp = {
    "UBIGEO":         "ubigeo",
    "DESCRIPCIO":     "nombre",
    "CATEGORIA":      "categ",
    "POBLACION":      "poblacion",
    "ALTITUD":        "altitud",
    "PROVINCIA":      "provincia",
    "DISTRITO":       "distrito",
    "REGION_NAT":     "reg_nat",
    "LONGITUD":       "lon_cp",
    "LATITUD":        "lat_cp",
    "CODIGO":         "codigo",
    "local_votacion": "local_vot",
    "total_vot":      "tot_vot",
    "electores":      "electores",
    "votos_jxp_p":    "v_jxp_p",
    "votos_an_p":     "v_an_p",
    "votos_fp_p":     "v_fp_p",
    "votos_obras_p":  "v_obras_p",
    "votos_rp_p":     "v_rp_p",
    "votos_jxp_d":    "v_jxp_d",
    "votos_jxp_dip":  "v_jxp_dip",
    "pref_huacac":    "pref_huac",
    "pref_marq":      "pref_marq",
    "pref_mallq":     "pref_mallq",
    "pref_maman":     "pref_maman",
    "pref_jancc":     "pref_jancc",
    "pref_veran":     "pref_veran",
    "pct_jxp_p":      "pct_jxp_p",
    "pct_an_p":       "pct_an_p",
    "pct_fp_p":       "pct_fp_p",
    "pct_obras_p":    "pct_obras_",
    "pct_rp_p":       "pct_rp_p",
    "pct_jxp_d":      "pct_jxp_d",
    "pct_jxp_dip":    "pct_jxp_di",
    "particip":       "particip",
    "pct_huacac":     "pct_huac",
    "pct_marq":       "pct_marq",
    "pct_mallq":      "pct_mallq",
    "pct_maman":      "pct_maman",
    "pct_jancc":      "pct_jancc",
    "pct_veran":      "pct_veran",
    "dist_m":         "dist_m",
    "pty_gan":        "pty_gan",
    "area_km2":       "area_km2",
    "dens_hab":       "dens_hab",
}

cols_keep = [c for c in list(rename_cp.keys()) + ["geometry"] if c in joined.columns]
final = joined[cols_keep].copy()
final = final.rename(columns={k:v for k,v in rename_cp.items() if k in final.columns})

final.to_file(os.path.join(OUT_DIR, "centros_poblados.shp"), driver="ESRI Shapefile", encoding="utf-8")
print(f"  OK centros_poblados.shp ({len(final)} CPs)")


# ══ Generar GeoJSON para frontend ═════════════════════════════════════════════
print("\n" + "=" * 60)
print("FASE 8 — GENERAR GeoJSON para frontend")
print("=" * 60)

geojson_path = os.path.join(BASE, "frontend", "public", "mapa_megantoni.geojson")
final_simplified = final.copy()
final_simplified["geometry"] = final_simplified["geometry"].simplify(0.0001)
final_simplified.to_file(geojson_path, driver="GeoJSON")
size_mb = os.path.getsize(geojson_path) / 1e6
print(f"  OK mapa_megantoni.geojson ({size_mb:.2f} MB) -> {geojson_path}")

distritos_geojson = os.path.join(BASE, "frontend", "public", "distritos_megantoni.geojson")
distritos_out.to_file(distritos_geojson, driver="GeoJSON")
print(f"  OK distritos_megantoni.geojson -> {distritos_geojson}")

# ── Resumen ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"Exportacion completa: {OUT_DIR}")
print()
total_kb = 0
for fname in sorted(os.listdir(OUT_DIR)):
    if fname.endswith(".zip"):
        continue
    path = os.path.join(OUT_DIR, fname)
    kb = os.path.getsize(path) / 1e3
    total_kb += kb
    print(f"  {fname:<44} {kb:>6.0f} KB")
print(f"\n  Total: {total_kb/1e3:.2f} MB")
print()
print("Capas para QGIS:")
print("  1. distritos.shp        — Limite del distrito Megantoni")
print("  2. centros_poblados.shp — Voronoi de CPs con datos electorales")
print("  3. locales_pts.shp      — 12 locales de votacion geocodificados")
print()
print("Campos clave en centros_poblados.shp:")
print("  ubigeo / nombre / categ / poblacion — datos INEI del CP")
print("  local_vot — local de votacion mas cercano")
print("  dist_m    — distancia al local en metros")
print("  pct_jxp_p  — % JxP Presidencial")
print("  pct_an_p   — % Ahora Nacion Presidencial")
print("  pct_fp_p   — % Fuerza Popular Presidencial")
print("  pct_obras_ — % Obras Presidencial")
print("  pct_jxp_d  — % JxP Senadores DEM")
print("  pct_jxp_di — % JxP Diputados")
print("  particip   — % Participacion")
print("  pct_huac   — % Maria Luz Huacac (Dip. #1 JxP Cusco)")
print("  pct_marq   — % Anali Marquez (Dip. #2 JxP Cusco)")
print("  pct_mallq  — % Julian Perez Mallqui (Dip. #3 JxP Cusco)")
print("  pct_maman  — % Simon Mamani Cardona (Dip. #4 JxP Cusco)")
print("  pct_jancc  — % Juana Jancco (Sen. #1 JxP Cusco)")
print("  pct_veran  — % Wilfredo Verano (Sen. #2 JxP Cusco)")
print("  pty_gan    — Partido ganador presidencial")
