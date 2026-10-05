import { useEffect, useState } from 'react'
import { api } from '../api'
import { useUser } from '../auth'
import TabBar from '../components/TabBar'
import { addDays, grams, kcal, longDate, parseIsoDate, today } from '../format'
import type { DaySummary } from '../types'

const CHART_H = 170

export default function Insights() {
  const user = useUser()
  const [days, setDays] = useState<DaySummary[] | null>(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(6)
  const end = today()
  const start = addDays(end, -6)

  useEffect(() => {
    api.get<DaySummary[]>(`/api/days?start=${start}&end=${end}`).then(setDays).catch((e) => setError(e.message))
  }, [start, end])

  const target = user.targets?.energy_kcal ?? 0
  const logged = (days ?? []).filter((d) => d.entries > 0 && d.date !== end)
  const avg = (key: string) => (logged.length ? logged.reduce((s, d) => s + d.totals[key], 0) / logged.length : null)
  const max = Math.max(target * 1.25, ...(days ?? []).map((d) => d.totals.energy_kcal), 1)
  const sel = days?.[selected]
  const avgKcal = avg('energy_kcal')
  const avgProtein = avg('protein_g')
  const avgFibre = avg('fibre_g')

  return (
    <div className="screen">
      <div className="content">
        <div className="stack" style={{ gap: 2 }}>
          <span className="small muted" style={{ fontWeight: 600 }}>{longDate(start)} – {longDate(end)}</span>
          <h1 className="title">This week</h1>
        </div>
        {error && <p className="error" role="alert">{error}</p>}

        {days && (
          <div className="card pad stack" style={{ gap: 10, borderRadius: 18 }}>
            <div className="row between" style={{ alignItems: 'baseline' }}>
              <strong style={{ fontSize: 15 }}>Calories per day</strong>
              <span className="small muted num" aria-live="polite">{sel && `${longDate(sel.date)}: ${kcal(sel.totals.energy_kcal)} kcal`}</span>
            </div>
            <div style={{ position: 'relative', height: CHART_H, display: 'flex', alignItems: 'flex-end', gap: 10, borderBottom: '1px solid var(--field)' }}>
              {target > 0 && (
                <>
                  <div style={{ position: 'absolute', left: 0, right: 0, bottom: (target / max) * CHART_H, borderTop: '1.5px dashed var(--muted)' }} />
                  <span className="xsmall" style={{ position: 'absolute', right: 0, bottom: (target / max) * CHART_H + 3, fontWeight: 700, color: '#4a574f', background: 'var(--surface)', padding: '0 4px' }}>Target {kcal(target)}</span>
                </>
              )}
              {days.map((d, i) => (
                <button
                  key={d.date}
                  aria-label={`${longDate(d.date)}: ${kcal(d.totals.energy_kcal)} kcal`}
                  aria-pressed={i === selected}
                  onMouseEnter={() => setSelected(i)} onFocus={() => setSelected(i)} onClick={() => setSelected(i)}
                  style={{ flex: 1, height: '100%', border: 0, padding: 0, background: 'transparent', display: 'flex', alignItems: 'flex-end', cursor: 'pointer' }}
                >
                  <div style={{ width: '100%', height: Math.max((d.totals.energy_kcal / max) * CHART_H, d.entries ? 2 : 0), borderRadius: '4px 4px 0 0', background: 'var(--protein)', opacity: i === selected ? 1 : 0.55 }} />
                </button>
              ))}
            </div>
            <div className="row" style={{ gap: 10 }}>
              {days.map((d) => (
                <span key={d.date} className="xsmall muted" style={{ flex: 1, textAlign: 'center' }}>
                  {d.date === end ? 'Today' : parseIsoDate(d.date).toLocaleDateString('en-IN', { weekday: 'short' })}
                </span>
              ))}
            </div>
            <span className="xsmall muted">
              {avgKcal != null ? `Average ${kcal(avgKcal)} kcal on ${logged.length} logged day${logged.length > 1 ? 's' : ''} (today not counted).` : 'Log a full day to see your average.'}
            </span>
          </div>
        )}

        {user.targets && avgProtein != null && avgFibre != null && (
          <div className="grid-2">
            <div className="card pad stack" style={{ gap: 4 }}>
              <span className="xsmall muted" style={{ fontWeight: 700 }}>Avg protein</span>
              <span className="big-num" style={{ fontSize: 24 }}>{grams(avgProtein)} g</span>
              <span className="xsmall" style={{ fontWeight: 600, color: avgProtein < user.targets.protein_g * 0.8 ? 'var(--warn-ink)' : '#4a574f' }}>
                {Math.round((avgProtein / user.targets.protein_g) * 100)}% of {user.targets.protein_g} g
              </span>
            </div>
            <div className="card pad stack" style={{ gap: 4 }}>
              <span className="xsmall muted" style={{ fontWeight: 700 }}>Avg fibre</span>
              <span className="big-num" style={{ fontSize: 24 }}>{grams(avgFibre)} g</span>
              <span className="xsmall" style={{ fontWeight: 600, color: avgFibre < user.targets.fibre_g * 0.8 ? 'var(--warn-ink)' : '#4a574f' }}>
                {Math.round((avgFibre / user.targets.fibre_g) * 100)}% of {user.targets.fibre_g} g
              </span>
            </div>
          </div>
        )}

        <p className="note small"><span>Vitamin and mineral insights (iron, calcium, B12) are coming in a later phase.</span></p>
      </div>
      <TabBar />
    </div>
  )
}
