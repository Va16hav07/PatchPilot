import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import type { Draft } from '../ai/meal'
import { mapPortion } from '../ai/meal'
import { api } from '../api'
import { hapticCommit } from '../feedback'
import FoodPicker, { SourceTag } from '../components/FoodPicker'
import Icon from '../components/Icon'
import { MacroRow } from '../components/Macros'
import { kcal, qty, today, unitLabel } from '../format'
import { MEALS, type FoodSummary, type Meal, type Nutrients, type OilLevel, type PortionResult } from '../types'

interface ReviewState {
  drafts: Draft[]
  meal: Meal
  date: string
  source: 'text' | 'voice' | 'photo'
  text: string | null
}

const OIL: [OilLevel, string][] = [['low', 'Low'], ['home', 'Home'], ['restaurant', 'Restaurant']]

function stepFor(unit: string) {
  return unit === 'g' || unit === 'ml' ? 10 : unit === 'serving' ? 1 : 0.5
}

function servingUnit(f: FoodSummary): string | null {
  return f.kind === 'dish' ? f.basis.replace(/^1 /, '') : null
}

function DraftCard({
  draft,
  onChange,
  onRemove,
  onResult,
}: {
  draft: Draft
  onChange: (d: Draft) => void
  onRemove: () => void
  onResult: (key: string, n: Nutrients | null) => void
}) {
  const [picking, setPicking] = useState(!draft.food && draft.candidates.length === 0)
  const [result, setResult] = useState<PortionResult | null>(null)
  const [error, setError] = useState('')
  const { food, quantity, unit, oil_level } = draft

  useEffect(() => {
    if (!food || !(quantity > 0)) {
      setResult(null)
      onResult(draft.key, null)
      return
    }
    const t = setTimeout(() => {
      api.post<PortionResult>(`/api/foods/${encodeURIComponent(food.id)}/portion`, { quantity, unit, oil_level })
        .then((r) => { setResult(r); setError(''); onResult(draft.key, r.nutrients) })
        .catch((e) => { setError(e.message); onResult(draft.key, null) })
    }, 150)
    return () => clearTimeout(t)
  }, [food, quantity, unit, oil_level, draft.key, onResult])

  const pick = (f: FoodSummary) => {
    const mapped = mapPortion({ quantity: draft.quantity, unit: draft.unit, estimated_grams: 0 }, f)
    onChange({ ...draft, food: f, ...mapped, check: mapped.check })
    setPicking(false)
  }
  const edit = (patch: Partial<Draft>) => onChange({ ...draft, ...patch, check: null })

  return (
    <div className="card pad stack" style={{ gap: 12, borderColor: draft.check ? 'var(--warn)' : undefined, borderWidth: draft.check ? 1.5 : 1 }}>
      <div className="row between" style={{ alignItems: 'flex-start' }}>
        <div className="stack grow" style={{ gap: 4 }}>
          <span className="xsmall muted">You said: {draft.phrase}</span>
          {food ? (
            <>
              <strong style={{ fontSize: 16 }}>{food.name}</strong>
              <span className="row" style={{ gap: 6 }}><SourceTag source={food.source} kind={food.kind} /></span>
            </>
          ) : (
            <strong style={{ fontSize: 16, color: 'var(--warn-ink)' }}>Which food was it?</strong>
          )}
        </div>
        <div className="row" style={{ gap: 0 }}>
          {food && result && <span className="num" style={{ fontWeight: 700, fontSize: 16, whiteSpace: 'nowrap' }}>{kcal(result.nutrients.energy_kcal)} kcal</span>}
          <button className="icon-btn" aria-label={`Remove ${draft.phrase}`} onClick={onRemove}><Icon name="trash" size={18} /></button>
        </div>
      </div>

      {draft.check && (
        <div className="row between" style={{ gap: 8 }}>
          <span className="small" style={{ color: 'var(--warn-ink)', fontWeight: 600 }}>{draft.check}</span>
          {food && <button className="link-btn" onClick={() => edit({})}>Looks right</button>}
        </div>
      )}

      {!picking && draft.candidates.length > 0 && (!food || draft.check) && (
        <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
          {draft.candidates.filter((c) => c.id !== food?.id).slice(0, 4).map((c) => (
            <button key={c.id} className="pill" onClick={() => pick(c)} style={{ height: 'auto', minHeight: 36, padding: '6px 12px', whiteSpace: 'normal', textAlign: 'left' }}>{c.name}</button>
          ))}
        </div>
      )}

      {picking ? (
        <div className="stack" style={{ gap: 8 }}>
          <FoodPicker onPick={pick} initial={draft.phrase} suggestions={draft.candidates} />
          {food && <button className="link-btn" onClick={() => setPicking(false)} style={{ alignSelf: 'flex-start' }}>Cancel</button>}
        </div>
      ) : (
        <button className="link-btn" onClick={() => setPicking(true)} style={{ alignSelf: 'flex-start', padding: 0 }}>{food ? 'Change food' : 'Search for it'}</button>
      )}

      {food && !picking && (
        <>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
            <div className="stepper">
              <button aria-label="Less" onClick={() => edit({ quantity: Math.max(0, Math.round((quantity - stepFor(unit)) * 100) / 100) })} disabled={quantity - stepFor(unit) <= 0}>−</button>
              <input aria-label="Quantity" inputMode="decimal" value={qty(quantity)} onChange={(e) => edit({ quantity: Number(e.target.value) || 0 })} />
              <button aria-label="More" onClick={() => edit({ quantity: Math.round((quantity + stepFor(unit)) * 100) / 100 })}>+</button>
            </div>
            {food.units.length > 1 ? (
              <select className="input" aria-label="Unit" value={unit} style={{ width: 'auto', flex: 1 }}
                onChange={(e) => { const u = e.target.value; edit({ unit: u, quantity: u === 'g' || u === 'ml' ? 100 : 1 }) }}>
                {food.units.map((u) => <option key={u} value={u}>{unitLabel(u, servingUnit(food))}</option>)}
              </select>
            ) : (
              <strong>{unitLabel(unit, servingUnit(food))}</strong>
            )}
          </div>
          {food.kind === 'dish' && (
            <div className="seg" role="group" aria-label="Oil level">
              {OIL.map(([v, label]) => <button key={v} aria-pressed={oil_level === v} onClick={() => edit({ oil_level: v })}>{label} oil</button>)}
            </div>
          )}
          {result?.assumptions.map((a) => <span key={a} className="xsmall muted">{a}</span>)}
        </>
      )}
      {error && <p className="error" style={{ margin: 0 }}>{error}</p>}
    </div>
  )
}

