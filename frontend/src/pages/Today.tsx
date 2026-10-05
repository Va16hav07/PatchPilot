import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useUser } from '../auth'
import Icon from '../components/Icon'
import { MacroBars } from '../components/Macros'
import TabBar from '../components/TabBar'
import { addDays, dayLabel, kcal, longDate, qty, today, unitLabel } from '../format'
import { MEALS, type Day, type LogEntry } from '../types'

function Ring({ eaten, target }: { eaten: number; target: number }) {
  const r = 56
  const circ = 2 * Math.PI * r
  const pct = target > 0 ? Math.min(eaten / target, 1) : 0
  const over = eaten > target
  return (
    <div style={{ position: 'relative', width: 128, height: 128, flexShrink: 0 }}>
      <svg width="128" height="128" viewBox="0 0 128 128" aria-hidden="true">
        <circle cx="64" cy="64" r={r} fill="none" stroke="var(--track)" strokeWidth="12" />
        {pct > 0 && (
          <circle cx="64" cy="64" r={r} fill="none" stroke={over ? 'var(--warn)' : 'var(--protein)'} strokeWidth="12" strokeLinecap="round"
            strokeDasharray={`${circ * pct} ${circ}`} transform="rotate(-90 64 64)" />
        )}
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span className="big-num" style={{ fontSize: 26 }}>{kcal(Math.abs(target - eaten))}</span>
        <span className="xsmall muted">{over ? 'kcal over' : 'kcal left'}</span>
      </div>
    </div>
  )
}

function entryLine(e: LogEntry): string {
  return `${qty(e.quantity)} ${unitLabel(e.unit, e.serving_unit)}`
}

export default function Today() {
  const user = useUser()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const date = params.get('date') ?? today()
  const [day, setDay] = useState<Day | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setDay(null)
    api.get<Day>(`/api/days/${date}`).then(setDay).catch((e) => setError(e.message))
  }, [date])

  const go = (n: number) => {
    const next = addDays(date, n)
    setParams(next === today() ? {} : { date: next })
  }
  const targets = day?.targets ?? user.targets
  const eaten = day?.totals.energy_kcal ?? 0

  return (
    <div className="screen">
      <div className="content">
        <div className="row between">
          <div className="row" style={{ gap: 2 }}>
            <button className="icon-btn" aria-label="Previous day" onClick={() => go(-1)} style={{ marginLeft: -12 }}><Icon name="back" /></button>
            <div className="stack" style={{ gap: 0 }}>
              <span className="small muted" style={{ fontWeight: 600 }}>{longDate(date)}</span>
              <h1 className="title">{dayLabel(date)}</h1>
            </div>
            {date < today() && <button className="icon-btn" aria-label="Next day" onClick={() => go(1)}><Icon name="forward" /></button>}
          </div>
          <Link to="/profile" aria-label="Profile" style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--accent)', color: 'var(--on-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, textDecoration: 'none', overflow: 'hidden' }}>
            {user.picture ? <img src={user.picture} alt="" width={44} height={44} referrerPolicy="no-referrer" /> : user.name[0]}
          </Link>
        </div>

        {error && <p className="error" role="alert">{error}</p>}

        {targets && (
          <div className="card pad stack" style={{ gap: 16, borderRadius: 20 }}>
            <div className="row" style={{ gap: 18 }}>
              <Ring eaten={eaten} target={targets.energy_kcal} />
              <div className="stack" style={{ gap: 10 }}>
                <div className="stack" style={{ gap: 0 }}><span className="small muted">Eaten</span><strong className="num" style={{ fontSize: 18 }}>{kcal(eaten)} kcal</strong></div>
                <div className="stack" style={{ gap: 0 }}><span className="small muted">Target</span><strong className="num" style={{ fontSize: 18 }}>{kcal(targets.energy_kcal)} kcal</strong></div>
              </div>
            </div>
            <MacroBars totals={day?.totals ?? {}} targets={targets} />
          </div>
        )}

        <div className="stack">
          {MEALS.map(({ key, label }) => {
            const entries = day?.meals[key] ?? []
            const total = entries.reduce((s, e) => s + e.nutrients.energy_kcal, 0)
            return (
              <section key={key} className="card" aria-label={label}>
                <div className="row between" style={{ padding: '12px 14px 12px 16px' }}>
                  <div className="stack" style={{ gap: 0 }}>
                    <strong style={{ fontSize: 15 }}>{label}</strong>
                    {entries.length > 0 && <span className="xsmall muted num">{kcal(total)} kcal</span>}
                  </div>
                  <Link className="pill-add" to={`/log?meal=${key}&date=${date}`}>+ Add</Link>
                </div>
                {entries.length > 0 && (
                  <div className="list" style={{ borderTop: '1px solid var(--line-soft)' }}>
                    {entries.map((e) => (
                      <button key={e.id} className="list-row" onClick={() => navigate(`/log/food/${encodeURIComponent(e.food_id)}`, { state: { entry: e } })}>
                        <span className="grow stack" style={{ gap: 2 }}>
                          <span style={{ fontWeight: 600, fontSize: 14 }}>{e.food_name}</span>
                          <span className="xsmall muted">{entryLine(e)}{e.oil_level !== 'home' ? ` · ${e.oil_level} oil` : ''}</span>
                        </span>
                        <span className="num" style={{ fontWeight: 700, fontSize: 14 }}>{kcal(e.nutrients.energy_kcal)}</span>
                      </button>
                    ))}
                  </div>
                )}
              </section>
            )
          })}
        </div>
      </div>
      <TabBar />
    </div>
  )
}
