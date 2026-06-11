import { NavLink, Link, useNavigate } from "react-router-dom"
import { useAuth } from "../../context/AuthContext"
import logo from "../../assets/hopemap_logo_v3.svg"
import "./AppSidebar.css"

export default function AppSidebar() {
  const { logout } = useAuth()
  const navigate   = useNavigate()

  async function handleLogout() {
    await logout()
    navigate("/login", { replace: true })
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Link to="/" aria-label="Go to home page">
          <img src={logo} alt="HopMap" width={120} />
        </Link>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/app/kids"
          className={({ isActive }) => `sidebar-link${isActive ? " sidebar-link--active" : ""}`}
        >
          <span className="sidebar-icon" aria-hidden="true">👧</span>
          Kids
        </NavLink>

        <NavLink
          to="/app/settings"
          className={({ isActive }) => `sidebar-link${isActive ? " sidebar-link--active" : ""}`}
        >
          <span className="sidebar-icon" aria-hidden="true">⚙</span>
          Settings
        </NavLink>
      </nav>

      <div className="sidebar-bottom">
        <button className="sidebar-logout" onClick={handleLogout}>
          <span className="sidebar-icon" aria-hidden="true">↩</span>
          Logout
        </button>
      </div>
    </aside>
  )
}
