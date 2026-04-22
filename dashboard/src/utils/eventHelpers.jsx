import { colors, fonts } from "./theme"

export const AVATAR_GRADS = [
  "linear-gradient(135deg,#6366f1,#8b5cf6)",
  "linear-gradient(135deg,#f43f5e,#fb7185)",
  "linear-gradient(135deg,#0ea5e9,#38bdf8)",
  "linear-gradient(135deg,#10b981,#34d399)",
  "linear-gradient(135deg,#f59e0b,#fbbf24)",
]

// Severity → display config used by Badge and the Alerts timeline.
export const typeConfig = {
  SAFE:   { label: "SAFE",      color: colors.success, bg: "rgba(46,213,115,0.13)"  },
  MEDIUM: { label: "WARNING",   color: colors.warning,  bg: "rgba(255,165,2,0.13)"   },
  HIGH:   { label: "HIGH RISK", color: colors.danger,   bg: "rgba(255,71,87,0.13)"   },
}

export function getInitials(name) {
  if (!name) return "??"
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

export function getAppIcon(to) {
  if (!to) return { icon: "📱", bg: "#1a1d28" }
  const t = to.toLowerCase()
  if (t.includes("roblox"))                                          return { icon: "🎮", bg: "#3B2D8C" }
  if (t.includes("minecraft") || t.includes("javaw"))               return { icon: "⛏",  bg: "#2D4A1E" }
  if (t.includes("fortnite"))                                        return { icon: "🎯", bg: "#1A3A5C" }
  if (t.includes("youtube"))                                         return { icon: "▶",  bg: "#8B1A1A" }
  if (t.includes("discord"))                                         return { icon: "💬", bg: "#2D2060" }
  if (t.includes("telegram"))                                        return { icon: "✈️", bg: "#1A4A5C" }
  if (t.includes("whatsapp"))                                        return { icon: "💚", bg: "#1A3A2A" }
  if (t.includes("instagram"))                                       return { icon: "📸", bg: "#4A1A3A" }
  if (t.includes("tiktok"))                                          return { icon: "🎵", bg: "#1A1A2A" }
  if (t.includes("steam"))                                           return { icon: "🎮", bg: "#1A2D3A" }
  if (t.includes("chrome") || t.includes("msedge") ||
      t.includes("firefox") || t.includes("brave"))                 return { icon: "🌐", bg: "#1A3A5C" }
  if (t.startsWith("http"))                                          return { icon: "🌐", bg: "#1A3A5C" }
  return { icon: "📱", bg: "#1a1d28" }
}

export function getEventDesc(event, fallback = "App switch detected") {
  if (event.classifyReason && event.classifyReason !== "server_unreachable") return event.classifyReason
  if (event.context) return String(event.context).replace(/^\[clipboard\] /, "")
  if (event.from)    return `${event.from} → ${event.to || "—"}`
  return fallback
}

export function getEventTitle(event) {
  if (event.alertReason === "confirmed_hop") return `HOP DETECTED — ${event.toTitle || event.to || "external link"}`
  if (event.alertReason === "blacklisted")   return `BLOCKED — ${event.toTitle || event.to || "app"}`
  if (event.alertReason === "parent_rule")   return `Rule triggered — ${event.toTitle || event.to}`
  return event.toTitle || event.to || "App switch"
}

export function getSeverity(event) {
  if (!event.alert) return "SAFE"
  if (event.alertReason === "confirmed_hop" || event.alertReason === "blacklisted") return "HIGH"
  return "MEDIUM"
}

export function todayDefault() {
  const d = new Date()
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-")
}

export function Badge({ risk }) {
  const c = typeConfig[risk]
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: "0.07em",
      color: c.color, background: c.bg,
      border: `1px solid ${c.color}33`,
      borderRadius: 4, padding: "2px 6px",
      fontFamily: fonts.mono, whiteSpace: "nowrap",
    }}>{c.label}</span>
  )
}

export function StatCard({ label, val, color, sub }) {
  return (
    <div style={{
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      borderTop: `3px solid ${color}`,
      borderRadius: 10, padding: "12px 14px",
    }}>
      <div style={{
        fontSize: 9, color: colors.muted, letterSpacing: "0.1em",
        fontFamily: fonts.mono, marginBottom: 5,
      }}>{label}</div>
      <div style={{
        fontSize: 30, fontWeight: 700, color, lineHeight: 1,
        fontFamily: fonts.mono, marginBottom: 3,
      }}>{val}</div>
      <div style={{ fontSize: 10, color: colors.muted }}>{sub}</div>
    </div>
  )
}

export function Dot({ color, pulse }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: 9, height: 9, flexShrink: 0 }}>
      {pulse && (
        <span style={{
          position: "absolute", inset: 0, borderRadius: "50%",
          background: color, animation: "ping 1.8s ease-out infinite", opacity: 0.7,
        }} />
      )}
      <span style={{ position: "absolute", inset: 1, borderRadius: "50%", background: color }} />
    </span>
  )
}
