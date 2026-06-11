import { Navigate, Outlet } from "react-router-dom"
import { useAuth } from "../../context/AuthContext"

export default function RequireAuth() {
  const { accessToken, loading } = useAuth()

  if (loading) {
    return (
      <div className="auth-loading">
        <span>Loading…</span>
      </div>
    )
  }

  if (!accessToken) return <Navigate to="/login" replace />

  return <Outlet />
}
