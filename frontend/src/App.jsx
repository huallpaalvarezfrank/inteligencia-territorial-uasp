import { useState, useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

// ── Diputados electos 2026 ────────────────────────────────────────────────────
const DIPUTADOS = [
  { nombre: 'Yenifer Paredes',  partido: 'JP', partido_full: 'Juntos por el Perú', votos: 1915, color: '#0284c7' },
  { nombre: 'Gabriel Gonzales', partido: 'JP', partido_full: 'Juntos por el Perú', votos: 806,  color: '#0284c7' },
  { nombre: 'Segundo Ticlla',   partido: 'FP', partido_full: 'Fuerza Popular',      votos: 113,  color: '#c2410c' },
  { nombre: 'Jessica Guevara', partido: 'JP', partido_full: 'Juntos por el Perú', votos: 88,   color: '#0284c7' },
  { nombre: 'Juan Villanueva',  partido: 'JP', partido_full: 'Juntos por el Perú', votos: 63,   color: '#0284c7' },
  { nombre: 'Luis Jibaja',      partido: 'JP', partido_full: 'Juntos por el Perú', votos: 51,   color: '#0284c7' },
]

// ── Variables coroplético ────────────────────────────────────────────────────
const DEPUTY_COLORS = {
  'Yenifer Paredes':  '#1d4ed8',
  'Gabriel Gonzales': '#0891b2',
  'Jessica Guevara':  '#7c3aed',
  'Juan Villanueva':  '#059669',
  'Luis Jibaja':      '#d97706',
  'Segundo Ticlla':   '#c2410c',
}

const VARIABLES = [
  // Electorales
  { key: 'pct_jxp',         label: '% Juntos por el Perú',   unit: '%',  min: 30,  max: 85,   palette: ['#1e3a5f','#1d6fa4','#2196d6','#5bbde8','#aadff5','#e0f4fc'] },
  { key: 'pct_fp',          label: '% Fuerza Popular',        unit: '%',  min: 4,   max: 22,   palette: ['#fff7ed','#fed7aa','#fb923c','#ea580c','#c2410c','#7c1d0a'] },
  { key: 'pct_obra',        label: '% Partido Cívico Obras',  unit: '%',  min: 0,   max: 25,   palette: ['#2e1065','#5b21b6','#7c3aed','#a78bfa','#c4b5fd','#ede9fe'] },
  { key: 'participacion',   label: 'Participación electoral',  unit: '%',  min: 30,  max: 100,  palette: ['#052e16','#14532d','#166534','#16a34a','#4ade80','#bbf7d0'] },
  // Diputados 2026
  { key: 'diputado_dom',        label: 'Diputado dominante',           type: 'categorical', colorMap: DEPUTY_COLORS },
  // Votos absolutos
  { key: 'pref_yenifer',       label: 'Yenifer Paredes — votos',      unit: 'votos', min: 0, max: 100, palette: ['#dbeafe','#93c5fd','#3b82f6','#1d4ed8','#1e3a8a','#0f1f4d'], deputy: true },
  { key: 'pref_gabriel',       label: 'Gabriel Gonzales — votos',     unit: 'votos', min: 0, max: 45,  palette: ['#cffafe','#67e8f9','#22d3ee','#0891b2','#0e7490','#083344'], deputy: true },
  { key: 'pref_jessica',       label: 'Jessica Guevara — votos',      unit: 'votos', min: 0, max: 3,   palette: ['#ede9fe','#c4b5fd','#8b5cf6','#7c3aed','#5b21b6','#2e1065'], deputy: true },
  { key: 'pref_juan',          label: 'Juan Villanueva — votos',      unit: 'votos', min: 0, max: 5,   palette: ['#d1fae5','#6ee7b7','#34d399','#059669','#065f46','#022c22'], deputy: true },
  { key: 'pref_jibaja',        label: 'Luis Jibaja — votos',          unit: 'votos', min: 0, max: 4,   palette: ['#fef3c7','#fcd34d','#f59e0b','#d97706','#92400e','#451a03'], deputy: true },
  { key: 'pref_ticlla',        label: 'Segundo Ticlla — votos',       unit: 'votos', min: 0, max: 10,  palette: ['#ffedd5','#fdba74','#fb923c','#ea580c','#9a3412','#431407'], deputy: true },
  // Porcentajes
  { key: 'pref_yenifer_pct',   label: 'Yenifer Paredes — %',          unit: '%',     min: 0, max: 22,  palette: ['#dbeafe','#93c5fd','#3b82f6','#1d4ed8','#1e3a8a','#0f1f4d'], deputy: true },
  { key: 'pref_gabriel_pct',   label: 'Gabriel Gonzales — %',         unit: '%',     min: 0, max: 12,  palette: ['#cffafe','#67e8f9','#22d3ee','#0891b2','#0e7490','#083344'], deputy: true },
  { key: 'pref_jessica_pct',   label: 'Jessica Guevara — %',          unit: '%',     min: 0, max: 2,   palette: ['#ede9fe','#c4b5fd','#8b5cf6','#7c3aed','#5b21b6','#2e1065'], deputy: true },
  { key: 'pref_juan_pct',      label: 'Juan Villanueva — %',          unit: '%',     min: 0, max: 2,   palette: ['#d1fae5','#6ee7b7','#34d399','#059669','#065f46','#022c22'], deputy: true },
  { key: 'pref_jibaja_pct',    label: 'Luis Jibaja — %',              unit: '%',     min: 0, max: 2,   palette: ['#fef3c7','#fcd34d','#f59e0b','#d97706','#92400e','#451a03'], deputy: true },
  { key: 'pref_ticlla_pct',    label: 'Segundo Ticlla — %',           unit: '%',     min: 0, max: 1,   palette: ['#ffedd5','#fdba74','#fb923c','#ea580c','#9a3412','#431407'], deputy: true },
  // Demográficas
  { key: 'poblacion',       label: 'Población (hab.)',         unit: 'hab',    min: 0,    max: 1400, palette: ['#0f172a','#1e3a6e','#2563eb','#60a5fa','#bfdbfe','#eff6ff'] },
  { key: 'densidad_hab_km2',label: 'Densidad poblacional',    unit: 'hab/km²',min: 0,    max: 200,  palette: ['#1c1200','#78350f','#d97706','#fbbf24','#fde68a','#fffbeb'] },
  { key: 'altitud',         label: 'Altitud',                  unit: 'm',      min: 1800, max: 4000, palette: ['#14290e','#1a4017','#2d6a24','#5a9e3a','#a3d977','#d9f0b0'] },
  // Servicios básicos (INEI 2017 — requiere data/redatam/)
  { key: 'agua_pct',        label: 'Acceso a agua potable',   unit: '%',  min: 0,   max: 100,  palette: ['#7f1d1d','#b91c1c','#ef4444','#60a5fa','#2563eb','#1e3a8a'], census: true },
  { key: 'luz_pct',         label: 'Alumbrado eléctrico',     unit: '%',  min: 0,   max: 100,  palette: ['#1c1a00','#78690f','#d4a017','#fbbf24','#fef08a','#fefce8'], census: true },
  { key: 'sanit_pct',       label: 'Saneamiento (red pública)',unit: '%',  min: 0,   max: 100,  palette: ['#1a0e2e','#4c1d95','#7c3aed','#a78bfa','#ddd6fe','#f5f3ff'], census: true },
]

const PARTIDOS = {
  pct_jxp: 'Juntos por el Perú', pct_fp: 'Fuerza Popular',
  pct_obra: 'Partido Cívico Obras', pct_pp: 'Podemos Perú',
  pct_an: 'Ahora Nación', pct_lp: 'Libertad Popular',
  pct_pbg: 'Perú Bienestar Grande', pct_ppt: 'PPT',
  pct_pl: 'Partido Libertario', pct_sp: 'Somos Perú',
  pct_app: 'Alianza Para el Progreso', pct_rp: 'Renovación Popular',
  pct_otros: 'Otros',
}
const PCT_COLS = Object.keys(PARTIDOS)

const CATASTRO_COLORS = {
  titulado:   { fill: '#fbbf24', stroke: '#fbbf24', fillOpacity: 0.12, weight: 2 },
  tramite:    { fill: '#fb923c', stroke: '#fb923c', fillOpacity: 0.12, weight: 2 },
  extinguido: { fill: '#94a3b8', stroke: '#94a3b8', fillOpacity: 0.08, weight: 1.5 },
  cantera:    { fill: '#c084fc', stroke: '#c084fc', fillOpacity: 0.12, weight: 2 },
  otro:       { fill: '#cbd5e1', stroke: '#cbd5e1', fillOpacity: 0.08, weight: 1.5 },
}
const ESTADO_LABEL = {
  titulado: 'Titulada', tramite: 'En trámite',
  extinguido: 'Extinguida', cantera: 'Cantera', otro: 'Otro',
}

const DISTRICTS = {
  encanada: { label: 'La Encañada', file: '/mapa_final.geojson',          cps: 110, center: [-7.05, -78.38], zoom: 11 },
  sorochuco:{ label: 'Sorochuco',   file: '/mapa_final_sorochuco.geojson', cps: 80,  center: [-6.86, -78.28], zoom: 12 },
}

// ── Utils ────────────────────────────────────────────────────────────────────
function hexToRgb(hex) {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)]
}
function interpolateColor(t, palette) {
  if (palette.length === 1) return palette[0]
  const scaled = t * (palette.length - 1)
  const i = Math.min(Math.floor(scaled), palette.length - 2)
  const f = scaled - i
  const [r1,g1,b1] = hexToRgb(palette[i])
  const [r2,g2,b2] = hexToRgb(palette[i+1])
  return `rgb(${Math.round(r1+f*(r2-r1))},${Math.round(g1+f*(g2-g1))},${Math.round(b1+f*(b2-b1))})`
}
function getColor(value, variable) {
  if (variable.type === 'categorical') {
    if (!value) return '#334155'
    return variable.colorMap[value] || '#334155'
  }
  if (value == null || isNaN(value)) return '#334155'
  const { min, max, palette } = variable
  const t = Math.min(1, Math.max(0, (value - min) / (max - min)))
  return interpolateColor(t, palette)
}
function fmt(value, unit) {
  if (value == null || isNaN(value)) return '—'
  if (unit === '%')       return `${Number(value).toFixed(1)}%`
  if (unit === 'hab')     return `${Math.round(value).toLocaleString('es-PE')} hab`
  if (unit === 'hab/km²') return `${Number(value).toFixed(1)} hab/km²`
  if (unit === 'm')       return `${Math.round(value).toLocaleString('es-PE')} m`
  if (unit === 'votos')   return `${Math.round(value).toLocaleString('es-PE')} votos`
  return String(value)
}

