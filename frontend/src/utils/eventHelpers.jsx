/**
 * Shared helpers used by both the Homepage timeline and the Alerts timeline.
 * Centralised here to follow the DRY principle and keep each component focused
 * on layout rather than data-mapping logic.
 */

export const AVATAR_GRADS = [
  "linear-gradient(135deg,#6366f1,#8b5cf6)",
  "linear-gradient(135deg,#f43f5e,#fb7185)",
  "linear-gradient(135deg,#0ea5e9,#38bdf8)",
  "linear-gradient(135deg,#10b981,#34d399)",
  "linear-gradient(135deg,#f59e0b,#fbbf24)",
]

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

/**
 * @param {object} event
 * @param {string} [fallback] - Shown when no reason/context/from are available.
 */
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
  const d  = new Date()
  const dd = String(d.getDate()).padStart(2, "0")
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  return `${dd}/${mm}/${d.getFullYear()}`
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
