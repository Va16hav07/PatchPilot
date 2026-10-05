/**
 * Light / dark theme. "system" follows the device; the choice is a per-device
 * preference kept in localStorage. index.html applies it before first paint.
 */
import { useEffect, useState } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'

const KEY = 'thali.theme'
const META_COLOR = { light: '#1E6A48', dark: '#0f1512' }

export function getThemeChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

const media = () => window.matchMedia('(prefers-color-scheme: dark)')

export function isDark(choice: ThemeChoice = getThemeChoice()): boolean {
  return choice === 'dark' || (choice === 'system' && media().matches)
}

function apply(choice: ThemeChoice) {
  const root = document.documentElement
  if (choice === 'system') delete root.dataset.theme
  else root.dataset.theme = choice
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', META_COLOR[isDark(choice) ? 'dark' : 'light'])
}

export function setThemeChoice(choice: ThemeChoice) {
  try {
    if (choice === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, choice)
  } catch {
    // storage blocked: the choice lasts for this page load only
  }
  apply(choice)
  window.dispatchEvent(new Event('thali-theme'))
}

/** Current effective darkness, updating on device or user changes. */
export function useIsDark(): boolean {
  const [dark, setDark] = useState(isDark)
  useEffect(() => {
    const update = () => {
      apply(getThemeChoice())
      setDark(isDark())
    }
    const m = media()
    m.addEventListener('change', update)
    window.addEventListener('thali-theme', update)
    return () => {
      m.removeEventListener('change', update)
      window.removeEventListener('thali-theme', update)
    }
  }, [])
  return dark
}