function CensusStat({ label, value }) {
  const pct = value != null ? Math.min(100, Math.max(0, value)) : null
  const color = pct == null ? '#475569' : pct >= 80 ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <div className="partido-row">
      <div className="partido-header">
        <span className="partido-nombre">{label}</span>
        <span className="partido-pct" style={{ color }}>{pct != null ? `${pct.toFixed(0)}%` : '—'}</span>
      </div>
      <div className="barra-bg">
        {pct != null && <div className="barra-fill" style={{ width: `${pct}%`, background: color }} />}
      </div>
    </div>
  )
}

// ── Diputados y sus claves de preferencia ────────────────────────────────────
const PREF_DEPUTIES = [
  { key: 'pref_yenifer', nombre: 'Yenifer Paredes',  color: '#1d4ed8', partido: 'JP' },
  { key: 'pref_gabriel', nombre: 'Gabriel Gonzales', color: '#0891b2', partido: 'JP' },
  { key: 'pref_jessica', nombre: 'Jessica Guevara',  color: '#7c3aed', partido: 'JP' },
  { key: 'pref_juan',    nombre: 'Juan Villanueva',  color: '#059669', partido: 'JP' },
  { key: 'pref_jibaja',  nombre: 'Luis Jibaja',      color: '#d97706', partido: 'JP' },
  { key: 'pref_ticlla',  nombre: 'Segundo Ticlla',   color: '#c2410c', partido: 'FP' },
]

