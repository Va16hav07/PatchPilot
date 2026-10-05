import { useNavigate } from 'react-router-dom'
import GeminiKeyCard from '../components/GeminiKeyCard'

/** Onboarding step 2: optional Gemini key. */
export default function SetupAi() {
  const navigate = useNavigate()
  return (
    <div className="screen">
      <div className="content">
        <div className="stack" style={{ gap: 6 }}>
          <span className="small muted" style={{ fontWeight: 600 }}>Step 2 of 2 · optional</span>
          <h1 className="title">Log meals by typing, voice or photo</h1>
        </div>
        <GeminiKeyCard onSaved={() => navigate('/', { replace: true })} />
        <p className="small muted" style={{ margin: 0 }}>You can skip this and add a key later in Profile. Search-and-pick logging works without it.</p>
      </div>
      <div className="footer">
        <button className="btn secondary" onClick={() => navigate('/', { replace: true })}>Skip for now</button>
      </div>
    </div>
  )
}
