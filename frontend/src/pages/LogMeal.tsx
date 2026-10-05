import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { aiAvailable } from '../ai/gemini'
import { analyseMeal, compressImage, type MealInput } from '../ai/meal'
import { listen, speechSupported, type Listening } from '../ai/speech'
import { api } from '../api'
import FoodPicker from '../components/FoodPicker'
import Icon from '../components/Icon'
import { addDays, kcal, qty, today, unitLabel } from '../format'
import { MEALS, type Day, type FoodSummary, type Meal, type OilLevel } from '../types'

type Mode = 'type' | 'speak' | 'photo' | 'search'

interface RecentFood {
  food_id: string
  food_name: string
  source: string
  quantity: number
  unit: string
  serving_unit: string | null
  oil_level: OilLevel
  energy_kcal: number
}

export function mealForNow(): Meal {
  const h = new Date().getHours()
  if (h < 11) return 'breakfast'
  if (h < 16) return 'lunch'
  if (h < 19) return 'snacks'
  return 'dinner'
}

const MODE_TABS: { key: Mode; label: string; icon: React.ReactNode }[] = [
  { key: 'type', label: 'Type', icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><path d="M4 6h16M4 12h16M4 18h10" /></svg> },
  { key: 'speak', label: 'Speak', icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg> },
  { key: 'photo', label: 'Photo', icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinejoin="round"><path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" /><circle cx="12" cy="13.5" r="3.5" /></svg> },
  { key: 'search', label: 'Search', icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg> },
]

export default function LogMeal() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const meal = (params.get('meal') as Meal) || mealForNow()
  const date = params.get('date') ?? today()
  const [ai, setAi] = useState<boolean | null>(null)
  const mode = (params.get('mode') as Mode) || (ai === false ? 'search' : 'type')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [recent, setRecent] = useState<RecentFood[]>([])
  const [yesterday, setYesterday] = useState<{ count: number; kcal: number } | null>(null)
  const [listening, setListening] = useState<Listening | null>(null)
  const [lang, setLang] = useState<'en-IN' | 'hi-IN'>('en-IN')
  const fileRef = useRef<HTMLInputElement>(null)
  const mealLabel = MEALS.find((m) => m.key === meal)?.label ?? meal

  useEffect(() => {
    aiAvailable().then(setAi)
    api.get<RecentFood[]>('/api/logs/recent?limit=6').then(setRecent).catch(() => setRecent([]))
  }, [])

  useEffect(() => {
    api.get<Day>(`/api/days/${addDays(date, -1)}`).then((d) => {
      const entries = d.meals[meal]
      setYesterday(entries.length ? { count: entries.length, kcal: entries.reduce((s, e) => s + e.nutrients.energy_kcal, 0) } : null)
    }).catch(() => setYesterday(null))
  }, [date, meal])

  useEffect(() => () => listening?.stop(), [listening])

  const setParam = (k: string, v: string) => {
    const next = new URLSearchParams(params)
    next.set(k, v)
    setParams(next, { replace: true })
  }
  const back = () => navigate(date === today() ? '/' : `/?date=${date}`)

  async function analyse(input: MealInput, source: 'text' | 'voice' | 'photo') {
    setError('')
    setBusy(source === 'photo' ? 'Looking at your plate…' : 'Working out what you ate…')
    try {
      const drafts = await analyseMeal(input)
      if (drafts.length === 0) {
        setError("Couldn't find any food in that. Try describing it differently.")
      } else {
        navigate('/log/review', { state: { drafts, meal, date, source, text: 'text' in input ? input.text : null } })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy('')
    }
  }

  function toggleListening() {
    if (listening) {
      listening.stop()
      return
    }
    setError('')
    const session = listen(lang, setText, (err) => {
      setListening(null)
      if (err) setError(err)
    })
    setListening(session)
  }

  async function onPhoto(file: File | undefined) {
    if (!file) return
    try {
      const image = await compressImage(file)
      await analyse({ image, note: text.trim() || undefined }, 'photo')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read the photo')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function copyYesterday() {
    setBusy('Copying…')
    try {
      await api.post(`/api/days/${date}/copy`, { from_date: addDays(date, -1), from_meal: meal, to_meal: meal })
      back()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not copy')
      setBusy('')
    }
  }

  const openFood = (f: FoodSummary) => navigate(`/log/food/${encodeURIComponent(f.id)}?meal=${meal}&date=${date}`)
  const openRecent = (r: RecentFood) =>
    navigate(`/log/food/${encodeURIComponent(r.food_id)}?meal=${meal}&date=${date}`, {
      state: { preset: { quantity: r.quantity, unit: r.unit, oil_level: r.oil_level } },
    })

  const needsKey = ai === false && mode !== 'search'

  return (
    <div className="screen">
      <div className="content">
        <div className="row" style={{ gap: 4 }}>
          <button className="icon-btn" aria-label="Close" onClick={back} style={{ marginLeft: -10 }}><Icon name="close" /></button>
          <h1 className="title-sm">What did you eat?</h1>
        </div>

        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }} role="group" aria-label="Meal">
          {MEALS.map((m) => <button key={m.key} className="pill" aria-pressed={meal === m.key} onClick={() => setParam('meal', m.key)}>{m.label}</button>)}
        </div>

        <div className="seg" role="tablist" aria-label="How to log" style={{ padding: 4, borderRadius: 14 }}>
          {MODE_TABS.map((t) => (
            <button key={t.key} role="tab" aria-selected={mode === t.key} aria-pressed={mode === t.key} onClick={() => setParam('mode', t.key)}
              style={{ height: 54, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, fontSize: 12 }}>
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        {needsKey && (
          <div className="note warn" style={{ margin: 0 }}>
            <Icon name="info" size={18} />
            <span>Typing, voice and photo logging need a Gemini key. <Link to="/profile#ai">Add your key in Profile</Link> (it stays on this device), or use Search.</span>
          </div>
        )}

        {mode === 'type' && !needsKey && (
          <form className="stack" style={{ gap: 10 }} onSubmit={(e) => { e.preventDefault(); if (text.trim()) analyse({ text: text.trim() }, 'text') }}>
            <label className="field">Write it like you'd tell a friend. Hindi, English or Hinglish.
              <textarea className="input" rows={4} style={{ height: 'auto', padding: '12px 14px', fontWeight: 500, lineHeight: 1.5, resize: 'none' }}
                placeholder="2 roti ghee wali, 1 katori dal tadka, thodi aloo gobhi aur salad" value={text} onChange={(e) => setText(e.target.value)} />
            </label>
            <button className="btn" type="submit" disabled={!text.trim() || Boolean(busy)}>{busy || 'Work out nutrition'}</button>
          </form>
        )}

        {mode === 'speak' && !needsKey && (
          <div className="stack" style={{ gap: 12, alignItems: 'center' }}>
            {!speechSupported() ? (
              <p className="note warn" style={{ margin: 0 }}><Icon name="info" size={18} /><span>Voice input isn't supported in this browser. Try Chrome, or use Type.</span></p>
            ) : (
              <>
                <div className="seg" role="group" aria-label="Language" style={{ width: '100%' }}>
                  <button aria-pressed={lang === 'en-IN'} onClick={() => setLang('en-IN')} disabled={Boolean(listening)}>English / Hinglish</button>
                  <button aria-pressed={lang === 'hi-IN'} onClick={() => setLang('hi-IN')} disabled={Boolean(listening)}>हिंदी</button>
                </div>
                <button onClick={toggleListening} aria-label={listening ? 'Stop listening' : 'Start listening'}
                  style={{ width: 96, height: 96, borderRadius: '50%', border: 0, cursor: 'pointer', background: listening ? 'var(--danger)' : 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {listening ? <span style={{ width: 28, height: 28, borderRadius: 6, background: '#fff' }} /> : <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>}
                </button>
                <span className="small muted">{listening ? 'Listening… tap to stop' : 'Tap and say what you ate, with amounts'}</span>
                <textarea className="input" rows={3} aria-label="What you said" style={{ height: 'auto', padding: '12px 14px', lineHeight: 1.5, resize: 'none' }}
                  placeholder={'"Do roti, ek katori dal, thoda chawal"'} value={text} onChange={(e) => setText(e.target.value)} />
                <button className="btn" disabled={!text.trim() || Boolean(listening) || Boolean(busy)} onClick={() => analyse({ text: text.trim() }, 'voice')}>{busy || 'Work out nutrition'}</button>
              </>
            )}
          </div>
        )}

        {mode === 'photo' && !needsKey && (
          <div className="stack" style={{ gap: 12 }}>
            <p className="note" style={{ margin: 0 }}><Icon name="info" size={18} /><span>Shoot from above with a spoon or your katori in frame; it helps judge portions. You'll check every item before it's saved.</span></p>
            <label className="field">Anything the photo won't show? (optional)
              <input className="input" placeholder="e.g. 2 more roti, cooked in ghee" value={text} onChange={(e) => setText(e.target.value)} />
            </label>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => onPhoto(e.target.files?.[0])} />
            <button className="btn" onClick={() => fileRef.current?.click()} disabled={Boolean(busy)}>{busy || 'Take or choose a photo'}</button>
          </div>
        )}

        {mode === 'search' && <FoodPicker onPick={openFood} />}

        {error && <p className="error" role="alert">{error}</p>}

        {mode !== 'search' && (
          <div className="stack">
            <h2 className="section-label">Quick add</h2>
            <div className="card list">
              {yesterday && (
                <button className="list-row" onClick={copyYesterday} disabled={Boolean(busy)}>
                  <span className="grow stack" style={{ gap: 2 }}>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>Same as yesterday's {mealLabel.toLowerCase()}</span>
                    <span className="xsmall muted">{yesterday.count} item{yesterday.count > 1 ? 's' : ''}</span>
                  </span>
                  <span className="num" style={{ fontWeight: 700, fontSize: 13 }}>{kcal(yesterday.kcal)} kcal</span>
                </button>
              )}
              {recent.map((r) => (
                <button key={r.food_id} className="list-row" onClick={() => openRecent(r)}>
                  <span className="grow stack" style={{ gap: 2 }}>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{r.food_name}</span>
                    <span className="xsmall muted">Recent · {qty(r.quantity)} {unitLabel(r.unit, r.serving_unit)}</span>
                  </span>
                  <span className="num" style={{ fontWeight: 700, fontSize: 13 }}>{kcal(r.energy_kcal)} kcal</span>
                </button>
              ))}
              <Link to="/recipes" className="list-row">
                <span className="grow" style={{ fontWeight: 700, fontSize: 14 }}>My recipes</span>
                <Icon name="forward" size={18} />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