export default function Review() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as ReviewState | null
  const [drafts, setDrafts] = useState<Draft[]>(state?.drafts ?? [])
  const [results, setResults] = useState<Record<string, Nutrients | null>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const onResult = useCallback((key: string, n: Nutrients | null) => setResults((r) => ({ ...r, [key]: n })), [])

  const totals = useMemo(() => {
    const t: Nutrients = {}
    for (const d of drafts) {
      const n = results[d.key]
      if (!n) continue
      for (const [k, v] of Object.entries(n)) t[k] = (t[k] ?? 0) + v
    }
    return t
  }, [drafts, results])

  if (!state) return <Navigate to="/log" replace />
  const { meal, date } = state
  const mealLabel = MEALS.find((m) => m.key === meal)?.label ?? meal
  const blocking = drafts.filter((d) => !d.food || d.check || !(d.quantity > 0)).length

  async function save() {
    setSaving(true)
    setError('')
    try {
      await api.post('/api/logs/batch', {
        date, meal,
        items: drafts.map((d) => ({ food_id: d.food!.id, quantity: d.quantity, unit: d.unit, oil_level: d.oil_level })),
      })
      hapticCommit()
      navigate(date === today() ? '/' : `/?date=${date}`, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
      setSaving(false)
    }
  }

  return (
    <div className="screen">
      <div className="content">
        <div className="row" style={{ gap: 4, alignItems: 'flex-start' }}>
          <button className="icon-btn" aria-label="Back" onClick={() => navigate(-1)} style={{ marginLeft: -10, flexShrink: 0 }}><Icon name="back" /></button>
          <div className="stack" style={{ gap: 2, paddingTop: 6 }}>
            <h1 className="title-sm">Check your {mealLabel.toLowerCase()}</h1>
            <span className="small muted">Adjust anything that's off. Numbers come from the food database.</span>
          </div>
        </div>
        {state.text && <p className="small muted" style={{ margin: 0 }}>"{state.text}"</p>}

        {drafts.map((d) => (
          <DraftCard key={d.key} draft={d}
            onChange={(nd) => setDrafts((all) => all.map((x) => (x.key === d.key ? nd : x)))}
            onRemove={() => setDrafts((all) => all.filter((x) => x.key !== d.key))}
            onResult={onResult} />
        ))}
        {drafts.length === 0 && <p className="small muted">Nothing left to log.</p>}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
      <div className="footer">
        <div className="row between" style={{ alignItems: 'baseline' }}>
          <span className="small" style={{ fontWeight: 700, color: 'var(--ink-3)' }}>{mealLabel} total</span>
          <span className="big-num" style={{ fontSize: 28 }}>{kcal(totals.energy_kcal ?? 0)} kcal</span>
        </div>
        <MacroRow nutrients={totals} />
        <button className="btn" onClick={save} disabled={saving || drafts.length === 0 || blocking > 0}>
          {blocking > 0 ? `Check ${blocking} highlighted item${blocking > 1 ? 's' : ''} to save` : saving ? 'Saving…' : `Save to ${mealLabel}`}
        </button>
      </div>
    </div>
  )
}
