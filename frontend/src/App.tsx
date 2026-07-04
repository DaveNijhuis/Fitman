import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { getToken } from './api/client'
import { checkSetupRequired } from './api/auth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import SetupPage from './pages/SetupPage'
import HomePage from './pages/HomePage'
import ActiveWorkoutPage from './pages/ActiveWorkoutPage'
import HistoryPage from './pages/HistoryPage'
import WorkoutDetailPage from './pages/WorkoutDetailPage'
import ProgressPage from './pages/ProgressPage'
import LibraryPage from './pages/LibraryPage'
import CardioPage from './pages/CardioPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!Boolean(getToken())) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  const [setupRequired, setSetupRequired] = useState<boolean | null>(null)

  useEffect(() => {
    checkSetupRequired()
      .then(setSetupRequired)
      .catch(() => setSetupRequired(false))
  }, [])

  // Brief check on startup — return nothing to avoid flash
  if (setupRequired === null) return null

  // First-run: show setup for all routes until account is created
  if (setupRequired) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="*" element={<SetupPage />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<Navigate to="/" replace />} />
        <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
        <Route path="/workout/:sessionId" element={<ProtectedRoute><ActiveWorkoutPage /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute><HistoryPage /></ProtectedRoute>} />
        <Route path="/history/:sessionId" element={<ProtectedRoute><WorkoutDetailPage /></ProtectedRoute>} />
        <Route path="/progress" element={<ProtectedRoute><ProgressPage /></ProtectedRoute>} />
        <Route path="/library" element={<ProtectedRoute><LibraryPage /></ProtectedRoute>} />
        <Route path="/cardio" element={<ProtectedRoute><CardioPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to={Boolean(getToken()) ? '/' : '/login'} replace />} />
      </Routes>
    </BrowserRouter>
  )
}
