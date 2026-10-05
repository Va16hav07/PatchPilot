import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { MacroRow } from '../components/Macros'
import { grams, kcal, qty, SOURCE_LABEL, today, unitLabel } from '../format'
import { MEALS, type FoodDetail, type LogEntry, type Meal, type OilLevel, type PortionResult } from '../types'

const MICROS: [string, string, string][] = [
  ['sugar_g', 'Free sugars', 'g'],
  ['sat_fat_g', 'Saturated fat', 'g'],
  ['sodium_mg', 'Sodium', 'mg'],
  ['potassium_mg', 'Potassium', 'mg'],
  ['calcium_mg', 'Calcium', 'mg'],
  ['iron_mg', 'Iron', 'mg'],
  ['zinc_mg', 'Zinc', 'mg'],
  ['magnesium_mg', 'Magnesium', 'mg'],
  ['folate_ug', 'Folate', 'µg'],
  ['vit_c_mg', 'Vitamin C', 'mg'],
]

const OIL: [OilLevel, string][] = [['low', 'Low'], ['home', 'Home-style'], ['restaurant', 'Restaurant']]

function defaultPortion(food: FoodDetail): { unit: string; quantity: number } {
  if (food.kind === 'ingredient') return { unit: 'g', quantity: 100 }
  if (food.units.includes('katori')) return { unit: 'katori', quantity: 1 }
  return { unit: 'serving', quantity: 1 }
}

function step(unit: string): number {
  return unit === 'g' || unit === 'ml' ? 10 : unit === 'serving' ? 1 : 0.5
}

