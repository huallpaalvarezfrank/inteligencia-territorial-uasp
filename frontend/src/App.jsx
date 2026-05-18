import { useState, useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './App.css'

const VARIABLES = [
  { key: 'votos_chirinos', label: 'Votos Patricia Chirinos', unit: 'votos', min: 0, max: 72,
    palette: ['#fef9ec','#fde68a','#fbbf24','#f59e0b','#b45309','#78350f'] },
  { key: 'pct_chirinos',   label: '% Patricia Chirinos',    unit: '%',     min: 0, max: 0.04,
    palette: ['#fef9ec','#fde68a','#fbbf24','#f59e0b','#b45309','#78350f'] },
  { key: 'pct_rp',         label: '% Renovación Popular',   unit: '%',     min: 0, max: 50,
    palette: ['#fef9ec','#fde68a','#fbbf24','#f59e0b','#b45309','#78350f'] },
]

function getColor(value, variable) {
  if (value == null || isNaN(value)) return '#e5e7eb'
  const { min, max, palette } = variable
  const t = Math.max(0, Math.min(1, (value - min) / (max - min || 1)))
  const idx = Math.min(Math.floor(t * palette.length), palette.length - 1)
  return palette[idx]
}

export default function App() {
  const mapRef      = useRef(null)
  const layerRef    = useRef(null)
  const [geoData,   setGeoData]   = useState(null)
  const [varKey,    setVarKey]    = useState('votos_chirinos')
  const [selected,  setSelected]  = useState(null)
  const [loading,   setLoading]   = useState(true)

  const currentVar = VARIABLES.find(v => v.key === varKey)

  // Cargar GeoJSON
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}mapa_callao.geojson`)
      .then(r => r.json())
      .then(data => { setGeoData(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  // Inicializar mapa
  useEffect(() => {
    if (mapRef.current) return
    mapRef.current = L.map('map', {
      center: [-12.06, -77.12],
      zoom: 12,
      zoomControl: true,
    })
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO',
      subdomains: 'abcd',
    }).addTo(mapRef.current)
  }, [])

  // Renderizar capa coroplética
  useEffect(() => {
    if (!mapRef.current || !geoData) return
    if (layerRef.current) { layerRef.current.remove(); layerRef.current = null }

    const variable = VARIABLES.find(v => v.key === varKey)

    layerRef.current = L.geoJSON(geoData, {
      style: feature => {
        const val = feature.properties[varKey]
        return {
          fillColor: getColor(val, variable),
          fillOpacity: 0.8,
          color: '#1f2937',
          weight: 1.5,
        }
      },
      onEachFeature: (feature, layer) => {
        layer.on({
          click: () => setSelected(feature.properties),
          mouseover: e => { e.target.setStyle({ weight: 3, color: '#f9fafb' }) },
          mouseout:  e => { layerRef.current?.resetStyle(e.target) },
        })
      },
    }).addTo(mapRef.current)

    mapRef.current.fitBounds(layerRef.current.getBounds(), { padding: [20, 20] })
  }, [geoData, varKey])

  const fmt = (v, unit) => {
    if (v == null || isNaN(v)) return '—'
    if (unit === '%') return `${Number(v).toFixed(3)}%`
    return Number(v).toLocaleString('es-PE')
  }

  return (
    <>
      {/* Header */}
      <div className="header">
        <div>
          <h1>Inteligencia Territorial</h1>
          <span className="subtitle">
            Senadores DEM 2026 · Callao · Patricia Chirinos (Renovación Popular)
          </span>
        </div>
        <div style={{ fontSize: 12, color: '#94a3b8', textAlign: 'right' }}>
          7 distritos · 2,898 mesas · {geoData ? geoData.features.reduce((s,f) => s + (f.properties.votos_chirinos||0), 0) : '—'} votos
        </div>
      </div>

      {/* Controles */}
      <div className="controls">
        <div className="control-group">
          <label className="control-label">VARIABLE A VISUALIZAR</label>
          <select className="select-var" value={varKey} onChange={e => setVarKey(e.target.value)}>
            {VARIABLES.map(v => (
              <option key={v.key} value={v.key}>{v.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Mapa */}
      <div id="map" style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 0 }} />

      {loading && (
        <div style={{ position:'absolute', top:'50%', left:'50%', transform:'translate(-50%,-50%)',
                      color:'#f1f5f9', background:'#1e293b', padding:'12px 24px', borderRadius:8, zIndex:999 }}>
          Cargando datos…
        </div>
      )}

      {/* Panel lateral */}
      <div className={`side-panel ${selected ? 'open' : ''}`}>
        {selected ? (
          <>
            <div className="panel-header">
              <div className="panel-title">{selected.nombre_distrito || selected.distrito_key}</div>
              <button className="panel-close" onClick={() => setSelected(null)}>✕</button>
            </div>

            <div className="section-title">Patricia Chirinos (RP)</div>
            <div className="stat-row">
              <span>Votos preferencia</span>
              <strong>{fmt(selected.votos_chirinos, 'votos')}</strong>
            </div>
            <div className="stat-row">
              <span>% sobre total votantes</span>
              <strong>{fmt(selected.pct_chirinos, '%')}</strong>
            </div>

            <div className="section-title" style={{ marginTop: 20 }}>Renovación Popular</div>
            <div className="stat-row">
              <span>Votos lista RP</span>
              <strong>{fmt(selected.votos_rp, 'votos')}</strong>
            </div>
            <div className="stat-row">
              <span>% sobre votos válidos</span>
              <strong>{fmt(selected.pct_rp, '%')}</strong>
            </div>

            <div className="section-title" style={{ marginTop: 20 }}>Participación</div>
            <div className="stat-row">
              <span>Total votantes</span>
              <strong>{fmt(selected.total_votantes, 'votos')}</strong>
            </div>
            <div className="stat-row">
              <span>Mesas</span>
              <strong>{selected.mesas}</strong>
            </div>
          </>
        ) : (
          <div style={{ color: '#64748b', padding: 20, textAlign: 'center', marginTop: 60 }}>
            Haz clic en un distrito para ver el detalle
          </div>
        )}
      </div>

      {/* Leyenda */}
      <div className="legend">
        <div className="legend-title">{currentVar.label}</div>
        <div className="legend-gradient" style={{
          background: `linear-gradient(to right, ${currentVar.palette.join(',')})`,
        }} />
        <div className="legend-labels">
          <span>{currentVar.min}{currentVar.unit === '%' ? '%' : ''}</span>
          <span>{currentVar.max}{currentVar.unit === '%' ? '%' : ''}</span>
        </div>
      </div>
    </>
  )
}
