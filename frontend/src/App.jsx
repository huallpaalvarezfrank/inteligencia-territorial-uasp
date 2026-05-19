import { useState, useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

// Nombres legibles por distrito (campo en GeoJSON tiene problemas de encoding con Ñ)
function distLabel(raw) {
  if (!raw) return '—'
  const u = raw.toUpperCase()
  if (u === 'AZANGARO') return 'Azángaro'
  if (u.startsWith('NU') && u.includes('OA')) return 'Ñuñoa'
  if (u === 'ORURILLO') return 'Orurillo'
  if (u === 'SAN ANTON') return 'San Antón'
  if (u === 'ANTAUTA') return 'Antauta'
  if (u === 'AJOYANI') return 'Ajoyani'
  return raw
}

const VARIABLES = [
  // ── Presidencial ─────────────────────────────────────────────────────────────
  {
    group: 'Presidencial',
    key: 'pct_jxp_p', label: '% JxP — Presidencial', unit: '%', min: 20, max: 45,
    palette: ['#dcfce7','#86efac','#4ade80','#16a34a','#15803d','#14532d'],
  },
  {
    group: 'Presidencial',
    key: 'pct_obras_', label: '% Obras — Presidencial', unit: '%', min: 10, max: 32,
    palette: ['#dbeafe','#93c5fd','#60a5fa','#2563eb','#1d4ed8','#1e3a8a'],
  },
  {
    group: 'Presidencial',
    key: 'pct_rp_p', label: '% Renovación Popular — Presidencial', unit: '%', min: 0, max: 2,
    palette: ['#ffedd5','#fed7aa','#fb923c','#ea580c','#c2410c','#7c2d12'],
  },
  {
    group: 'Presidencial',
    key: 'particip', label: '% Participación', unit: '%', min: 70, max: 96,
    palette: ['#f3e8ff','#d8b4fe','#a855f7','#7e22ce','#6b21a8','#3b0764'],
  },
  // ── Diputados lista ──────────────────────────────────────────────────────────
  {
    group: 'Diputados lista',
    key: 'pct_jxp_di', label: '% JxP — Lista Diputados', unit: '%', min: 24, max: 45,
    palette: ['#dcfce7','#86efac','#4ade80','#16a34a','#15803d','#14532d'],
  },
  // ── Candidatos JxP ───────────────────────────────────────────────────────────
  {
    group: 'Preferencias JxP',
    key: 'pct_jess', label: '% Jessica Perez (#2 JxP)', unit: '%', min: 1, max: 7,
    palette: ['#dcfce7','#86efac','#4ade80','#16a34a','#15803d','#14532d'],
  },
  {
    group: 'Preferencias JxP',
    key: 'pct_tito', label: '% Cesar Tito (#3 JxP)', unit: '%', min: 1, max: 7,
    palette: ['#dcfce7','#86efac','#4ade80','#16a34a','#15803d','#14532d'],
  },
  {
    group: 'Preferencias JxP',
    key: 'pct_cond', label: '% Remigio Condori (#1 JxP)', unit: '%', min: 1, max: 7,
    palette: ['#dcfce7','#86efac','#4ade80','#16a34a','#15803d','#14532d'],
  },
  // ── Otros candidatos ─────────────────────────────────────────────────────────
  {
    group: 'Otros candidatos',
    key: 'pct_hanc', label: '% Dina Hancco (#1 Obras)', unit: '%', min: 0, max: 5,
    palette: ['#dbeafe','#93c5fd','#60a5fa','#2563eb','#1d4ed8','#1e3a8a'],
  },
  {
    group: 'Otros candidatos',
    key: 'pct_sonco', label: '% Helard Sonco (#1 AN)', unit: '%', min: 0, max: 2,
    palette: ['#fff1f2','#fecdd3','#fb7185','#f43f5e','#be123c','#881337'],
  },
]

function getColor(value, variable) {
  if (value == null || isNaN(value) || value === 0) return '#1e293b'
  const { min, max, palette } = variable
  const t = Math.max(0, Math.min(1, (value - min) / (max - min || 1)))
  const idx = Math.min(Math.floor(t * palette.length), palette.length - 1)
  return palette[idx]
}

function fmt(v, unit) {
  if (v == null || v === '' || (typeof v === 'number' && isNaN(v))) return '—'
  if (unit === '%') return `${Number(v).toFixed(1)}%`
  return Number(v).toLocaleString('es-PE')
}

const DISTRITOS = [
  { value: 'Todos',     label: 'Todos los distritos' },
  { value: 'AZANGARO',  label: 'Azángaro' },
  { value: 'NUNOA',     label: 'Ñuñoa' },
  { value: 'ORURILLO',  label: 'Orurillo' },
  { value: 'SAN ANTON', label: 'San Antón' },
  { value: 'ANTAUTA',   label: 'Antauta' },
  { value: 'AJOYANI',   label: 'Ajoyani' },
]

function matchDist(raw, filter) {
  if (!raw) return false
  const u = raw.toUpperCase().trim()
  if (filter === 'NUNOA') return u.startsWith('NU') && u.includes('OA')
  return u === filter
}

function filterFeatures(geoData, distFilter) {
  if (distFilter === 'Todos') return geoData
  return {
    ...geoData,
    features: geoData.features.filter(f =>
      matchDist(f.properties.distrito, distFilter)
    ),
  }
}

export default function App() {
  const mapRef       = useRef(null)
  const layerRef     = useRef(null)
  const distLayerRef = useRef(null)

  const [geoData,    setGeoData]    = useState(null)
  const [distData,   setDistData]   = useState(null)
  const [varKey,     setVarKey]     = useState('pct_jxp_p')
  const [selected,   setSelected]   = useState(null)
  const [distFilter, setDistFilter] = useState('Todos')
  const [showDist,   setShowDist]   = useState(true)
  const [loading,    setLoading]    = useState(true)

  const currentVar = VARIABLES.find(v => v.key === varKey)

  // Cargar GeoJSONs
  useEffect(() => {
    const base = import.meta.env.BASE_URL
    Promise.all([
      fetch(`${base}mapa_puno.geojson`).then(r => r.json()),
      fetch(`${base}distritos_puno.geojson`).then(r => r.json()),
    ]).then(([cp, dist]) => {
      setGeoData(cp)
      setDistData(dist)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  // Inicializar mapa (una vez)
  useEffect(() => {
    if (mapRef.current) return
    mapRef.current = L.map('map', {
      center: [-14.9, -70.2],
      zoom: 9,
      zoomControl: false,
    })
    L.control.zoom({ position: 'topright' }).addTo(mapRef.current)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO',
      subdomains: 'abcd',
    }).addTo(mapRef.current)
  }, [])

  // Capa de límites de distritos (toggle)
  useEffect(() => {
    if (!mapRef.current || !distData) return
    if (distLayerRef.current) { distLayerRef.current.remove(); distLayerRef.current = null }
    if (!showDist) return

    distLayerRef.current = L.geoJSON(distData, {
      style: {
        color: '#f59e0b',
        weight: 2.5,
        fillOpacity: 0,
        dashArray: '8 5',
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties
        const nombre = distLabel(p.distrito || p.NAME_3 || '')
        layer.bindTooltip(nombre, {
          permanent: false,
          direction: 'auto',
          className: 'dist-label-tt',
        })
      },
    }).addTo(mapRef.current)
  }, [distData, showDist])

  // Capa coroplética de CPs
  useEffect(() => {
    if (!mapRef.current || !geoData) return
    if (layerRef.current) { layerRef.current.remove(); layerRef.current = null }

    const variable = VARIABLES.find(v => v.key === varKey)
    const filtered = filterFeatures(geoData, distFilter)

    layerRef.current = L.geoJSON(filtered, {
      style: feature => ({
        fillColor: getColor(feature.properties[varKey], variable),
        fillOpacity: 0.82,
        color: '#0f172a',
        weight: 0.5,
      }),
      onEachFeature: (feature, layer) => {
        layer.on({
          click: () => setSelected(feature.properties),
          mouseover: e => e.target.setStyle({ weight: 2, color: '#e2e8f0', fillOpacity: 0.95 }),
          mouseout:  e => layerRef.current?.resetStyle(e.target),
        })
      },
    }).addTo(mapRef.current)

    if (layerRef.current.getLayers().length > 0) {
      mapRef.current.fitBounds(layerRef.current.getBounds(), { padding: [20, 20] })
    }
  }, [geoData, varKey, distFilter])

  const nCPs = geoData
    ? filterFeatures(geoData, distFilter).features.length
    : '—'

  // Agrupar variables por grupo para el select
  const groups = [...new Set(VARIABLES.map(v => v.group))]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0f172a' }}>

      {/* Header */}
      <div className="header">
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc', margin: 0 }}>
            Inteligencia Territorial — Puno
          </h1>
          <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
            Diputados &amp; Presidencial 2026 · 6 distritos prioritarios
          </div>
        </div>
        <div style={{ fontSize: 12, color: '#64748b', textAlign: 'right' }}>
          {nCPs} centros poblados
        </div>
      </div>

      {/* Cuerpo */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>

        <div id="map" style={{ width: '100%', height: '100%' }} />

        {/* Panel de controles (top-left) */}
        <div className="variable-control" style={{ width: 250, display: 'flex', flexDirection: 'column', gap: 10 }}>

          <div>
            <label style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 6 }}>
              Variable
            </label>
            <select
              value={varKey}
              onChange={e => { setVarKey(e.target.value); setSelected(null) }}
              style={{ width: '100%', background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569', borderRadius: 4, padding: '6px 8px', fontSize: 12, cursor: 'pointer', outline: 'none' }}
            >
              {groups.map(g => (
                <optgroup key={g} label={g}>
                  {VARIABLES.filter(v => v.group === g).map(v => (
                    <option key={v.key} value={v.key}>{v.label}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'block', marginBottom: 6 }}>
              Distrito
            </label>
            <select
              value={distFilter}
              onChange={e => { setDistFilter(e.target.value); setSelected(null) }}
              style={{ width: '100%', background: '#0f172a', color: '#e2e8f0', border: '1px solid #475569', borderRadius: 4, padding: '6px 8px', fontSize: 12, cursor: 'pointer', outline: 'none' }}
            >
              {DISTRITOS.map(d => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 12, color: '#cbd5e1', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={showDist}
              onChange={e => setShowDist(e.target.checked)}
              style={{ cursor: 'pointer', accentColor: '#f59e0b' }}
            />
            Límites de distritos
          </label>

        </div>

        {/* Leyenda */}
        <div className="legend">
          <div className="legend-title">{currentVar.label}</div>
          <div className="legend-gradient" style={{
            background: `linear-gradient(to right, ${currentVar.palette.join(',')})`,
          }} />
          <div className="legend-labels">
            <span>{currentVar.min}%</span>
            <span>{currentVar.max}%</span>
          </div>
        </div>

        {/* Spinner */}
        {loading && (
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%,-50%)',
            background: '#1e293b', color: '#e2e8f0',
            padding: '12px 24px', borderRadius: 8, zIndex: 9999, fontSize: 13,
          }}>
            Cargando datos…
          </div>
        )}

        {/* Panel lateral */}
        {selected && (
          <div style={{
            position: 'absolute', top: 0, right: 0, bottom: 0, width: 300,
            background: '#1e293b', borderLeft: '1px solid #334155',
            overflowY: 'auto', zIndex: 900, padding: 20,
          }}>
            <button
              onClick={() => setSelected(null)}
              style={{ position: 'absolute', top: 12, right: 12, background: 'none', border: 'none', color: '#94a3b8', fontSize: 18, cursor: 'pointer' }}
            >✕</button>

            <div style={{ fontSize: 15, fontWeight: 700, color: '#f8fafc', lineHeight: 1.3, paddingRight: 28 }}>
              {selected.nombre}
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
              {distLabel(selected.distrito)}
            </div>
            <div style={{ display: 'inline-block', fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', padding: '2px 8px', borderRadius: 99, background: '#334155', color: '#94a3b8', marginTop: 6, marginBottom: 16 }}>
              {selected.categ}
            </div>

            <div className="section-title">Centro Poblado</div>
            <div className="stat-row">
              <span className="stat-label">Población</span>
              <span className="stat-value">{fmt(selected.poblacion, 'n')} hab.</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Altitud</span>
              <span className="stat-value">{fmt(selected.altitud, 'n')} msnm</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Área</span>
              <span className="stat-value">{fmt(selected.area_km2, 'n')} km²</span>
            </div>

            <div className="section-title" style={{ marginTop: 12 }}>Local de votación</div>
            <div style={{ fontSize: 12, color: '#cbd5e1', lineHeight: 1.4, marginBottom: 8 }}>
              {selected.local_vot || '—'}
            </div>
            <div className="stat-row">
              <span className="stat-label">Distancia al local</span>
              <span className="stat-value">
                {selected.dist_m ? `${(selected.dist_m / 1000).toFixed(1)} km` : '—'}
              </span>
            </div>

            <div className="section-title" style={{ marginTop: 12 }}>Participación</div>
            <div className="stat-row">
              <span className="stat-label">Electores</span>
              <span className="stat-value">{fmt(selected.electores, 'n')}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Votantes</span>
              <span className="stat-value">{fmt(selected.tot_vot, 'n')}</span>
            </div>
            <div className="stat-row">
              <span className="stat-label">Participación</span>
              <span className="stat-value">{fmt(selected.particip, '%')}</span>
            </div>

            <div className="section-title" style={{ marginTop: 12 }}>Presidencial</div>
            {[
              { label: 'JxP',    key: 'pct_jxp_p',  color: '#4ade80' },
              { label: 'Obras',  key: 'pct_obras_',  color: '#60a5fa' },
              { label: 'RP',     key: 'pct_rp_p',    color: '#fb923c' },
            ].map(({ label, key, color }) => (
              <div key={key} className="partido-row">
                <div className="partido-header">
                  <span className="partido-nombre">{label}</span>
                  <span className="partido-pct" style={{ color }}>{fmt(selected[key], '%')}</span>
                </div>
                <div className="barra-bg">
                  <div className="barra-fill" style={{
                    width: `${Math.min(100, (selected[key] || 0) / 50 * 100)}%`,
                    background: color,
                  }} />
                </div>
              </div>
            ))}

            <div className="section-title" style={{ marginTop: 12 }}>Diputados — Lista JxP</div>
            <div className="stat-row">
              <span className="stat-label">% JxP</span>
              <span className="stat-value" style={{ color: '#4ade80' }}>{fmt(selected.pct_jxp_di, '%')}</span>
            </div>

            <div className="section-title" style={{ marginTop: 12 }}>Preferencias Diputados</div>
            {[
              { label: 'Jessica Perez (#2 JxP)',  pct: 'pct_jess',  pref: 'pref_jess',  color: '#4ade80' },
              { label: 'Cesar Tito (#3 JxP)',      pct: 'pct_tito',  pref: 'pref_tito',  color: '#86efac' },
              { label: 'Remigio Condori (#1 JxP)', pct: 'pct_cond',  pref: 'pref_cond',  color: '#a7f3d0' },
              { label: 'Dina Hancco (#1 Obras)',   pct: 'pct_hanc',  pref: 'pref_hanc',  color: '#60a5fa' },
              { label: 'Helard Sonco (#1 AN)',     pct: 'pct_sonco', pref: 'pref_sonco', color: '#fb7185' },
            ].map(({ label, pct, pref, color }) => (
              <div key={pct} className="stat-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 2 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                  <span className="stat-label" style={{ fontSize: 11 }}>{label}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color }}>
                    {fmt(selected[pct], '%')}
                    <span style={{ color: '#475569', fontWeight: 400 }}> ({fmt(selected[pref], 'n')})</span>
                  </span>
                </div>
                <div className="barra-bg" style={{ width: '100%' }}>
                  <div className="barra-fill" style={{
                    width: `${Math.min(100, (selected[pct] || 0) / 8 * 100)}%`,
                    background: color,
                  }} />
                </div>
              </div>
            ))}

          </div>
        )}
      </div>
    </div>
  )
}
