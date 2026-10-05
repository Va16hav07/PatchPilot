import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useUser } from '../auth'
import { SourceTag } from '../components/FoodPicker'
import Icon from '../components/Icon'
import TabBar from '../components/TabBar'
import { addDays, grams, kcal, longDate, parseIsoDate, today } from '../format'
import type { DaySummary, Insights as InsightsData, LimitAvg, MicroAvg, NutrientAvg } from '../types'

const CHART_H = 160
const RANGES = [7, 30] as const
type Range = (typeof RANGES)[number]

const STATUS = {
  good: { label: 'Good', color: 'var(--protein)', icon: '✓' },
  borderline: { label: 'A bit low', color: 'var(--warn)', icon: '!' },
  low: { label: 'Likely low', color: 'var(--danger)', icon: '!' },
} as const

const MACRO_COLOR: Record<string, string> = {
  protein_g: 'var(--protein)', carb_g: 'var(--carb)', fat_g: 'var(--fat)', fibre_g: 'var(--fibre)',
}

function amount(n: number, unit: string) {
  return `${unit === 'kcal' ? kcal(n) : grams(n)} ${unit}`
}

function CaloriesChart({ days, target }: { days: DaySummary[]; target: number }) {
  const [selected, setSelected] = useState(days.length - 1)
  const max = Math.max(target * 1.25, ...days.map((d) => d.totals.energy_kcal), 1)
  const sel = days[selected]
  const dense = days.length > 10
  return (
    <div className="card pad stack" style={{ gap: 10, borderRadius: 18 }}>
      <div className="row between" style={{ alignItems: 'baseline' }}>
        <strong style={{ fontSize: 15 }}>Calories per day</strong>
        <span className="small muted num" aria-live="polite">{sel && `${longDate(sel.date)}: ${kcal(sel.totals.energy_kcal)} kcal`}</span>
      </div>
      <div style={{ position: 'relative', height: CHART_H, display: 'flex', alignItems: 'flex-end', gap: dense ? 3 : 10, borderBottom: '1px solid var(--field)' }}>
        {target > 0 && (
          <>
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: (target / max) * CHART_H, borderTop: '1.5px dashed var(--muted)' }} />
            <span className="xsmall" style={{ position: 'absolute', right: 0, bottom: (target / max) * CHART_H + 3, fontWeight: 700, color: 'var(--ink-3)', background: 'var(--surface)', padding: '0 4px' }}>Target {kcal(target)}</span>
          </>
        )}
        {days.map((d, i) => (
          <button key={d.date} aria-label={`${longDate(d.date)}: ${kcal(d.totals.energy_kcal)} kcal`} aria-pressed={i === selected}
            onMouseEnter={() => setSelected(i)} onFocus={() => setSelected(i)} onClick={() => setSelected(i)}
            style={{ flex: 1, height: '100%', border: 0, padding: 0, background: 'transparent', display: 'flex', alignItems: 'flex-end', cursor: 'pointer' }}>
            <div style={{ width: '100%', height: Math.max((d.totals.energy_kcal / max) * CHART_H, d.entries ? 2 : 0), borderRadius: '4px 4px 0 0', background: 'var(--protein)', opacity: i === selected ? 1 : 0.55 }} />
          </button>
        ))}
      </div>
      <div className="row" style={{ gap: dense ? 3 : 10 }}>
        {days.map((d, i) => (
          <span key={d.date} className="xsmall muted" style={{ flex: 1, textAlign: 'center', overflow: 'hidden' }}>
            {dense ? (i % 5 === 4 || i === days.length - 1 ? parseIsoDate(d.date).getDate() : '') : d.date === today() ? 'Today' : parseIsoDate(d.date).toLocaleDateString('en-IN', { weekday: 'short' })}
          </span>
        ))}
      </div>
    </div>
  )
}

function Bar({ pct, color, marker }: { pct: number; color: string; marker?: number }) {
  return (
    <div className="bar" style={{ position: 'relative', overflow: 'visible' }}>
      <div style={{ width: `${Math.min(pct, 100)}%`, background: color }} />
      {marker !== undefined && marker < 100 && (
        <span aria-hidden="true" title="Average requirement (EAR)" style={{ position: 'absolute', left: `${marker}%`, top: -3, bottom: -3, width: 2, background: 'var(--ink-2)', borderRadius: 1 }} />
      )}
    </div>
  )
}

