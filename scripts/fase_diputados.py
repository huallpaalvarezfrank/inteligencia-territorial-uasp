"""
Fase Diputados — enriquece ambos GeoJSONs con preferencias electorales 2026
Para cada centro poblado añade:
  pref_yenifer, pref_gabriel, pref_jessica, pref_juan, pref_jibaja, pref_ticlla
  (votos de preferencia / total_votantes_IE * 100)
  diputado_dom  — nombre del diputado con más preferencias en esa IE
"""

import os, sqlite3, json, warnings
import geopandas as gpd
import pandas as pd
warnings.filterwarnings("ignore")

BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = r"C:\Users\frank\Desktop\ESTRATEGIA\Actas\onpe_resultados.db"

GEOJSONS = {
    "encanada":  os.path.join(BASE, "frontend", "public", "mapa_final.geojson"),
    "sorochuco": os.path.join(BASE, "frontend", "public", "mapa_final_sorochuco.geojson"),
}

# Mapeo nombre_cand (DB) → clave corta
DIPUTADOS = {
    "YENIFER NOELIA PAREDES NAVARRO":      "pref_yenifer",
    "GABRIEL ROBERTINO GONZALES DELGADO":  "pref_gabriel",
    "JESSICA ROXANA GUEVARA RAMIREZ":      "pref_jessica",
    "JUAN AMILCAR VILLANUEVA CALDERON":    "pref_juan",
    "LUIS ANGEL JIBAJA RAMOS":             "pref_jibaja",
    "SEGUNDO SENOVIO TICLLA RAFAEL":       "pref_ticlla",
}
DIPUTADO_NOMBRE = {
    "pref_yenifer": "Yenifer Paredes",
    "pref_gabriel": "Gabriel Gonzales",
    "pref_jessica": "Jessica Guevara",
    "pref_juan":    "Juan Villanueva",
    "pref_jibaja":  "Luis Jibaja",
    "pref_ticlla":  "Segundo Ticlla",
}
PREF_COLS = list(DIPUTADO_NOMBRE.keys())

# ── 1. Consultar votos de preferencia por IE y diputado ───────────────────────
print("Consultando preferencias por IE...")
con = sqlite3.connect(DB_PATH)

q = """
    SELECT
        p.distrito,
        r.local_votacion,
        p.nombre_cand,
        SUM(p.votos_pref) AS votos_pref
    FROM preferencias_2026 p
    INNER JOIN (
        SELECT DISTINCT num_mesa, local_votacion, distrito
        FROM resultados_2026
        WHERE tipo_eleccion = 'PRESIDENCIAL'
    ) r ON p.num_mesa = r.num_mesa AND p.distrito = r.distrito
    WHERE (p.distrito LIKE '%ENCA%' OR p.distrito LIKE '%SOROCHUCO%')
      AND p.tipo_eleccion = 'DIPUTADOS'
    GROUP BY p.distrito, r.local_votacion, p.nombre_cand
"""
df_pref = pd.read_sql_query(q, con)

# Total votantes por IE (denominador para la tasa)
q_tv = """
    SELECT distrito, local_votacion,
           SUM(total_votantes) / COUNT(DISTINCT candidato) AS total_votantes
    FROM resultados_2026
    WHERE (distrito LIKE '%ENCA%' OR distrito LIKE '%SOROCHUCO%')
      AND tipo_eleccion = 'PRESIDENCIAL'
    GROUP BY distrito, local_votacion
"""
df_tv = pd.read_sql_query(q_tv, con)
con.close()

print(f"  Filas de preferencias: {len(df_pref)}")
print(f"  IEs únicas: {df_pref['local_votacion'].nunique()}")

# ── 2. Filtrar solo los 6 diputados electos y pivotar ─────────────────────────
df_pref["pref_key"] = df_pref["nombre_cand"].str.upper().str.strip().map(DIPUTADOS)
df_6 = df_pref[df_pref["pref_key"].notna()].copy()

