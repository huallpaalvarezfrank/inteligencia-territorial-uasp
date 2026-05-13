"""
Fase 5 — Integrar variables censales REDATAM al mapa final
============================================================
Entrada:  Excels exportados manualmente desde censos2017.inei.gob.pe/redatam/
          (uno por variable, guardados en data/redatam/)
Salida:   frontend/public/mapa_final.geojson  (con campos censales añadidos)

Variables esperadas:
  agua_pct     — % viviendas con red pública de agua (dentro o fuera)
  luz_pct      — % viviendas con alumbrado eléctrico de red pública
  sanit_pct    — % viviendas con desagüe a red pública (dentro o fuera)

Para exportar desde REDATAM (instrucciones en README_REDATAM.md):
  - Unidad geográfica: Centro Poblado
  - Filtro: Cajamarca / Cajamarca / La Encañada
  - Variable agua:    V104 - Abastecimiento de agua
  - Variable luz:     V112 - Alumbrado eléctrico
  - Variable sanit:   V108 - Servicio higiénico conectado a...
  Exportar cada una a Excel en data/redatam/
"""

import os, re, json
import pandas as pd
from difflib import SequenceMatcher

BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REDATAM_DIR = os.path.join(BASE, "data", "redatam")
MAPA_IN   = os.path.join(BASE, "frontend", "public", "mapa_final.geojson")
MAPA_OUT  = os.path.join(BASE, "frontend", "public", "mapa_final.geojson")