function MacroRow({ m }: { m: NutrientAvg }) {
  return (
    <div className="stack" style={{ gap: 5 }}>
      <div className="row between small">
        <strong>{m.label}</strong>
        <span className="muted num">{amount(m.avg, m.unit)} of {amount(m.target, m.unit)} · {m.pct}%</span>
      </div>
      <Bar pct={m.pct} color={MACRO_COLOR[m.key] ?? 'var(--protein)'} />
    </div>
  )
}

function MicroRow({ m }: { m: MicroAvg }) {
  const s = STATUS[m.status]
  return (
    <div className="stack" style={{ gap: 6, padding: '10px 0' }}>
      <div className="row between small">
        <strong>{m.label}</strong>
        <span className="row" style={{ gap: 6 }}>
          <span className="num muted">{amount(m.avg, m.unit)} / {amount(m.target, m.unit)}</span>
          <span className="xsmall" style={{ fontWeight: 700, color: m.status === 'good' ? 'var(--accent-ink)' : m.status === 'low' ? 'var(--danger)' : 'var(--warn-ink)', whiteSpace: 'nowrap' }}>
            {s.icon} {s.label}
          </span>
        </span>
      </div>
      <Bar pct={m.pct} color={s.color} marker={m.ear ? (m.ear / m.target) * 100 : undefined} />
    </div>
  )
}

function LimitRow({ l }: { l: LimitAvg }) {
  const pct = l.limit > 0 ? (l.avg / l.limit) * 100 : 0
  return (
    <div className="stack" style={{ gap: 6, padding: '10px 0' }}>
      <div className="row between small">
        <strong>{l.label}</strong>
        <span className="row" style={{ gap: 6 }}>
          <span className="num muted">{amount(l.avg, l.unit)} / under {amount(l.limit, l.unit)}</span>
          <span className="xsmall" style={{ fontWeight: 700, color: l.over ? 'var(--danger)' : 'var(--accent-ink)' }}>{l.over ? '! Over' : '✓ OK'}</span>
        </span>
      </div>
      <Bar pct={pct} color={l.over ? 'var(--danger)' : 'var(--protein)'} />
    </div>
  )
}

