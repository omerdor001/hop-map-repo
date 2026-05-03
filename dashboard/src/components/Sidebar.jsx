import { useNavigate, useLocation } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import styles from "./Sidebar.module.css"

const sideNav = [
  { section: "MONITOR", items: [
    { icon: "🗺️", label: "Live Map", path: "/" },
  ]},
  { section: "ACCOUNT", items: [
    { icon: "👦", label: "Kids",     path: "/kids"     },
    { icon: "💳", label: "Plan",     path: "/plan"     },
    { icon: "⚙️", label: "Settings", path: "/settings" },
  ]},
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { logout } = useAuth()

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <div className={styles.logoIcon}>🛡️</div>
        <span className={styles.logoText}>
          <span className={styles.logoMain}>Hop</span>{" "}
          <span className={styles.logoAccent}>Map</span>
        </span>
      </div>

      {sideNav.map((group) => (
        <div key={group.section} className={styles.navGroup}>
          <span className={styles.navGroupLabel}>{group.section}</span>

          {group.items.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <button
                key={item.label}
                onClick={() => navigate(item.path)}
                className={isActive ? `${styles.navBtn} ${styles.navBtnActive}` : styles.navBtn}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span className={styles.navLabel}>{item.label}</span>
              </button>
            )
          })}
        </div>
      ))}

      <div className={styles.footer}>
        <div className={styles.divider} />
        <button onClick={logout} className={styles.signOutBtn}>
          <span className={styles.navIcon}>→</span>
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  )
}
