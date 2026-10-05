import { GoogleLogin } from '@react-oauth/google'
import { useState } from 'react'
import { useAuth } from '../auth'
import { useIsDark } from '../theme'

const configured = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID)

export default function SignIn() {
  const { signIn } = useAuth()
  const [error, setError] = useState('')
  const dark = useIsDark()

  return (
    <div className="screen" style={{ position: 'relative', overflow: 'hidden' }}>
      <div aria-hidden="true">
        <div style={{ position: 'absolute', right: -120, top: 150, width: 360, height: 360, borderRadius: '50%', background: 'var(--deco-1)' }} />
        <div style={{ position: 'absolute', right: -40, top: 230, width: 200, height: 200, borderRadius: '50%', background: 'var(--deco-2)', border: '2px solid var(--deco-2-line)' }} />
        <div style={{ position: 'absolute', right: 70, top: 255, width: 64, height: 64, borderRadius: '50%', background: 'var(--deco-turmeric)' }} />
        <div style={{ position: 'absolute', right: 10, top: 320, width: 70, height: 70, borderRadius: '50%', background: 'var(--deco-leaf)' }} />
        <div style={{ position: 'absolute', right: 90, top: 335, width: 52, height: 52, borderRadius: '50%', background: 'var(--deco-clay)' }} />
      </div>
      <div className="content" style={{ padding: '64px 28px 40px', position: 'relative' }}>
        <div className="row">
          <img src="/icon.svg" width={36} height={36} alt="" style={{ borderRadius: 10 }} />
          <span style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: 22 }}>Thali</span>
        </div>
        <div className="stack" style={{ marginTop: 'auto', gap: 16 }}>
          <h1 style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: 40, lineHeight: 1.05, letterSpacing: -1 }}>
            Know what's on your plate, katori by katori.
          </h1>
          <p style={{ margin: 0, fontSize: 16, lineHeight: 1.5, color: 'var(--ink-3)' }}>
            Nutrition for Indian meals, from the official Indian food tables (ICMR-NIN).
          </p>
        </div>
        <div className="stack" style={{ marginTop: 32, gap: 14, alignItems: 'center' }}>
          {configured ? (
            <GoogleLogin
              onSuccess={async (res) => {
                setError('')
                if (!res.credential) return setError('Google did not return a credential.')
                try {
                  await signIn(res.credential)
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'Sign-in failed')
                }
              }}
              onError={() => setError('Google sign-in was cancelled or failed.')}
              text="continue_with"
              theme={dark ? 'filled_black' : 'outline'}
              key={dark ? 'dark' : 'light'}
              shape="pill"
              size="large"
              width="334"
            />
          ) : (
            <p className="note warn" style={{ margin: 0 }}>
              Google sign-in isn't configured. Set VITE_GOOGLE_CLIENT_ID in frontend/.env.local.
            </p>
          )}
          {error && <p className="error" role="alert">{error}</p>}
          <p className="small muted" style={{ textAlign: 'center', margin: 0 }}>
            Google sign-in only. No passwords to remember.
          </p>
        </div>
      </div>
    </div>
  )
}