export default function Insights() {
  const user = useUser()
  const [range, setRange] = useState<Range>(7)
  const [days, setDays] = useState<DaySummary[] | null>(null)
  const [data, setData] = useState<InsightsData | null>(null)
  const [error, setError] = useState('')
  const end = today()
  const start = addDays(end, -(range - 1))

  useEffect(() => {
    setData(null)
    setError('')
    api.get<DaySummary[]>(`/api/days?start=${start}&end=${end}`).then(setDays).catch((e) => setError(e.message))
    // Averages use complete days only: today is still in progress.
    api.get<InsightsData>(`/api/insights?start=${start}&end=${addDays(end, -1)}`).then(setData).catch((e) => setError(e.message))
  }, [start, end])

  const target = user.targets?.energy_kcal ?? 0

  return (
    <div className="screen">
      <div className="content">
        <div className="row between" style={{ alignItems: 'flex-end' }}>
          <div className="stack" style={{ gap: 2 }}>
            <span className="small muted" style={{ fontWeight: 600 }}>{longDate(start)} – {longDate(end)}</span>
            <h1 className="title">{range === 7 ? 'This week' : 'Last 30 days'}</h1>
          </div>
          <div className="seg" role="group" aria-label="Range" style={{ width: 150 }}>
            {RANGES.map((r) => <button key={r} aria-pressed={range === r} onClick={() => setRange(r)}>{r} days</button>)}
          </div>
        </div>
        {error && <p className="error" role="alert">{error}</p>}

        {days && <CaloriesChart key={range} days={days} target={target} />}

        {data && data.days_logged === 0 && (
          <p className="note"><Icon name="info" size={18} /><span>No complete days logged in this period yet. Averages and suggestions appear once you've logged a full day (today isn't counted until it's over).</span></p>
        )}

        {data && data.days_logged > 0 && (
          <>
            <p className={`note${data.enough_data ? '' : ' warn'}`} style={{ margin: 0 }}>
              <Icon name="info" size={18} />
              <span>
                Averages over {data.days_logged} logged day{data.days_logged > 1 ? 's' : ''} (days you didn't log are skipped).
                {!data.enough_data && ' Log at least 3 full days for reliable trends.'}
              </span>
            </p>

            <div className="stack">
              <h2 className="section-label">Energy and macros (daily average)</h2>
              <div className="card pad stack" style={{ gap: 14 }}>
                {data.energy && (
                  <div className="row between" style={{ alignItems: 'baseline' }}>
                    <span className="big-num" style={{ fontSize: 26 }}>{kcal(data.energy.avg)} <span className="small muted" style={{ fontFamily: 'var(--body)' }}>kcal</span></span>
                    <span className="small muted num">target {kcal(data.energy.target)} · {data.energy.pct}%</span>
                  </div>
                )}
                {data.macros.map((m) => <MacroRow key={m.key} m={m} />)}
              </div>
            </div>

            {data.suggestions.length > 0 && (
              <div className="stack">
                <h2 className="section-label">What would help most</h2>
                {data.suggestions.map((s) => (
                  <div key={s.key} className="card" style={{ overflow: 'hidden' }}>
                    <div className="stack" style={{ gap: 2, padding: '12px 16px', background: 'var(--warn-soft)' }}>
                      <strong style={{ fontSize: 15, color: 'var(--warn-ink)' }}>Low on {s.label.replace(/^[A-Z](?=[a-z])/, (c) => c.toLowerCase())}</strong>
                      <span className="xsmall" style={{ color: 'var(--warn-ink)' }}>About {grams(s.gap)} {s.unit} a day short. Good sources{data.diet ? '' : ' (vegetarian, as your diet isn’t set)'}:</span>
                    </div>
                    {s.foods.length === 0 ? (
                      <p className="small muted" style={{ margin: 0, padding: '12px 16px' }}>No suitable foods found in the database.</p>
                    ) : (
                      <div className="list">
                        {s.foods.map((f) => (
                          <Link key={f.id} to={`/log/food/${encodeURIComponent(f.id)}`} className="list-row">
                            <span className="grow stack" style={{ gap: 4 }}>
                              <span style={{ fontWeight: 700, fontSize: 14 }}>{f.name}</span>
                              <span className="row xsmall muted" style={{ gap: 6, flexWrap: 'wrap' }}>
                                <SourceTag source={f.source} kind="ingredient" />
                                {f.portion} · {kcal(f.energy_kcal)} kcal
                                {f.you_eat_it && <span className="tag green">You eat this</span>}
                              </span>
                            </span>
                            <span className="stack" style={{ gap: 2, alignItems: 'flex-end' }}>
                              <span className="num" style={{ fontWeight: 700, fontSize: 14 }}>+{grams(f.amount)} {s.unit}</span>
                              <span className="xsmall muted num">{f.pct_of_target}% of daily</span>
                            </span>
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="stack">
              <h2 className="section-label">Vitamins and minerals</h2>
              <div className="card" style={{ padding: '4px 16px' }}>
                <div className="list">{data.micros.map((m) => <MicroRow key={m.key} m={m} />)}</div>
              </div>
              <span className="xsmall muted" style={{ lineHeight: 1.5 }}>
                Targets are ICMR-NIN 2020 RDAs for your sex (potassium: WHO). The dark tick is the average requirement (EAR): below it, intake is likely too low.
                Some foods have no data for some vitamins, so real intake may be a little higher than shown. Vitamin B12, A and D aren't tracked yet.
              </span>
            </div>

            <div className="stack">
              <h2 className="section-label">Keep these under</h2>
              <div className="card" style={{ padding: '4px 16px' }}>
                <div className="list">{data.limits.map((l) => <LimitRow key={l.key} l={l} />)}</div>
              </div>
              <span className="xsmall muted">WHO limits: sodium under 2 g a day (5 g salt); free sugars and saturated fat each under 10% of your calories.</span>
            </div>
          </>
        )}
      </div>
      <TabBar />
    </div>
  )
}
