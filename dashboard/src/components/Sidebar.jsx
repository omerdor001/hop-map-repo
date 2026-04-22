import { useNavigate, useLocation } from "react-router-dom"
import { colors, fonts } from "../utils/theme"

const sideNav = [
  { section: "MONITOR", items: [
    { icon: "🗺️", label: "Live Map", path: "/" },
  ]},
  { section: "ACCOUNT", items: [
    { icon: "👦", label: "Kids",  path: "/kids"  },
    { icon: "💳", label: "Plan",  path: "/plan"  },
  ]},
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <aside style={{
      width: 240, background: colors.surface, borderRight: `1px solid ${colors.border}`,
      display: "flex", flexDirection: "column", padding: "28px 0", flexShrink: 0,
      fontFamily: fonts.sans,
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 20px 28px" }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: "linear-gradient(135deg, #6366f1, #818cf8)",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
        }}>🛡️</div>
        <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em" }}>
          <span style={{ color: colors.text }}>Hop</span>{" "}
          <span style={{ color: colors.indigoLight }}>Map</span>
        </span>
      </div>

      {/* Nav */}
      {sideNav.map((group) => (
        <div key={group.section} style={{ marginBottom: 24 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
            color: colors.muted, padding: "0 20px 8px",
            fontFamily: fonts.mono,
          }}>{group.section}</div>

          {group.items.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <button key={item.label} onClick={() => navigate(item.path)} style={{
                display: "flex", alignItems: "center", gap: 10,
                width: "100%", padding: "9px 20px", border: "none", cursor: "pointer",
                background: isActive ? "rgba(99,102,241,0.15)" : "transparent",
                borderLeft: isActive ? `3px solid ${colors.indigo}` : "3px solid transparent",
                color: isActive ? colors.indigoLight : colors.muted,
                fontSize: 14, fontWeight: isActive ? 600 : 400,
                transition: "all 0.15s", textAlign: "left",
                fontFamily: fonts.sans,
              }}>
                <span style={{ fontSize: 15 }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
              </button>
            )
          })}
        </div>
      ))}
    </aside>
  )
}
