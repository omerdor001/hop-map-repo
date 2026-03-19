import { useState } from "react"

const timelineEvents = [
  {
    time: "19:20",
    title: "Session started — Roblox",
    risk: "SAFE",
    icon: "🎮",
    iconBg: "#3B2D8C",
    detail: ["Opened ", <b key="a">Roblox desktop app</b>, " · Moderated platform · Age-appropriate"],
    platform: "Roblox",
  },
  {
    time: "19:45",
    title: "Browsed roblox.com",
    risk: "SAFE",
    icon: "🌐",
    iconBg: "#1A3A5C",
    detail: ["Visited ", <b key="b">roblox.com/games</b>, " · In-platform navigation · No external links"],
    platform: "Roblox",
  },
  {
    time: "20:12",
    title: "Opened YouTube",
    risk: "SAFE",
    icon: "▶",
    iconBg: "#8B1A1A",
    detail: ["Navigated to ", <b key="c">youtube.com</b>, " · SafeSearch enabled · Gaming content"],
    platform: "YouTube",
  },
  {
    time: "21:08",
    title: "Switched to Discord (personal)",
    risk: "MEDIUM",
    icon: "💬",
    iconBg: "#2D2060",
    detail: ["Opened ", <b key="d">Discord desktop</b>, " · Known friends server · Monitored by school community"],
    platform: "Discord",
  },
  {
    time: "21:34",
    title: "HOP DETECTED — External server invite",
    risk: "HIGH",
    icon: "🚨",
    iconBg: "#3D1A1A",
    detail: ["Followed link from Roblox chat → ", <b key="e">discord.gg/xR9k2mP</b>, " · Unknown server · No age verification · No moderation policy"],
    platform: "Discord",
  },
]

const typeConfig = {
  SAFE:   { label: "SAFE",      color: "#2ed573", bg: "rgba(46,213,115,0.13)"  },
  MEDIUM: { label: "WARNING",   color: "#ffa502", bg: "rgba(255,165,2,0.13)"   },
  HIGH:   { label: "HIGH RISK", color: "#ff4757", bg: "rgba(255,71,87,0.13)"   },
}

function Dot({ color, pulse }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: 9, height: 9, flexShrink: 0 }}>
      {pulse && <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: color, animation: "ping 1.8s ease-out infinite", opacity: 0.7 }} />}
      <span style={{ position: "absolute", inset: 1, borderRadius: "50%", background: color }} />
    </span>
  )
}

function Badge({ risk }) {
  const c = typeConfig[risk]
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: "0.07em",
      color: c.color, background: c.bg,
      border: `1px solid ${c.color}33`, borderRadius: 4, padding: "2px 6px",
      fontFamily: "'IBM Plex Mono',monospace", whiteSpace: "nowrap",
    }}>{c.label}</span>
  )
}

