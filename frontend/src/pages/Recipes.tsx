import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useUser } from '../auth'
import FoodPicker from '../components/FoodPicker'
import Icon from '../components/Icon'
import { MacroRow } from '../components/Macros'
import { grams, kcal } from '../format'
import type { FoodSummary, Nutrients } from '../types'

interface Recipe {
  id: string
  name: string
  ingredients: { food_id: string; name: string; grams: number }[]
  raw_weight_g: number
  cooked_weight_g: number
  per_100g: Nutrients
}

export function RecipeList() {
  const navigate = useNavigate()
  const { katori_ml } = useUser().measures
  const [recipes, setRecipes] = useState<Recipe[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get<Recipe[]>('/api/recipes').then(setRecipes).catch((e) => setError(e.message))
  }, [])

  return (
    <div className="screen">
      <div className="content">
        <div className="row" style={{ gap: 4 }}>
          <button className="icon-btn" aria-label="Back" onClick={() => navigate(-1)} style={{ marginLeft: -10 }}><Icon name="back" /></button>
          <h1 className="title-sm">My recipes</h1>
        </div>
        <p className="small muted" style={{ margin: 0, lineHeight: 1.5 }}>
          Your own version of a dish: weigh the raw ingredients and the cooked pot, and every katori you log is exact for how you cook.
        </p>
        {error && <p className="error">{error}</p>}
        {recipes && recipes.length > 0 && (
          <div className="card list">
            {recipes.map((r) => (
              <Link key={r.id} to={`/recipes/${encodeURIComponent(r.id)}`} className="list-row">
                <span className="grow stack" style={{ gap: 2 }}>
                  <span style={{ fontWeight: 700, fontSize: 15 }}>{r.name}</span>
                  <span className="xsmall muted">{r.ingredients.length} ingredients · {grams(r.cooked_weight_g)} g cooked</span>
                </span>
                <span className="num small" style={{ fontWeight: 700 }}>{kcal((r.per_100g.energy_kcal * katori_ml) / 100)} kcal / katori</span>
              </Link>
            ))}
          </div>
        )}
        {recipes && recipes.length === 0 && <p className="small muted">No recipes yet.</p>}
      </div>
      <div className="footer">
        <Link to="/recipes/new" className="btn">New recipe</Link>
      </div>
    </div>
  )
}

interface Row {
  food: { id: string; name: string }
  grams: string
}

