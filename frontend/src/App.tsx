import { Suspense, lazy, useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { getToken } from './api/client'
import { checkSetupRequired } from './api/auth'
import { ONBOARDING_FLAG } from './onboarding'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'

// Eager: the two screens that are the first thing anyone sees. Loading these
// lazily would only add a round trip before first paint.
import LoginPage from './pages/LoginPage'
import SetupPage from './pages/SetupPage'
import HomePage from './pages/HomePage'

// Lazy: everything reachable only after a deliberate navigation (#271).
// ProgressPage is the one that matters — it is the sole user of recharts, which
// with its d3, redux-toolkit and immer dependencies is roughly 640 kB of the
// bundle. Loading that on the login screen served nobody.
const ActiveWorkoutPage = lazy(() => import('./pages/ActiveWorkoutPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const WorkoutDetailPage = lazy(() => import('./pages/WorkoutDetailPage'))
const ProgressPage = lazy(() => import('./pages/ProgressPage'))
const LibraryPage = lazy(() => import('./pages/LibraryPage'))
const CardioPage = lazy(() => import('./pages/CardioPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'))

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return (
    <Layout>
      <ErrorBoundary>
        <Suspense fallback={null}>{children}</Suspense>
      </ErrorBoundary>
    </Layout>
  )
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
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
        <Route path="/onboarding" element={getToken() ? <Suspense fallback={null}><OnboardingPage /></Suspense> : <Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to={getToken() ? (localStorage.getItem(ONBOARDING_FLAG) ? '/onboarding' : '/') : '/login'} replace />} />
      </Routes>
    </BrowserRouter>
  )
}
