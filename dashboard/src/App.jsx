import { BrowserRouter, Routes, Route } from "react-router-dom"
import { AuthProvider, useAuth } from "./context/AuthContext"
import { ChildrenProvider } from "./context/ChildrenContext"
import Sidebar from "./components/Sidebar"
import Homepage from "./components/Homepage"
import Kids from "./components/Kids"
import Login from "./components/Login"
import Plan from "./components/Plan"
import Settings from "./components/Settings"
import styles from "./App.module.css"

function Dashboard() {
  return (
    <ChildrenProvider>
      <div className={styles.shell}>
        <Sidebar />
        <div className={styles.content}>
          <Routes>
            <Route path="/" element={<Homepage />} />
            <Route path="/kids" element={<Kids />} />
            <Route path="/plan" element={<Plan />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </div>
    </ChildrenProvider>
  )
}

function AppRoutes() {
  const { accessToken, loading } = useAuth()

  if (loading) {
    return <div className={styles.loading}>Loading…</div>
  }

  if (!accessToken) return <Login />

  return <Dashboard />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