export function RecipeEditor() {
  const { recipeId } = useParams()
  const navigate = useNavigate()
  const { katori_ml } = useUser().measures
  const isNew = !recipeId
  const [name, setName] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [cooked, setCooked] = useState('')
  const [adding, setAdding] = useState(false)
  const [preview, setPreview] = useState<{ raw_weight_g: number; per_100g: Nutrients } | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (isNew) return
    api.get<Recipe>(`/api/recipes/${encodeURIComponent(recipeId!)}`).then((r) => {
      setName(r.name)
      setRows(r.ingredients.map((i) => ({ food: { id: i.food_id, name: i.name }, grams: String(i.grams) })))
      setCooked(String(r.cooked_weight_g))
    }).catch((e) => setError(e.message))
  }, [isNew, recipeId])

  const valid = rows.length > 0 && rows.every((r) => Number(r.grams) > 0) && Number(cooked) > 0
  const body = valid ? { name: name.trim() || 'Untitled', cooked_weight_g: Number(cooked), ingredients: rows.map((r) => ({ food_id: r.food.id, grams: Number(r.grams) })) } : null
  const bodyKey = JSON.stringify(body)

  useEffect(() => {
    if (!body) return setPreview(null)
    const t = setTimeout(() => {
      api.post<{ raw_weight_g: number; per_100g: Nutrients }>('/api/recipes/preview', body).then((p) => { setPreview(p); setError('') }).catch((e) => setError(e.message))
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bodyKey])

  const addIngredient = (f: FoodSummary) => {
    setRows((r) => [...r, { food: { id: f.id, name: f.name }, grams: '' }])
    setAdding(false)
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!body || !name.trim()) return setError('Give the recipe a name, at least one ingredient with grams, and the cooked weight.')
    setBusy(true)
    try {
      if (isNew) await api.post('/api/recipes', body)
      else await api.put(`/api/recipes/${encodeURIComponent(recipeId!)}`, body)
      navigate('/recipes', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
      setBusy(false)
    }
  }

  async function remove() {
    if (!confirmDelete) return setConfirmDelete(true)
    setBusy(true)
    try {
      await api.del(`/api/recipes/${encodeURIComponent(recipeId!)}`)
      navigate('/recipes', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete')
      setBusy(false)
    }
  }

  const perKatori = preview ? Object.fromEntries(Object.entries(preview.per_100g).map(([k, v]) => [k, (v * katori_ml) / 100])) : null

  return (
    <form className="screen" onSubmit={save}>
      <div className="content">
        <div className="row" style={{ gap: 4 }}>
          <button type="button" className="icon-btn" aria-label="Back" onClick={() => navigate(-1)} style={{ marginLeft: -10 }}><Icon name="back" /></button>
          <h1 className="title-sm">{isNew ? 'New recipe' : 'Edit recipe'}</h1>
        </div>

        <label className="field">Recipe name
          <input className="input" placeholder="Mom's rajma" value={name} onChange={(e) => setName(e.target.value)} />
        </label>

        <div className="stack">
          <span className="field">Raw ingredients, weighed before cooking</span>
          {rows.length > 0 && (
            <div className="card list">
              {rows.map((r, i) => (
                <div key={i} className="row" style={{ padding: '8px 8px 8px 16px', gap: 8 }}>
                  <span className="grow small" style={{ fontWeight: 600 }}>{r.food.name}</span>
                  <input className="input num" aria-label={`Grams of ${r.food.name}`} inputMode="decimal" placeholder="g" value={r.grams}
                    onChange={(e) => setRows((all) => all.map((x, j) => (j === i ? { ...x, grams: e.target.value } : x)))}
                    style={{ width: 84, height: 40, textAlign: 'right' }} />
                  <span className="small muted">g</span>
                  <button type="button" className="icon-btn" aria-label={`Remove ${r.food.name}`} onClick={() => setRows((all) => all.filter((_, j) => j !== i))}><Icon name="close" size={18} /></button>
                </div>
              ))}
            </div>
          )}
          {adding ? (
            <div className="stack" style={{ gap: 8 }}>
              <FoodPicker kind="ingredient" onPick={addIngredient} placeholder="Search ingredient: rajma, onion, mustard oil…" />
              <button type="button" className="link-btn" style={{ alignSelf: 'flex-start' }} onClick={() => setAdding(false)}>Cancel</button>
            </div>
          ) : (
            <button type="button" className="btn secondary small" onClick={() => setAdding(true)}>+ Add ingredient</button>
          )}
          <span className="xsmall muted">Skip water: the cooked weight already accounts for it.</span>
        </div>

        <label className="field">Cooked weight of the whole dish (g)
          <input className="input num" inputMode="decimal" placeholder="Weigh the pot, subtract the empty pot" value={cooked} onChange={(e) => setCooked(e.target.value)} />
        </label>

        {perKatori && (
          <div className="card pad stack" style={{ gap: 10, background: 'var(--accent-soft)', borderColor: 'transparent' }}>
            <span className="small" style={{ fontWeight: 700, color: 'var(--accent-ink)' }}>Per katori ({katori_ml} ml, about {katori_ml} g)</span>
            <span className="big-num" style={{ fontSize: 30 }}>{kcal(perKatori.energy_kcal)} <span className="small muted" style={{ fontFamily: 'var(--body)' }}>kcal</span></span>
            <MacroRow nutrients={perKatori} />
            <span className="xsmall muted">Makes about {(Number(cooked) / katori_ml).toFixed(1)} katoris from {grams(preview!.raw_weight_g)} g of raw ingredients.</span>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </div>
      <div className="footer">
        <button className="btn" type="submit" disabled={busy || !valid || !name.trim()}>{busy ? 'Saving…' : 'Save recipe'}</button>
        {!isNew && <button type="button" className="btn danger small" onClick={remove} disabled={busy}><Icon name="trash" size={18} />{confirmDelete ? 'Tap again to delete for good' : 'Delete recipe'}</button>}
      </div>
    </form>
  )
}
