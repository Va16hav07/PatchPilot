import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth, useUser } from '../auth'
import Icon from '../components/Icon'
import { kcal } from '../format'
import { DIETS, type Activity, type Diet, type Goal, type Profile, type Sex, type Targets, type User } from '../types'

interface Form {
  sex: Sex
  age: string
  height_cm: string
  weight_kg: string
  activity: Activity
  goal: Goal
  diet: Diet | null
}

function toProfile(f: Form): Profile | null {
  const age = Number(f.age)
  const height = Number(f.height_cm)
  const weight = Number(f.weight_kg)
  if (!(age >= 18 && age <= 100 && height >= 120 && height <= 230 && weight >= 30 && weight <= 250)) return null
  if (!f.diet) return null
  return { sex: f.sex, age: Math.round(age), height_cm: height, weight_kg: weight, activity: f.activity, goal: f.goal, diet: f.diet }
}

function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="stack" style={{ gap: 6 }}>
      <span className="field">{label}</span>
      <div className="seg" role="group" aria-label={label}>
        {options.map(([v, text]) => (
          <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function Setup() {
  const user = useUser()
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const p = user.profile
  const [form, setForm] = useState<Form>({
    sex: p?.sex ?? 'male',
    age: p ? String(p.age) : '',
    height_cm: p ? String(p.height_cm) : '',
    weight_kg: p ? String(p.weight_kg) : '',
    activity: p?.activity ?? 'moderate',
    goal: p?.goal ?? 'maintain',
    diet: p?.diet ?? null,
  })
  const [preview, setPreview] = useState<Targets | null>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const profile = toProfile(form)
  const profileKey = JSON.stringify(profile)

  useEffect(() => {
    if (!profile) return setPreview(null)
    const t = setTimeout(() => {
      api.post<Targets>('/api/me/targets/preview', profile).then(setPreview).catch(() => setPreview(null))
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileKey])

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }))

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!profile) return setError('Please fill in age (18+), height, weight and diet.')
    setSaving(true)
    try {
      const firstTime = !user.profile
      setUser(await api.put<User>('/api/me/profile', profile))
      navigate(firstTime ? '/setup/ai' : '/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save')
      setSaving(false)
    }
  }

  const first = user.name.split(' ')[0]
  return (
    <form className="screen" onSubmit={save}>
      <div className="content">
        {user.profile && (
          <button type="button" className="icon-btn" aria-label="Back" onClick={() => navigate(-1)} style={{ marginLeft: -10 }}>
            <Icon name="back" />
          </button>
        )}
        <div className="stack" style={{ gap: 6 }}>
          <h1 className="title">{user.profile ? 'Your profile' : `Hi ${first}, let's set your targets`}</h1>
          <p className="small muted" style={{ margin: 0 }}>Used to calculate your daily needs. Only you can see it.</p>
        </div>

        <div className="grid-3">
          <label className="field">Age
            <input className="input num" inputMode="numeric" value={form.age} onChange={(e) => set('age', e.target.value)} />
          </label>
          <label className="field">Height (cm)
            <input className="input num" inputMode="decimal" value={form.height_cm} onChange={(e) => set('height_cm', e.target.value)} />
          </label>
          <label className="field">Weight (kg)
            <input className="input num" inputMode="decimal" value={form.weight_kg} onChange={(e) => set('weight_kg', e.target.value)} />
          </label>
        </div>

        <Seg label="Sex (for the energy formula)" value={form.sex} onChange={(v) => set('sex', v)} options={[['male', 'Male'], ['female', 'Female']]} />

        <div className="stack" style={{ gap: 6 }}>
          <span className="field">Diet (food suggestions only show what you eat)</span>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }} role="group" aria-label="Diet">
            {DIETS.map(([v, label]) => (
              <button key={v} type="button" className="pill" aria-pressed={form.diet === v} onClick={() => set('diet', v)}>{label}</button>
            ))}
          </div>
        </div>

        <label className="field">Activity
          <select className="input" value={form.activity} onChange={(e) => set('activity', e.target.value as Activity)}>
            <option value="sedentary">Sedentary (desk job, little exercise)</option>
            <option value="moderate">Moderate (on your feet, regular exercise)</option>
            <option value="heavy">Heavy (manual work, hard daily training)</option>
          </select>
        </label>

        <Seg label="Goal" value={form.goal} onChange={(v) => set('goal', v)} options={[['lose', 'Lose'], ['maintain', 'Maintain'], ['gain', 'Gain']]} />

        <div className="card pad stack" style={{ gap: 12 }} aria-live="polite">
          <strong style={{ fontSize: 15 }}>Your daily targets</strong>
          {preview ? (
            <>
              <div className="row" style={{ alignItems: 'baseline', gap: 6 }}>
                <span className="big-num" style={{ fontSize: 34 }}>{kcal(preview.energy_kcal)}</span>
                <span className="small muted">kcal / day</span>
              </div>
              <div className="macro-grid xsmall muted">
                <div className="stack" style={{ gap: 2 }}><strong className="num" style={{ fontSize: 15, color: 'var(--ink)' }}>{preview.protein_g} g</strong>Protein</div>
                <div className="stack" style={{ gap: 2 }}><strong className="num" style={{ fontSize: 15, color: 'var(--ink)' }}>{preview.carb_g} g</strong>Carbs</div>
                <div className="stack" style={{ gap: 2 }}><strong className="num" style={{ fontSize: 15, color: 'var(--ink)' }}>{preview.fat_g} g</strong>Fat</div>
                <div className="stack" style={{ gap: 2 }}><strong className="num" style={{ fontSize: 15, color: 'var(--ink)' }}>{preview.fibre_g} g</strong>Fibre</div>
              </div>
              <span className="xsmall muted">ICMR-NIN 2020 method for Indian adults. You can fine-tune these later in Profile.</span>
            </>
          ) : (
            <span className="small muted">Fill in age, height, weight and diet to see them.</span>
          )}
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
      <div className="footer">
        <button className="btn" type="submit" disabled={!profile || saving}>
          {saving ? 'Saving…' : user.profile ? 'Save' : 'Continue'}
        </button>
      </div>
    </form>
  )
}
