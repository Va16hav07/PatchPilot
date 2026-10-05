import { useEffect, useState, type FormEvent } from 'react'
import { aiStatus, getDeviceKey, setDeviceKey, testKey } from '../ai/gemini'
import Icon from './Icon'

/** Add, test and remove the user's own Gemini key. The key is stored only in this browser. */
export default function GeminiKeyCard({ onSaved }: { onSaved?: () => void }) {
  const [saved, setSaved] = useState<string | null>(getDeviceKey())
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null)
  const [serverKey, setServerKey] = useState(false)

  useEffect(() => {
    aiStatus().then((s) => setServerKey(s.server_key))
  }, [])

  async function save(e: FormEvent) {
    e.preventDefault()
    const key = draft.trim()
    if (!key) return
    setBusy(true)
    setMessage(null)
    const problem = await testKey(key)
    if (problem) {
      setMessage({ text: problem, ok: false })
    } else {
      try {
        setDeviceKey(key)
        setSaved(key)
        setDraft('')
        setMessage({ text: 'Key works and is saved on this device.', ok: true })
        onSaved?.()
      } catch (err) {
        setMessage({ text: err instanceof Error ? err.message : 'Could not save', ok: false })
      }
    }
    setBusy(false)
  }

  async function retest() {
    if (!saved) return
    setBusy(true)
    const problem = await testKey(saved)
    setMessage(problem ? { text: problem, ok: false } : { text: 'Key works.', ok: true })
    setBusy(false)
  }

  function remove() {
    setDeviceKey(null)
    setSaved(null)
    setMessage({ text: 'Key removed from this device.', ok: true })
  }

  return (
    <div className="card pad stack" style={{ gap: 12 }}>
      <p className="small" style={{ margin: 0, lineHeight: 1.5, color: 'var(--ink-2)' }}>
        Gemini reads what you type, say or photograph and works out which foods and portions you mean. The nutrition numbers
        still come from the food database.
      </p>
      <p className="note" style={{ margin: 0 }}>
        <Icon name="info" size={18} />
        <span>Your key is stored only in this browser on this device. It is sent only to Google, never to our server or database.</span>
      </p>

      {saved ? (
        <div className="row between" style={{ flexWrap: 'wrap' }}>
          <span className="small num" style={{ fontWeight: 700 }}>Key saved: ••••{saved.slice(-4)}</span>
          <div className="row" style={{ gap: 4 }}>
            <button type="button" className="link-btn" onClick={retest} disabled={busy}>Test</button>
            <button type="button" className="link-btn" style={{ color: 'var(--danger)' }} onClick={remove} disabled={busy}>Remove</button>
          </div>
        </div>
      ) : (
        <span className="small muted">
          {serverKey ? 'No key on this device: the app’s shared key is used, which has a daily limit.' : 'No key on this device yet. AI logging needs one.'}
        </span>
      )}

      <form className="stack" style={{ gap: 8 }} onSubmit={save}>
        <label className="field">{saved ? 'Replace key' : 'Your Gemini API key'}
          <input className="input" type="password" autoComplete="off" spellCheck={false} placeholder="AIza…" value={draft} onChange={(e) => setDraft(e.target.value)} />
        </label>
        <button className="btn small" type="submit" disabled={busy || !draft.trim()}>{busy ? 'Checking with Google…' : 'Test and save'}</button>
      </form>
      {message && <p className={message.ok ? 'small' : 'error'} role="status" style={{ margin: 0, color: message.ok ? 'var(--accent-ink)' : undefined }}>{message.text}</p>}
      <span className="xsmall muted">
        Get a free key at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>.
      </span>
    </div>
  )
}
