import { GoogleOAuthProvider } from '@react-oauth/google'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import './index.css'
import { useIsDark } from './theme'

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''

/** Keeps the theme in sync with the device while the app is open. */
function ThemeSync() {
  useIsDark()
  return null
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={clientId}>
      <AuthProvider>
        <BrowserRouter>
          <ThemeSync />
          <App />
        </BrowserRouter>
      </AuthProvider>
    </GoogleOAuthProvider>
  </StrictMode>,
)
