import { useState, useEffect } from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import { AuthProvider, useAuth } from "./context/AuthContext"
import Sidebar from "./components/Sidebar"
import Homepage from "./components/Homepage"
import Kids from "./components/Kids"
import Login from "./components/Login"
import Plan from "./components/Plan"

function Dashboard() {
  const { authFetch, loading: authLoading } = useAuth()
  const [activeId, setActiveId]   = useState(null)
  const [childList, setChildList] = useState([])

  useEffect(() => {
    if (authLoading) return
    authFetch("/api/children")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        const list = (data?.children) || []
        setChildList(list)
        if (list.length > 0) setActiveId(list[0].childId)
      })
      .catch(() => {})
  }, [authLoading, authFetch])

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#0d0d0f" }}>
      <Sidebar />
      <div style={{ flex: 1 }}>
        <Routes>
          <Route path="/" element={<Homepage childList={childList} activeId={activeId} setActiveId={setActiveId} />} />
          <Route path="/kids" element={<Kids setChildList={setChildList} />} />
          <Route path="/plan" element={<Plan />} />
        </Routes>
      </div>
    </div>
  )
}

function AppRoutes() {
  const { accessToken, loading } = useAuth()

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh", background: "#0d0d0f",
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "#6b7280", fontSize: 14,
      }}>
        Loading…
      </div>
    )
  }

  if (!accessToken) return <Login />

  return (
    <BrowserRouter>
      <Dashboard />
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}