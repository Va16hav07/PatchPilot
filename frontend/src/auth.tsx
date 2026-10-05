import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError } from './api'
import type { User } from './types'

interface AuthState {
  user: User | null
  loading: boolean
  setUser: (u: User | null) => void
  signIn: (credential: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .get<User>('/api/me')
      .then(setUser)
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 401)) console.error(e)
      })
      .finally(() => setLoading(false))
  }, [])

  const signIn = useCallback(async (credential: string) => {
    setUser(await api.post<User>('/api/auth/google', { credential }))
  }, [])

  const signOut = useCallback(async () => {
    await api.post('/api/auth/logout')
    setUser(null)
  }, [])

  return <AuthContext.Provider value={{ user, loading, setUser, signIn, signOut }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}

/** For pages behind the auth guard. */
export function useUser(): User {
  const { user } = useAuth()
  if (!user) throw new Error('useUser without a signed-in user')
  return user
}