export default function Alerts() {
  const [selectedDate, setSelectedDate] = useState("19/03/2026")

  const handleDateChange = (e) => {
    let val = e.target.value.replace(/[^\d/]/g, "")
    if (val.length === 2 && !val.includes("/")) val += "/"
    if (val.length === 5 && val.split("/").length - 1 === 1) val += "/"
    if (val.length > 10) return
    setSelectedDate(val)
  }

  const parseDate = (str) => {
    const [dd, mm, yyyy] = str.split("/")
    return `${yyyy}-${mm}-${dd}`
  }

  const fetchSessionData = (date) => {
    const isoDate = parseDate(date)
    console.log("Fetching session data for:", isoDate)
  }

  const high = timelineEvents.filter(e => e.risk === "HIGH").length
  const med  = timelineEvents.filter(e => e.risk === "MEDIUM").length
  const safe = timelineEvents.filter(e => e.risk === "SAFE").length

  return (
    <div style={{
      width: "100%", height: "100vh", background: "#0d0f14", color: "#e8eaf0",
      fontFamily: "'IBM Plex Sans',sans-serif", display: "flex", flexDirection: "column", overflow: "hidden",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');
        *{box-sizing:border-box;margin:0;padding:0;}
        @keyframes ping{0%{transform:scale(1);opacity:.7}70%{transform:scale(2.2);opacity:0}100%{transform:scale(1);opacity:0}}
        @keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
        .ev-row:hover{background:rgba(255,255,255,0.03)!important;cursor:pointer;}
        ::-webkit-scrollbar{width:3px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#2a2d38;border-radius:2px}
      `}</style>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "24px 32px", gap: 16, overflow: "hidden" }}>

        {/* Page title */}
        <div style={{ animation: "in 0.4s ease" }}>
          <div style={{ fontSize: 10, color: "#4b5268", fontFamily: "'IBM Plex Mono',monospace", letterSpacing: "0.1em", marginBottom: 3 }}>MONITOR</div>
          <h1 style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>Session Timeline</h1>
          <p style={{ fontSize: 11, color: "#4b5268", marginTop: 2 }}>Today, March 19 · Yonatan's session · <span style={{ color: "#ff4757" }}>● LIVE</span></p>
        </div>

        {/* Stat cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 11, flexShrink: 0, animation: "in 0.35s ease 0.05s both" }}>
          {[
            { label: "HIGH RISK", val: high, color: "#ff4757", sub: "Hops detected" },
            { label: "WARNINGS",  val: med,  color: "#ffa502", sub: "Medium risk events" },
            { label: "ALL CLEAR", val: safe, color: "#2ed573", sub: "Safe events" },
          ].map(s => (
            <div key={s.label} style={{ background: "#111318", border: "1px solid #1e2130",
              borderTop: `3px solid ${s.color}`, borderRadius: 10, padding: "12px 14px" }}>
              <div style={{ fontSize: 9, color: "#4b5268", letterSpacing: "0.1em",
                fontFamily: "'IBM Plex Mono',monospace", marginBottom: 5 }}>{s.label}</div>
              <div style={{ fontSize: 30, fontWeight: 700, color: s.color, lineHeight: 1,
                fontFamily: "'IBM Plex Mono',monospace", marginBottom: 3 }}>{s.val}</div>
              <div style={{ fontSize: 10, color: "#4b5268" }}>{s.sub}</div>
            </div>
          ))}
        </div>

        {/* Timeline header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0, animation: "in 0.35s ease 0.1s both" }}>
          <span style={{ fontSize: 11, fontWeight: 700, fontFamily: "'IBM Plex Mono',monospace", letterSpacing: "0.1em" }}>
            SESSION TIMELINE
          </span>
          <span style={{ fontSize: 9, fontWeight: 700, color: "#ff4757",
            background: "rgba(255,71,87,0.13)", border: "1px solid rgba(255,71,87,0.28)",
            borderRadius: 4, padding: "2px 6px", fontFamily: "'IBM Plex Mono',monospace" }}>● LIVE</span>

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: "#4b5268", fontFamily: "'IBM Plex Mono',monospace" }}>Data from</span>
            <input
              type="text"
              value={selectedDate}
              onChange={handleDateChange}
              placeholder="DD/MM/YYYY"
              maxLength={10}
              style={{
                background: "#111318", border: "1px solid #1e2130",
                borderRadius: 7, padding: "5px 10px", color: "#e8eaf0",
                fontSize: 11, fontFamily: "'IBM Plex Mono',monospace",
                outline: "none", width: 100, letterSpacing: "0.05em",
              }}
            />
            <span style={{ fontSize: 11, color: "#4b5268", fontFamily: "'IBM Plex Mono',monospace" }}>backwards</span>
            <button
              onClick={() => fetchSessionData(selectedDate)}
              style={{
                padding: "5px 13px", borderRadius: 6, border: "none", cursor: "pointer",
                fontSize: 11, fontWeight: 700, letterSpacing: "0.05em",
                background: "#6366f1", color: "#fff",
              }}
            >GO</button>
          </div>
        </div>

        {/* Timeline events */}
        <div style={{ flex: 1, background: "#111318", border: "1px solid #1e2130",
          borderRadius: 10, overflowY: "auto", animation: "in 0.35s ease 0.15s both" }}>
          {timelineEvents.map((ev, i) => (
  <div key={i} className="ev-row" style={{
    display: "flex", alignItems: "center", gap: 11, padding: "10px 15px",
    borderBottom: i < timelineEvents.length - 1 ? "1px solid #1a1d28" : "none",
    background: ev.risk === "HIGH" ? "rgba(255,71,87,0.04)" : "transparent",
    transition: "background 0.15s",
  }}>
    <Dot color={typeConfig[ev.risk].color} pulse={ev.risk === "HIGH"} />
    <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11,
      color: "#4b5268", minWidth: 34, flexShrink: 0 }}>{ev.time}</span>

    {/* ✅ Child avatar */}
    <div style={{ width: 24, height: 24, borderRadius: "50%",
      background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 8, fontWeight: 700, color: "#fff", flexShrink: 0 }}>YS</div>

    <div style={{ width: 28, height: 28, borderRadius: 7, background: ev.iconBg,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 13, flexShrink: 0 }}>{ev.icon}</div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 2 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#e8eaf0",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 360 }}>{ev.title}</span>
        <Badge risk={ev.risk} />
      </div>
      <div style={{ fontSize: 11, color: "#4b5268" }}>{ev.detail}</div>
    </div>
  </div>
))}


        </div>

      </div>
    </div>
  )
}