pivot = (
    df_6.pivot_table(
        index=["distrito", "local_votacion"],
        columns="pref_key",
        values="votos_pref",
        aggfunc="sum",
        fill_value=0,
    )
    .reset_index()
)

# Asegurar que las 6 columnas existen
for col in PREF_COLS:
    if col not in pivot.columns:
        pivot[col] = 0

# Unir con total_votantes
pivot = pivot.merge(df_tv, on=["distrito", "local_votacion"], how="left")

# Porcentajes (votos pref / total votantes * 100)
for col in PREF_COLS:
    pivot[col + "_pct"] = (pivot[col] / pivot["total_votantes"] * 100).round(2)

PCT_COLS_CALC = [c + "_pct" for c in PREF_COLS]

# Diputado dominante por IE (por votos absolutos)
pivot["diputado_dom"] = pivot[PREF_COLS].idxmax(axis=1).map(DIPUTADO_NOMBRE)

print("\nRango de votos por diputado:")
for col in PREF_COLS:
    pct = col + "_pct"
    print(f"  {DIPUTADO_NOMBRE[col]:22s}: {pivot[col].min():.0f}–{pivot[col].max():.0f} votos  |  {pivot[pct].min():.1f}–{pivot[pct].max():.1f}%")

# ── 3. Enriquecer cada GeoJSON ────────────────────────────────────────────────
DISTRITO_LABEL = {"encanada": "ENCA", "sorochuco": "SOROCHUCO"}

for dist_id, geojson_path in GEOJSONS.items():
    print(f"\nEnriqueciendo {dist_id}...")
    gdf = gpd.read_file(geojson_path)
    print(f"  Registros: {len(gdf)}")

    # Filtrar solo las filas del distrito correspondiente
    mask = pivot["distrito"].str.upper().str.contains(DISTRITO_LABEL[dist_id])
    df_dist = pivot[mask][["local_votacion"] + PREF_COLS + PCT_COLS_CALC + ["diputado_dom"]].copy()

    # Eliminar columnas previas si ya existían (re-ejecución)
    cols_to_drop = [c for c in PREF_COLS + PCT_COLS_CALC + ["diputado_dom"] if c in gdf.columns]
    if cols_to_drop:
        gdf = gdf.drop(columns=cols_to_drop)

    # Join por local_votacion — cada CP hereda los totales de su IE
    gdf = gdf.merge(df_dist, on="local_votacion", how="left")

    # ── Distribuir votos IE → CP proporcionalmente por población ──────────────
    ie_pop_sum  = gdf.groupby("local_votacion")["poblacion"].transform("sum")
    ie_cp_count = gdf.groupby("local_votacion")["local_votacion"].transform("count")

    for col in PREF_COLS:
        ie_votes = gdf[col].fillna(0)
        # Reparto poblacional; igual entre CPs si toda la IE tiene poblacion 0
        share = gdf["poblacion"] / ie_pop_sum.where(ie_pop_sum > 0, ie_cp_count)
        gdf[col] = (ie_votes * share).round(0).fillna(0).astype(int)

    # pref_X_pct ya viene del merge (tasa a nivel IE) — se mantiene igual
    for col in PCT_COLS_CALC:
        gdf[col] = gdf[col].fillna(0).round(2)

    # Diputado dominante por CP
    gdf["diputado_dom"] = gdf[PREF_COLS].idxmax(axis=1).map(DIPUTADO_NOMBRE)

    print(f"  CPs con datos de preferencia: {(gdf['pref_yenifer'] > 0).sum()} / {len(gdf)}")
    print(f"  Diputado dominante:")
    print(f"  {gdf['diputado_dom'].value_counts().to_string()}")
    print(f"  Rango votos distribuidos por CP:")
    for col in PREF_COLS:
        print(f"    {DIPUTADO_NOMBRE[col]:22s}: {gdf[col].min()}–{gdf[col].max()} votos")

    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"  Exportado: {geojson_path}")

print("\nFase diputados completada.")
