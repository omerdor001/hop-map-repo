
import { useNavigate, useLocation } from "react-router-dom"

const sideNav = [
  { section: "MONITOR", items: [
    { icon: "🗺️", label: "Live Map", path: "/", badge: null },
  ]},
  { section: "ACCOUNT", items: [
    { icon: "👦", label: "Kids",  path: "/kids",  badge: null },
    { icon: "💳", label: "Plan",  path: "/plan",  badge: null },
  ]},
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <aside style={{
      width: 240, background: "#111114", borderRight: "1px solid #1e1e24",
      display: "flex", flexDirection: "column", padding: "28px 0", flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 20px 28px" }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: "linear-gradient(135deg, #6366f1, #818cf8)",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
        }}>🛡️</div>
        <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em" }}>
          <span style={{ color: "#fff" }}>Hop</span>{" "}
          <span style={{ color: "#818cf8" }}>Map</span>
        </span>
      </div>

      {/* Nav */}
      {sideNav.map((group) => (
        <div key={group.section} style={{ marginBottom: 24 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
            color: "#4b5563", padding: "0 20px 8px", textTransform: "uppercase",
          }}>{group.section}</div>

          {group.items.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <button key={item.label} onClick={() => navigate(item.path)} style={{
                display: "flex", alignItems: "center", gap: 10,
                width: "100%", padding: "9px 20px", border: "none", cursor: "pointer",
                background: isActive ? "rgba(99,102,241,0.15)" : "transparent",
                borderLeft: isActive ? "3px solid #6366f1" : "3px solid transparent",
                color: isActive ? "#a5b4fc" : "#9ca3af",
                fontSize: 14, fontWeight: isActive ? 600 : 400,
                transition: "all 0.15s", textAlign: "left",
              }}>
                <span style={{ fontSize: 15 }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.badge && (
                  <span style={{
                    background: "#ef4444", color: "#fff",
                    borderRadius: "50%", width: 18, height: 18, fontSize: 11,
                    display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700,
                  }}>{item.badge}</span>
                )}
              </button>
            )
          })}
        </div>
      ))}
    </aside>
  )
}