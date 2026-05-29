import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import Explore from './pages/Explore'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

function ProtectedRoute({ children }) {
  const { session, loading } = useAuth()
  if (loading) {
    return <FullPageStatus>LOADING...</FullPageStatus>
  }
  if (!session) return <Navigate to="/" replace />
  return children
}

function FullPageStatus({ children }) {
  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', color: 'var(--muted)', fontSize: '0.75rem', letterSpacing: '0.14em' }}>
      {children}
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth
      .getSession()
      .then(({ data: { session } }) => {
        setSession(session)
      })
      .catch((error) => {
        console.error('Failed to read Supabase session', error)
      })
      .finally(() => {
        setLoading(false)
      })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  if (loading) {
    return <FullPageStatus>LOADING...</FullPageStatus>
  }

  return (
    <AuthContext.Provider value={{ session, loading }}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={session ? <Navigate to="/dashboard" replace /> : <Landing />} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/explore" element={<ProtectedRoute><Explore /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to={session ? '/dashboard' : '/'} replace />} />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  )
}
