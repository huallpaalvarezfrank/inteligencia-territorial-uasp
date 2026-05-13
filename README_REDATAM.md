# Exportar variables censales desde REDATAM (INEI 2017)

El servidor censos2017.inei.gob.pe no es accesible desde scripts Python, pero sí desde el navegador. Sigue estos pasos para exportar los datos de agua, electricidad y saneamiento por Centro Poblado.

---

## Paso 1 — Abrir REDATAM

Abre en tu navegador:  
**http://censos2017.inei.gob.pe/redatam/**

---

## Paso 2 — Para CADA variable, repetir el proceso:

### 2a. Seleccionar área geográfica (filtro)

1. En el menú izquierdo, clic en **"Área Geográfica"** (o "Selección de Área")
2. Selecciona: `Departamento = CAJAMARCA`
3. Luego: `Provincia = CAJAMARCA`
4. Luego: `Distrito = LA ENCAÑADA`
5. Confirma la selección.

### 2b. Seleccionar nivel de desagregación

En el panel donde dice **"Unidad de análisis"** o **"Nivel geográfico"**:
- Selecciona **`CENTRO POBLADO`** (no Manzana, no Distrito)

### 2c. Crear la tabla (frecuencia simple)

1. Clic en **"Frecuencias"** o **"Nueva Consulta"**
2. En el árbol de variables, selecciona la variable (ver detalle abajo)
3. Arrastra/agrega como variable de **fila**
4. En el área geográfica ya debería estar "La Encañada / Centro Poblado"
5. Clic **"Procesar"** o **"Calcular"**

---

## Variables a exportar (3 consultas separadas)

### Variable 1 — Agua potable
- Nombre en REDATAM: **`V104 – Abastecimiento de agua`**  
  (busca "agua" o "abastecimiento" en el árbol de Vivienda)
- Archivo a guardar: `data/redatam/agua.xlsx`
- Categorías que nos interesan (son "positivas"):
  - "Red pública dentro de la vivienda"
  - "Red pública fuera de la vivienda, pero dentro del edificio"

### Variable 2 — Alumbrado eléctrico
- Nombre en REDATAM: **`V112 – Alumbrado eléctrico`**  
  (busca "alumbrado" o "electricidad" en el árbol de Vivienda)
- Archivo a guardar: `data/redatam/luz.xlsx`
- Categorías positivas:
  - "Red pública de energía eléctrica"

### Variable 3 — Servicio higiénico (saneamiento)
- Nombre en REDATAM: **`V108 – Servicio higiénico`**  
  (busca "higiénico" o "desagüe" en el árbol de Vivienda)
- Archivo a guardar: `data/redatam/saneamiento.xlsx`
- Categorías positivas:
  - "Red pública de desagüe dentro de la vivienda"
  - "Red pública de desagüe fuera de la vivienda, pero dentro del edificio"

---

## Paso 3 — Exportar a Excel

Una vez que aparezca la tabla de resultados:
1. Busca el botón **"Exportar"** o el ícono de Excel
2. Elige formato **Excel (.xlsx)**
3. Guarda el archivo en:
   ```
   InteligenciaTerritorial/data/redatam/agua.xlsx      ← para agua
   InteligenciaTerritorial/data/redatam/luz.xlsx       ← para luz
   InteligenciaTerritorial/data/redatam/saneamiento.xlsx ← para saneamiento
   ```

---

## Paso 4 — Ejecutar el script de procesamiento

Con los 3 archivos guardados en `data/redatam/`, ejecuta:

```bash
cd InteligenciaTerritorial
python scripts/fase5_censos_redatam.py
```

El script:
- Parsea cada Excel (formato REDATAM)
- Calcula el % de viviendas en la(s) categoría(s) positiva(s)
- Hace join con `mapa_final.geojson` por nombre del CP
- Agrega los campos `agua_pct`, `luz_pct`, `sanit_pct` al GeoJSON

---

## Paso 5 — El mapa se actualiza automáticamente

El frontend ya carga el `mapa_final.geojson` actualizado. Solo necesitas recargar la página.

> **Nota:** Si el portal REDATAM no responde o muestra error, prueba en otro horario. Los servidores del INEI suelen estar más disponibles en la mañana (7am–10am hora Perú).