os.makedirs(REDATAM_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de parsing del Excel REDATAM
# ─────────────────────────────────────────────────────────────────────────────

def parse_redatam_excel(filepath, categoria_positiva):
    """
    Parsea un Excel exportado desde REDATAM y devuelve:
      {nombre_cp: pct_positivo, ...}

    categoria_positiva: lista de strings que identifican la categoría "favorable"
    Ejemplos:
      agua:  ["Red pública dentro", "Red pública fuera"]
      luz:   ["Red pública de energía eléctrica", "Red pública"]
      sanit: ["Red pública de desagüe dentro", "Red pública de desagüe fuera"]

    Si el Excel tiene el nombre de la categoría exacto, lo busca.
    Si no, busca substrings (case insensitive).
    """
    df = pd.read_excel(filepath, header=None)

    results = {}
    current_cp = None

    for i, row in df.iterrows():
        row_vals = [str(x).strip() for x in row if str(x).strip() and str(x).strip() != "nan"]
        if not row_vals:
            continue

        # Detectar encabezado de área
        # Formato: "AREA # XXXXXXXX  NombreCP, ..."
        area_match = re.match(r"AREA\s*#\s*\d+", row_vals[0], re.IGNORECASE)
        if area_match and len(row_vals) >= 2:
            # Extraer nombre del CP de la descripción
            desc = row_vals[1]
            # Descripción tipo: "060105..., Cajamarca,Cajamarca,Encañada,Centro Poblado: NOMBRE CP,..."
            cp_match = re.search(r"Centro Poblado:\s*([^,]+)", desc, re.IGNORECASE)
            if cp_match:
                current_cp = cp_match.group(1).strip().upper()
            else:
                # Intentar extraer desde AREA si la descripción está en otra col
                current_cp = None
            continue

        # Detectar fila de área alternativa (solo código en columna 0)
        if row_vals[0].startswith("AREA #") and len(row_vals) == 1:
            # La descripción puede estar en la siguiente fila; no la procesamos por ahora
            current_cp = None
            continue

        # Detectar fila de datos con porcentaje
        if current_cp is not None and len(row_vals) >= 3:
            categoria = row_vals[0]
            try:
                pct = float(row_vals[2])  # columna "%"
            except (ValueError, IndexError):
                continue

            # Verificar si esta categoría es la positiva
            cat_upper = categoria.upper()
            for cat_pos in categoria_positiva:
                if cat_pos.upper() in cat_upper:
                    results[current_cp] = results.get(current_cp, 0) + pct
                    break

    return results


def match_nombres(cp_redatam: str, nombres_mapa: list) -> str | None:
    """
    Busca el nombre más similar en el mapa para un nombre de CP de REDATAM.
    Retorna None si la similitud es menor a 0.6.
    """
    # Exacto primero
    if cp_redatam in nombres_mapa:
        return cp_redatam

    # Buscar por substring
    for n in nombres_mapa:
        if cp_redatam in n or n in cp_redatam:
            return n

    # Similitud difusa
    best, best_score = None, 0
    for n in nombres_mapa:
        score = SequenceMatcher(None, cp_redatam, n).ratio()
        if score > best_score:
            best, best_score = n, score

    if best_score >= 0.6:
        return best
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Buscar archivos Excel en data/redatam/
# ─────────────────────────────────────────────────────────────────────────────

print(f"Buscando Excels en: {REDATAM_DIR}")
excel_files = [f for f in os.listdir(REDATAM_DIR) if f.lower().endswith((".xlsx", ".xls"))]
print(f"  Encontrados: {excel_files}")

if not excel_files:
    print("\nNo se encontraron archivos Excel en data/redatam/")
    print("Exporta las variables desde censos2017.inei.gob.pe/redatam/ y")
    print("guárdalos en data/redatam/ con nombres descriptivos, por ejemplo:")
    print("  agua.xlsx, luz.xlsx, saneamiento.xlsx")
    exit(0)

# ─────────────────────────────────────────────────────────────────────────────
# Cargar mapa_final.geojson
# ─────────────────────────────────────────────────────────────────────────────

with open(MAPA_IN, encoding="utf-8") as f:
    geojson = json.load(f)

nombres_mapa = [feat["properties"]["nombre"] for feat in geojson["features"]]

# ─────────────────────────────────────────────────────────────────────────────
# Configuración de variables: mapeo nombre_archivo → categorías positivas
# ─────────────────────────────────────────────────────────────────────────────

VARIABLE_CONFIG = {
    # Clave en el GeoJSON → (strings que identifican file, categorías favorables)
    "agua_pct": (
        ["agua", "water", "abastec"],
        ["Red pública dentro", "Red pública fuera", "Pilón de uso público"]
    ),
    "luz_pct": (
        ["luz", "alumbrado", "electr", "light"],
        ["Red pública de energía", "Red pública", "Electricidad"]
    ),
    "sanit_pct": (
        ["sanit", "higien", "desag", "sewer"],
        ["Red pública de desagüe dentro", "Red pública de desagüe fuera",
         "Red pública", "Desagüe"]
    ),
}

collected = {}  # var_key -> {nombre_cp_mapa: pct}

for excel_file in excel_files:
    fpath = os.path.join(REDATAM_DIR, excel_file)
    fname_lower = excel_file.lower()

    matched_var = None
    matched_cats = None
    for var_key, (keywords, cats) in VARIABLE_CONFIG.items():
        if any(kw in fname_lower for kw in keywords):
            matched_var = var_key
            matched_cats = cats
            break

    if matched_var is None:
        print(f"  [{excel_file}] No se reconoce la variable. Usa nombres como agua.xlsx, luz.xlsx, saneamiento.xlsx")
        continue

    print(f"\nProcesando [{excel_file}] → variable: {matched_var}")
    raw = parse_redatam_excel(fpath, matched_cats)
    print(f"  CPs encontrados en Excel: {len(raw)}")

    # Hacer match con nombres del mapa
    matched = {}
    unmatched = []
    for cp_name, pct in raw.items():
        nombre_mapa = match_nombres(cp_name, nombres_mapa)
        if nombre_mapa:
            matched[nombre_mapa] = round(pct, 1)
        else:
            unmatched.append(cp_name)

    print(f"  Match exitoso: {len(matched)} / {len(raw)}")
    if unmatched:
        print(f"  Sin match ({len(unmatched)}): {unmatched[:10]}")

    collected[matched_var] = matched

# ─────────────────────────────────────────────────────────────────────────────
# Actualizar GeoJSON con las nuevas variables
# ─────────────────────────────────────────────────────────────────────────────

if not collected:
    print("\nNo se procesó ninguna variable. Verifica los archivos Excel.")
    exit(1)

for feat in geojson["features"]:
    nombre = feat["properties"]["nombre"]
    for var_key, cp_dict in collected.items():
        feat["properties"][var_key] = cp_dict.get(nombre, None)

# Guardar
with open(MAPA_OUT, "w", encoding="utf-8") as f:
    json.dump(geojson, f, ensure_ascii=False, separators=(",", ":"))

print(f"\nActualizado: {MAPA_OUT}")
print("Variables añadidas:", list(collected.keys()))
print("\nCoverage por variable:")
for var_key, cp_dict in collected.items():
    n = len([v for v in cp_dict.values() if v is not None])
    print(f"  {var_key}: {n}/{len(nombres_mapa)} CPs con dato")