// ── Panel: Diputados electos ──────────────────────────────────────────────────
function DiputadosSection() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderTop: '1px solid #334155', marginTop: 16, paddingTop: 12 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer',
          fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          padding: '2px 0',
        }}
      >
        <span>Diputados electos 2026</span>
        <span style={{ fontSize: 14, transition: 'transform 0.2s', transform: open ? 'rotate(180deg)' : 'none' }}>▾</span>
      </button>
      {open && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {DIPUTADOS.map((d, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: '#1e293b', borderRadius: 5, padding: '6px 8px',
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 4,
                background: d.color + '33', border: `1px solid ${d.color}66`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 9, fontWeight: 800, color: d.color, flexShrink: 0,
              }}>{d.partido}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, color: '#e2e8f0', fontWeight: 600, lineHeight: 1.2 }}>{d.nombre}</div>
                <div style={{ fontSize: 10, color: '#64748b', marginTop: 1 }}>{d.partido_full}</div>
              </div>
              <div style={{ fontSize: 11, color: '#475569', textAlign: 'right', flexShrink: 0 }}>
                {d.votos.toLocaleString('es-PE')}
                <div style={{ fontSize: 9, color: '#334155' }}>pref.</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const mapRef          = useRef(null)
  const cpLayerRef      = useRef(null)
  const catLayerRef     = useRef(null)
  const geoDataRef      = useRef(null)        // Encañada
  const geoDataSoroRef  = useRef(null)        // Sorochuco
  const catDataRef      = useRef(null)
  const fitBoundsRef    = useRef(false)       // flag para fitBounds al cambiar de distrito

  const [district, setDistrict]           = useState('encanada')
  const [varKey, setVarKey]               = useState('pct_jxp')
  const [showCatastro, setShowCatastro]   = useState(false)
  const [selected, setSelected]           = useState(null)
  const [selectedCat, setSelectedCat]     = useState(null)
  const [loading, setLoading]             = useState(true)

  const currentVar  = VARIABLES.find(v => v.key === varKey)
  const activeDistrict = DISTRICTS[district]
  const censusAvailable = geoDataRef.current
    ? geoDataRef.current.features.some(f => f.properties.agua_pct != null)
    : false

  // ── Inicializar mapa ───────────────────────────────────────────────────────
  useEffect(() => {
    const map = L.map('map', { center: [-7.05, -78.38], zoom: 11, zoomControl: false })
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO', subdomains: 'abcd', maxZoom: 18,
    }).addTo(map)
    mapRef.current = map

    Promise.all([
      fetch('/mapa_final.geojson').then(r => r.json()),
      fetch('/mapa_final_sorochuco.geojson').then(r => r.json()),
      fetch('/catastro_minero.geojson').then(r => r.json()),
    ]).then(([enc, soro, cat]) => {
      geoDataRef.current     = enc
      geoDataSoroRef.current = soro
      catDataRef.current     = cat
      setLoading(false)
    })

    return () => map.remove()
  }, [])

  // Cuando cambia el distrito: limpiar selección, programar fitBounds
  useEffect(() => {
    setSelected(null)
    setSelectedCat(null)
    fitBoundsRef.current = true
  }, [district])

  // ── Capa CP coroplético ────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || loading) return
    if (cpLayerRef.current) cpLayerRef.current.remove()

    const activeData = district === 'encanada' ? geoDataRef.current : geoDataSoroRef.current
    if (!activeData) return

    const variable = VARIABLES.find(v => v.key === varKey)
    const layer = L.geoJSON(activeData, {
      style: feature => ({
        fillColor:   getColor(feature.properties[varKey], variable),
        fillOpacity: 0.75,
        color:       '#0f172a',
        weight:      0.8,
      }),
      onEachFeature: (feature, fl) => {
        fl.on({
          mouseover: e => { e.target.setStyle({ fillOpacity: 0.95, weight: 2, color: '#f8fafc' }); e.target.bringToFront() },
          mouseout:  e => { layer.resetStyle(e.target) },
          click:     e => {
            setSelected(feature.properties)
            setSelectedCat(null)
            e.target.setStyle({ fillOpacity: 0.95, weight: 2, color: '#38bdf8' })
          },
        })
      },
    }).addTo(mapRef.current)

    cpLayerRef.current = layer

    if (fitBoundsRef.current) {
      mapRef.current.fitBounds(layer.getBounds(), { padding: [20, 20] })
      fitBoundsRef.current = false
    }
  }, [varKey, loading, district])

  // ── Capa catastro minero ──────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !catDataRef.current) return
    if (catLayerRef.current) { catLayerRef.current.remove(); catLayerRef.current = null }
    if (!showCatastro) return

    // Filtrar solo las concesiones del distrito activo
    const filtered = {
      ...catDataRef.current,
      features: catDataRef.current.features.filter(
        f => f.properties.distrito_id === district
      ),
    }

    const layer = L.geoJSON(filtered, {
      style: feature => {
        const cat = feature.properties.estado_cat || 'otro'
        const { fill, stroke, fillOpacity, weight } = CATASTRO_COLORS[cat] || CATASTRO_COLORS.otro
        return { fillColor: fill, fillOpacity, color: stroke, weight,
                 dashArray: cat === 'tramite' ? '6 4' : null, opacity: 0.9 }
      },
      onEachFeature: (feature, fl) => {
        fl.on({
          mouseover: e => { e.target.setStyle({ fillOpacity: 0.28, weight: 3 }); e.target.bringToFront() },
          mouseout:  e => { layer.resetStyle(e.target) },
          click:     e => { setSelectedCat(feature.properties); setSelected(null); L.DomEvent.stopPropagation(e) },
        })
      },
    })
    layer.addTo(mapRef.current)
    catLayerRef.current = layer
  }, [showCatastro, loading, district])

  // ── Partidos ordenados para el panel ──────────────────────────────────────
  const sortedPartidos = selected
    ? Object.entries(PARTIDOS)
        .map(([k, nombre]) => ({ key: k, nombre, pct: selected[k] ?? 0 }))
        .filter(p => p.pct > 0)
        .sort((a, b) => b.pct - a.pct)
    : []
  const coloresPartido = {
    pct_jxp: '#0284c7', pct_fp: '#c2410c', pct_obra: '#7c3aed',
    pct_pp: '#0891b2', pct_an: '#dc2626',
  }

  // ── Panel lateral ─────────────────────────────────────────────────────────
  const renderPanel = () => {
    if (selectedCat) {
      const p = selectedCat
      const cat = p.estado_cat || 'otro'
      const { fill } = CATASTRO_COLORS[cat] || CATASTRO_COLORS.otro
      return (
        <div className="panel-content">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ width: 12, height: 12, borderRadius: 2, background: fill, flexShrink: 0, display: 'inline-block' }} />
            <div className="panel-nombre" style={{ fontSize: 14 }}>{p.concesion || '(sin nombre)'}</div>
          </div>
          <span className="panel-categoria" style={{ background: fill+'33', color: fill }}>{ESTADO_LABEL[cat] || cat}</span>

          <div className="section-title">Datos de la concesión</div>
          <div className="stat-row"><span className="stat-label">Código</span><span className="stat-value" style={{ fontFamily:'monospace', fontSize:12 }}>{p.codigo||'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Titular</span><span className="stat-value" style={{ fontSize:11, textAlign:'right', maxWidth:170 }}>{p.titular||'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Sustancia</span><span className="stat-value">{p.sustancia_txt||p.sustancia||'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Estado</span><span className="stat-value" style={{ fontSize:11, textAlign:'right', maxWidth:170 }}>{p.estado||'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Fecha denuncia</span><span className="stat-value">{p.fecha_denuncia?String(p.fecha_denuncia).slice(0,10):'—'}</span></div>

          <div className="section-title" style={{ marginTop: 20 }} />
          <button onClick={() => setSelectedCat(null)} style={{
            marginTop: 8, width: '100%', padding: '6px 0',
            background: '#334155', color: '#94a3b8', border: 'none',
            borderRadius: 4, cursor: 'pointer', fontSize: 12,
          }}>Volver a centros poblados</button>

          <DiputadosSection />
        </div>
      )
    }

    if (selected) {
      return (
        <div className="panel-content">
          <div className="panel-nombre">{selected.nombre || '(sin nombre)'}</div>
          <span className="panel-categoria">{selected.categoria || 'N/D'}</span>

          <div className="section-title">Geografía</div>
          <div className="stat-row"><span className="stat-label">Altitud</span><span className="stat-value">{fmt(selected.altitud,'m')}</span></div>
          <div className="stat-row"><span className="stat-label">Área</span><span className="stat-value">{selected.area_km2?`${selected.area_km2} km²`:'—'}</span></div>

          <div className="section-title">Censo 2017</div>
          <div className="stat-row"><span className="stat-label">Población</span><span className="stat-value highlight">{fmt(selected.poblacion,'hab')}</span></div>
          <div className="stat-row"><span className="stat-label">Densidad</span><span className="stat-value">{fmt(selected.densidad_hab_km2,'hab/km²')}</span></div>

          {censusAvailable && (
            <>
              <div className="section-title">Servicios básicos</div>
              <CensusStat label="Agua potable"         value={selected.agua_pct} />
              <CensusStat label="Alumbrado eléctrico"  value={selected.luz_pct} />
              <CensusStat label="Saneamiento"          value={selected.sanit_pct} />
            </>
          )}

          <div className="section-title">Elecciones 2026</div>
          <div className="stat-row"><span className="stat-label">Local de votación</span><span className="stat-value" style={{ fontSize:11, textAlign:'right', maxWidth:160 }}>{selected.local_votacion||'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Electores hábiles</span><span className="stat-value">{selected.electores_hab?selected.electores_hab.toLocaleString('es-PE'):'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Total votantes</span><span className="stat-value">{selected.total_votantes?selected.total_votantes.toLocaleString('es-PE'):'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Participación</span><span className="stat-value highlight">{fmt(selected.participacion,'%')}</span></div>
          <div className="stat-row"><span className="stat-label">Ausentismo</span><span className="stat-value">{fmt(selected.ausentismo,'%')}</span></div>
          <div className="stat-row"><span className="stat-label">Ganador</span><span className="stat-value" style={{ color:'#4ade80', maxWidth:160, textAlign:'right', fontSize:12 }}>{selected.partido_ganador||'—'}</span></div>
          <div className="stat-row"><span className="stat-label">Margen victoria</span><span className="stat-value">{fmt(selected.margen_victoria,'%')}</span></div>

          <div className="section-title">Votos por partido</div>
          {sortedPartidos.map(p => (
            <div key={p.key} className="partido-row">
              <div className="partido-header">
                <span className="partido-nombre">{p.nombre}</span>
                <span className="partido-pct">{p.pct.toFixed(1)}%</span>
              </div>
              <div className="barra-bg">
                <div className="barra-fill" style={{ width:`${Math.min(100,p.pct)}%`, background: coloresPartido[p.key]||'#475569' }} />
              </div>
            </div>
          ))}

          {/* Preferencias por diputado */}
          {PREF_DEPUTIES.some(d => selected[d.key] > 0) && (() => {
            const maxPref = Math.max(...PREF_DEPUTIES.map(d => selected[d.key] || 0), 0.1)
            return (
              <>
                <div className="section-title">Preferencias por diputado</div>
                <div style={{ fontSize: 10, color: '#475569', marginBottom: 6, marginTop: -4 }}>
                  votos de preferencia en este local de votación
                </div>
                {PREF_DEPUTIES.map(d => {
                  const val = selected[d.key] || 0
                  const barW = (val / maxPref * 100).toFixed(1)
                  return (
                    <div key={d.key} className="partido-row">
                      <div className="partido-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                          <span style={{
                            fontSize: 9, fontWeight: 700, color: d.color,
                            background: d.color + '22', border: `1px solid ${d.color}55`,
                            borderRadius: 3, padding: '1px 4px', flexShrink: 0,
                          }}>{d.partido}</span>
                          <span className="partido-nombre">{d.nombre}</span>
                        </div>
                        <span className="partido-pct" style={{ color: d.color }}>
                          {val.toLocaleString('es-PE')}
                          <span style={{ color: '#475569', fontWeight: 400, fontSize: 10, marginLeft: 3 }}>
                            ({(selected[d.key + '_pct'] || 0).toFixed(1)}%)
                          </span>
                        </span>
                      </div>
                      <div className="barra-bg">
                        <div className="barra-fill" style={{ width: `${barW}%`, background: d.color }} />
                      </div>
                    </div>
                  )
                })}
              </>
            )
          })()}

          <DiputadosSection />
        </div>
      )
    }

    return (
      <div className="panel-empty">
        <span className="icon">🗺</span>
        <p>Haz click en un centro poblado {showCatastro?'o concesión minera':''} para ver sus datos</p>
        <DiputadosSection />
      </div>
    )
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <div className="header">
        <div>
          <h1>Inteligencia Territorial · UASP</h1>
          <span className="subtitle">
            Elecciones 2026 · Cajamarca ·{' '}
            {district === 'encanada'
              ? '110 centros poblados · La Encañada'
              : '80 centros poblados · Sorochuco (Celendín)'}
          </span>
        </div>
        <div className="header-spacer" />
        <span style={{ fontSize: 12, color: '#475569' }}>Datos: ONPE 2026 · INEI CCPP · GEOCATMIN 2024</span>
      </div>

      <div className="layout">
        <div className="map-container">
          <div id="map" />

          {/* Controles */}
          <div className="variable-control">
            {/* Selector de distrito */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              {Object.entries(DISTRICTS).map(([key, d]) => (
                <button
                  key={key}
                  onClick={() => setDistrict(key)}
                  style={{
                    flex: 1, padding: '6px 4px', borderRadius: 5, fontSize: 11, fontWeight: 700,
                    cursor: 'pointer', transition: 'all 0.15s',
                    border: district === key ? '1px solid #38bdf8' : '1px solid #334155',
                    background: district === key ? '#38bdf822' : 'transparent',
                    color: district === key ? '#38bdf8' : '#64748b',
                  }}
                >
                  {d.label}
                </button>
              ))}
            </div>

            <label>Variable a visualizar</label>
            <select value={varKey} onChange={e => setVarKey(e.target.value)}>
              <optgroup label="Electorales">
                {VARIABLES.filter(v => !v.census && !v.deputy && v.type !== 'categorical' && !['poblacion','densidad_hab_km2','altitud'].includes(v.key)).map(v => (
                  <option key={v.key} value={v.key}>{v.label}</option>
                ))}
              </optgroup>
              <optgroup label="Diputados 2026 — preferencias">
                {VARIABLES.filter(v => v.type === 'categorical' || v.deputy).map(v => (
                  <option key={v.key} value={v.key}>{v.label}</option>
                ))}
              </optgroup>
              <optgroup label="Demográficas">
                {VARIABLES.filter(v => ['poblacion','densidad_hab_km2','altitud'].includes(v.key)).map(v => (
                  <option key={v.key} value={v.key}>{v.label}</option>
                ))}
              </optgroup>
              <optgroup label={censusAvailable ? 'Servicios básicos (INEI 2017)' : 'Servicios básicos — sin datos aún'}>
                {VARIABLES.filter(v => v.census).map(v => (
                  <option key={v.key} value={v.key} disabled={!censusAvailable}>
                    {v.label}{!censusAvailable?' (pendiente)':''}
                  </option>
                ))}
              </optgroup>
            </select>

            {/* Toggle catastro minero — ambos distritos */}
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid #334155' }}>
              <button
                onClick={() => setShowCatastro(s => !s)}
                style={{
                  width: '100%', padding: '7px 10px', borderRadius: 5,
                  border: `1px solid ${showCatastro ? '#f59e0b' : '#475569'}`,
                  background: showCatastro ? '#f59e0b22' : 'transparent',
                  color: showCatastro ? '#fbbf24' : '#94a3b8',
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 7, transition: 'all 0.15s',
                }}
              >
                <span style={{
                  width: 10, height: 10, borderRadius: 2,
                  background: showCatastro ? '#f59e0b' : '#475569',
                  flexShrink: 0, display: 'inline-block', transition: 'background 0.15s',
                }} />
                Catastro minero
                <span style={{ marginLeft: 'auto', fontSize: 10, opacity: 0.7 }}>
                  {showCatastro ? 'ON' : 'OFF'}
                </span>
              </button>

              {showCatastro && (
                <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {Object.entries(CATASTRO_COLORS).map(([k, { fill }]) => (
                    <div key={k} style={{ display:'flex', alignItems:'center', gap:6, fontSize:11, color:'#cbd5e1' }}>
                      <span style={{ width:10, height:10, borderRadius:2, background:fill, flexShrink:0 }} />
                      {ESTADO_LABEL[k]}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Leyenda */}
          {!loading && (
            <div className="legend">
              <div className="legend-title">{currentVar.label}</div>
              {currentVar.type === 'categorical' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 4 }}>
                  {Object.entries(currentVar.colorMap).map(([name, color]) => (
                    <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ width: 12, height: 12, borderRadius: 2, background: color, flexShrink: 0 }} />
                      <span style={{ fontSize: 11, color: '#cbd5e1' }}>{name}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <>
                  <div className="legend-gradient" style={{ background:`linear-gradient(to right, ${currentVar.palette.join(', ')})` }} />
                  <div className="legend-labels">
                    <span>{fmt(currentVar.min, currentVar.unit)}</span>
                    <span>{fmt(currentVar.max, currentVar.unit)}</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Panel lateral */}
        <div className="side-panel">
          {renderPanel()}
        </div>
      </div>
    </>
  )
}
