import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Insights from './pages/Insights'
import LogMeal from './pages/LogMeal'
import Portion from './pages/Portion'
import Profile from './pages/Profile'
import { RecipeEditor, RecipeList } from './pages/Recipes'
import Review from './pages/Review'
import Setup from './pages/Setup'
import SetupAi from './pages/SetupAi'
import SignIn from './pages/SignIn'
import Today from './pages/Today'

function Guard({ children, needsProfile = true }: { children: ReactNode; needsProfile?: boolean }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/signin" replace state={{ from: location.pathname }} />
  if (needsProfile && !user.profile) return <Navigate to="/setup" replace />
  return children
}

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <div className="screen center muted">Loading…</div>
  return (
    <Routes>
      <Route path="/signin" element={user ? <Navigate to="/" replace /> : <SignIn />} />
      <Route path="/setup" element={<Guard needsProfile={false}><Setup /></Guard>} />
      <Route path="/" element={<Guard><Today /></Guard>} />
      <Route path="/log" element={<Guard><LogMeal /></Guard>} />
      <Route path="/setup/ai" element={<Guard><SetupAi /></Guard>} />
      <Route path="/log/food/:foodId" element={<Guard><Portion /></Guard>} />
      <Route path="/log/review" element={<Guard><Review /></Guard>} />
      <Route path="/recipes" element={<Guard><RecipeList /></Guard>} />
      <Route path="/recipes/new" element={<Guard><RecipeEditor /></Guard>} />
      <Route path="/recipes/:recipeId" element={<Guard><RecipeEditor /></Guard>} />
      <Route path="/insights" element={<Guard><Insights /></Guard>} />
      <Route path="/profile" element={<Guard><Profile /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