export default function Portion() {
  const { foodId = '' } = useParams()
  const [params] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const navState = location.state as { entry?: LogEntry; preset?: { quantity: number; unit: string; oil_level: OilLevel } } | null
  const entry = navState?.entry
  const preset = navState?.preset
  const [meal, setMeal] = useState<Meal>(entry?.meal ?? ((params.get('meal') as Meal) || 'lunch'))
  const date = entry?.date ?? params.get('date') ?? today()

  const [food, setFood] = useState<FoodDetail | null>(null)
  const [unit, setUnit] = useState(entry?.unit ?? '')
  const [quantity, setQuantity] = useState<number>(entry?.quantity ?? 0)
  const [qtyText, setQtyText] = useState(entry ? qty(entry.quantity) : '')
  const [oil, setOil] = useState<OilLevel>(entry?.oil_level ?? 'home')
  const [result, setResult] = useState<PortionResult | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get<FoodDetail>(`/api/foods/${encodeURIComponent(foodId)}`).then((f) => {
      setFood(f)
      if (!entry) {
        const d = preset && f.units.includes(preset.unit) ? preset : defaultPortion(f)
        setUnit(d.unit)
        setQuantity(d.quantity)
        setQtyText(qty(d.quantity))
        if (preset) setOil(preset.oil_level)
      }
    }).catch((e) => setError(e.message))
  }, [foodId, entry, preset])

  useEffect(() => {
    if (!food || !unit || !(quantity > 0)) return setResult(null)
    const t = setTimeout(() => {
      api.post<PortionResult>(`/api/foods/${encodeURIComponent(food.id)}/portion`, { quantity, unit, oil_level: oil })
        .then((r) => { setResult(r); setError('') })
        .catch((e) => setError(e.message))
    }, 150)
    return () => clearTimeout(t)
  }, [food, unit, quantity, oil])

  const setQty = (n: number) => {
    const v = Math.max(0, Math.round(n * 100) / 100)
    setQuantity(v)
    setQtyText(qty(v))
  }
  const changeUnit = (u: string) => {
    setUnit(u)
    setQty(u === 'g' || u === 'ml' ? 100 : 1)
  }

  async function save() {
    if (!food) return
    setBusy(true)
    try {
      const portion = { quantity, unit, oil_level: oil }
      if (entry) await api.patch(`/api/logs/${entry.id}`, portion)
      else await api.post('/api/logs', { ...portion, date, meal, food_id: food.id })
      navigate(date === today() ? '/' : `/?date=${date}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
      setBusy(false)
    }
  }

  async function remove() {
    if (!entry) return
    setBusy(true)
    try {
      await api.del(`/api/logs/${entry.id}`)
      navigate(date === today() ? '/' : `/?date=${date}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete')
      setBusy(false)
    }
  }

  if (!food) {
    return <div className="screen center">{error ? <p className="error">{error}</p> : <p className="muted">Loading…</p>}</div>
  }

  const isDish = food.kind === 'dish'
  const mealLabel = MEALS.find((m) => m.key === meal)?.label ?? meal
  const showOil = isDish && (food.added_fat_g ?? 0) > 0
  const n = result?.nutrients

  return (
    <div className="screen">
      <div className="content">
        <button className="icon-btn" aria-label="Back" onClick={() => navigate(-1)} style={{ marginLeft: -10 }}><Icon name="back" /></button>
        <div className="stack" style={{ gap: 8 }}>
          <h1 className="title-sm">{food.name}</h1>
          <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
            <span className={`tag${isDish ? ' green' : ''}`}>{SOURCE_LABEL[food.source] ?? food.source}</span>
            {food.group && <span className="tag">{food.group}</span>}
            {food.local_names.slice(0, 3).map((l) => <span key={l} className="tag">{l}</span>)}
          </div>
        </div>

        {!entry && (
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }} role="group" aria-label="Meal">
            {MEALS.map((m) => <button key={m.key} className="pill" aria-pressed={meal === m.key} onClick={() => setMeal(m.key)}>{m.label}</button>)}
          </div>
        )}

        <div className="card pad stack" style={{ gap: 14 }}>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
            <div className="stepper">
              <button aria-label="Less" onClick={() => setQty(quantity - step(unit))} disabled={quantity - step(unit) <= 0}>−</button>
              <input
                aria-label="Quantity" inputMode="decimal" value={qtyText}
                onChange={(e) => { setQtyText(e.target.value); setQuantity(Number(e.target.value) || 0) }}
              />
              <button aria-label="More" onClick={() => setQty(quantity + step(unit))}>+</button>
            </div>
            {food.units.length > 1 ? (
              <select className="input" aria-label="Unit" value={unit} onChange={(e) => changeUnit(e.target.value)} style={{ width: 'auto', flex: 1 }}>
                {food.units.map((u) => <option key={u} value={u}>{unitLabel(u, food.serving_unit)}</option>)}
              </select>
            ) : (
              <strong>{unitLabel(unit, food.serving_unit)}</strong>
            )}
          </div>

          {showOil && (
            <div className="stack" style={{ gap: 6 }}>
              <span className="xsmall" style={{ fontWeight: 700, color: 'var(--muted)' }}>Oil / ghee in cooking</span>
              <div className="seg" role="group" aria-label="Oil level">
                {OIL.map(([v, label]) => <button key={v} aria-pressed={oil === v} onClick={() => setOil(v)}>{label}</button>)}
              </div>
            </div>
          )}

          <div className="row between" style={{ alignItems: 'baseline' }}>
            <span className="small muted">
              {result?.grams != null && `${grams(result.grams)} g`}
              {result?.servings != null && `${qty(result.servings)} × standard ${food.serving_unit ?? 'serving'}`}
            </span>
            <span className="big-num" style={{ fontSize: 30 }}>{n ? kcal(n.energy_kcal) : '–'} <span className="small muted" style={{ fontFamily: 'var(--body)' }}>kcal</span></span>
          </div>
          {n && <MacroRow nutrients={n} />}
        </div>

        {result?.assumptions.map((a) => (
          <p key={a} className="note warn" style={{ margin: 0 }}><Icon name="info" size={18} /><span>{a}</span></p>
        ))}

        {n && (
          <div className="stack">
            <h2 className="section-label">More nutrients</h2>
            <div className="card list">
              {MICROS.map(([k, label, u]) => (
                <div key={k} className="row between small" style={{ padding: '10px 16px' }}>
                  <span>{label}</span><span className="num" style={{ fontWeight: 700 }}>{grams(n[k] ?? 0)} {u}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="stack">
          <h2 className="section-label">Where these numbers come from</h2>
          <div className="card pad stack small" style={{ gap: 8, lineHeight: 1.5, color: 'var(--ink-2)' }}>
            {food.source === 'IFCT2017' && <span>Indian Food Composition Tables 2017 (ICMR-NIN), lab-measured, per 100 g edible portion.</span>}
            {food.source === 'INDB' && <span>Indian Nutrient Databank standard recipe, calculated from IFCT ingredients. Values are per standard {food.serving_unit ?? 'serving'} of the recipe.</span>}
            {food.derived_from && <span>Not in INDB, so derived from: {food.derived_from}, using IFCT 2017 values for the swapped ingredient.</span>}
            {food.source === 'USDA' && <span>USDA FoodData Central #{food.id.split(':')[1]}, used because IFCT 2017 has no entry for this food.</span>}
            {food.source === 'MY_RECIPE' && <span>Your own recipe: raw ingredient values from IFCT 2017 divided by the cooked weight you entered.</span>}
            {food.ingredients && food.ingredients.length > 0 && (
              <details>
                <summary style={{ cursor: 'pointer', fontWeight: 700, color: 'var(--accent)' }}>Recipe ingredients</summary>
                <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                  {food.ingredients.map((i, idx) => <li key={idx}>{i.name}: {i.amount} {i.unit}</li>)}
                </ul>
              </details>
            )}
            {food.quality_flags.length > 0 && <span className="xsmall muted">Data checks: {food.quality_flags.join(', ').replaceAll('_', ' ')}</span>}
          </div>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
      <div className="footer">
        <button className="btn" onClick={save} disabled={busy || !result}>{entry ? 'Save changes' : `Add to ${mealLabel}`}</button>
        {entry && <button className="btn danger small" onClick={remove} disabled={busy}><Icon name="trash" size={18} />Remove from {mealLabel}</button>}
      </div>
    </div>
  )
}
