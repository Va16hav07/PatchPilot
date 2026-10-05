import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAuth, useUser } from '../auth'
import GeminiKeyCard from '../components/GeminiKeyCard'
import Icon from '../components/Icon'
import TabBar from '../components/TabBar'
import { kcal } from '../format'
import type { Measures, Targets, User } from '../types'

const ACTIVITY = { sedentary: 'Sedentary', moderate: 'Moderate', heavy: 'Heavy' }
const GOAL = { lose: 'Lose weight', maintain: 'Maintain', gain: 'Gain weight' }
const DIET = { vegetarian: 'Vegetarian', eggetarian: 'Eggetarian', non_vegetarian: 'Non-vegetarian', jain: 'Jain' }

function TargetsForm({ targets, onDone }: { targets: Targets; onDone: () => void }) {
  const { setUser } = useAuth()
  const [form, setForm] = useState(targets)
  const [error, setError] = useState('')
  const fields: [keyof Targets, string][] = [
    ['energy_kcal', 'Energy (kcal)'], ['protein_g', 'Protein (g)'], ['carb_g', 'Carbs (g)'], ['fat_g', 'Fat (g)'], ['fibre_g', 'Fibre (g)'],
  ]
  async function save(e: FormEvent) {
    e.preventDefault()
    try {
      setUser(await api.put<User>('/api/me/targets', form))
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
    }
  }
  return (
    <form className="card pad stack" style={{ gap: 12 }} onSubmit={save}>
      <div className="grid-2">
        {fields.map(([k, label]) => (
          <label key={k} className="field">{label}
            <input className="input num" inputMode="numeric" value={form[k]} onChange={(e) => setForm({ ...form, [k]: Math.max(0, Math.round(Number(e.target.value) || 0)) })} />
          </label>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button type="button" className="btn secondary small" onClick={onDone}>Cancel</button>
        <button type="submit" className="btn small">Save targets</button>
      </div>
    </form>
  )
}

function MeasuresForm({ measures }: { measures: Measures }) {
  const { setUser } = useAuth()
  const [form, setForm] = useState({ katori_ml: String(measures.katori_ml), glass_ml: String(measures.glass_ml) })
  const [status, setStatus] = useState('')
  const dirty = Number(form.katori_ml) !== measures.katori_ml || Number(form.glass_ml) !== measures.glass_ml
  async function save(e: FormEvent) {
    e.preventDefault()
    try {
      setUser(await api.put<User>('/api/me/measures', { katori_ml: Number(form.katori_ml), glass_ml: Number(form.glass_ml) }))
      setStatus('Saved')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Could not save')
    }
  }
  return (
    <form className="card pad stack" style={{ gap: 12 }} onSubmit={save}>
      <p className="small muted" style={{ margin: 0, lineHeight: 1.5 }}>
        Fill your katori with water and weigh it (1 g of water is 1 ml). This makes every "1 katori" you log match your real bowl.
      </p>
      <div className="grid-2">
        <label className="field">Your katori (ml)
          <input className="input num" inputMode="numeric" value={form.katori_ml} onChange={(e) => { setForm({ ...form, katori_ml: e.target.value }); setStatus('') }} />
        </label>
        <label className="field">Your glass (ml)
          <input className="input num" inputMode="numeric" value={form.glass_ml} onChange={(e) => { setForm({ ...form, glass_ml: e.target.value }); setStatus('') }} />
        </label>
      </div>
      <div className="row between">
        <span className="small muted" role="status">{status}</span>
        <button type="submit" className="btn small" style={{ width: 'auto', padding: '0 20px' }} disabled={!dirty}>Save</button>
      </div>
    </form>
  )
}

export default function Profile() {
  const user = useUser()
  const { signOut } = useAuth()
  const [editTargets, setEditTargets] = useState(false)
  const { hash } = useLocation()

  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [hash])
  const p = user.profile!
  const t = user.targets

  return (
    <div className="screen">
      <div className="content">
        <h1 className="title">Profile</h1>

        <div className="card pad stack" style={{ gap: 14 }}>
          <div className="row" style={{ gap: 12 }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 20, overflow: 'hidden', flexShrink: 0 }}>
              {user.picture ? <img src={user.picture} alt="" width={52} height={52} referrerPolicy="no-referrer" /> : user.name[0]}
            </div>
            <div className="stack grow" style={{ gap: 2 }}>
              <strong style={{ fontSize: 17 }}>{user.name}</strong>
              <span className="xsmall muted" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>Signed in with Google · {user.email}</span>
            </div>
          </div>
          <Link to="/setup" className="row between" style={{ borderTop: '1px solid var(--line-soft)', paddingTop: 12, textDecoration: 'none', color: 'var(--ink)' }}>
            <span className="macro-grid xsmall muted grow">
              <span className="stack" style={{ gap: 2 }}><strong className="num" style={{ fontSize: 15, color: 'var(--ink)' }}>{p.age}</strong>Age</span>
              <span className="stack" style={{ gap: 2 }}><strong className="num" style={{ fontSize: 15, color: 'var(--ink)' }}>{p.height_cm} cm</strong>Height</span>
              <span className="stack" style={{ gap: 2 }}><strong className="num" style={{ fontSize: 15, color: 'var(--ink)' }}>{p.weight_kg} kg</strong>Weight</span>
              <span className="stack" style={{ gap: 2 }}><strong style={{ fontSize: 15, color: 'var(--ink)' }}>{ACTIVITY[p.activity]}</strong>Activity</span>
            </span>
            <Icon name="forward" size={18} />
          </Link>
          <span className="xsmall muted">Goal: {GOAL[p.goal]} · Diet: {p.diet ? DIET[p.diet] : 'not set'}. Tap above to update.</span>
        </div>

        <div className="stack">
          <div className="row between">
            <h2 className="section-label">Daily targets</h2>
            {!editTargets && <button className="link-btn" onClick={() => setEditTargets(true)}>Edit</button>}
          </div>
          {editTargets && t ? (
            <TargetsForm targets={t} onDone={() => setEditTargets(false)} />
          ) : t && (
            <div className="card pad stack" style={{ gap: 6 }}>
              <span className="num" style={{ fontWeight: 700 }}>{kcal(t.energy_kcal)} kcal · P {t.protein_g} g · C {t.carb_g} g · F {t.fat_g} g · Fibre {t.fibre_g} g</span>
              <span className="xsmall muted">{user.targets_custom ? 'Set by you. Saving your profile recalculates them.' : 'Calculated with the ICMR-NIN 2020 method.'}</span>
            </div>
          )}
        </div>

        <div className="stack">
          <h2 className="section-label">Your measurements</h2>
          <MeasuresForm measures={user.measures} />
        </div>

        <Link to="/recipes" className="card list-row" style={{ borderRadius: 16 }}>
          <span className="grow stack" style={{ gap: 2 }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>My recipes</span>
            <span className="xsmall muted">Your own dishes, exact per katori</span>
          </span>
          <Icon name="forward" size={18} />
        </Link>

        <div className="stack" id="ai">
          <h2 className="section-label">AI logging (Gemini)</h2>
          <GeminiKeyCard />
        </div>

        <button className="btn danger" onClick={signOut}>Sign out</button>
      </div>
      <TabBar />
    </div>
  )
}
