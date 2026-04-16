import { useState, useEffect, useMemo } from "react"
import {
  AVATAR_GRADS,
  getInitials,
  getAppIcon,
  getEventDesc,
  getEventTitle,
  getSeverity,
  todayDefault,
  Dot,
} from "../utils/eventHelpers"

const typeConfig = {
  SAFE:   { label: "SAFE",      color: "#2ed573", bg: "rgba(46,213,115,0.13)"  },
  MEDIUM: { label: "WARNING",   color: "#ffa502", bg: "rgba(255,165,2,0.13)"   },
  HIGH:   { label: "HIGH RISK", color: "#ff4757", bg: "rgba(255,71,87,0.13)"   },
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

export default function Alerts({ childList, activeId }) {
  const [selectedDate, setSelectedDate] = useState(todayDefault)
  const [allEvents, setAllEvents]       = useState([])
  const [sseConnected, setSseConnected] = useState(false)

  useEffect(() => {
    if (!activeId) return
    setAllEvents([])
    setSseConnected(false)
    const es = new EventSource(`/stream/${activeId}`)
    es.onopen    = () => setSseConnected(true)
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === "history") {
          setAllEvents(msg.events || [])
        } else if (msg.type === "event") {
          const { type, ...event } = msg
          setAllEvents(prev => [event, ...prev])
        }
      } catch {}
    }
    es.onerror = () => {
      setSseConnected(false)
      fetch(`/api/events/${activeId}?limit=500`)
        .then(r => r.json())
        .then(data => setAllEvents(data.events || []))
        .catch(() => {})
    }
    return () => es.close()
  }, [activeId])

  const handleDateChange = (e) => {
    let val = e.target.value.replace(/[^\d/]/g, "")
    if (val.length === 2 && !val.includes("/")) val += "/"
    if (val.length === 5 && val.split("/").length - 1 === 1) val += "/"
    if (val.length > 10) return
    setSelectedDate(val)
  }

  const filteredEvents = useMemo(() => {
    if (!selectedDate || selectedDate.length < 10) return allEvents
    const [dd, mm, yyyy] = selectedDate.split("/")
    if (!dd || !mm || !yyyy) return allEvents
    const prefix = `${yyyy}-${mm}-${dd}`
    return allEvents.filter(e => e.timestamp && e.timestamp.startsWith(prefix))
  }, [allEvents, selectedDate])

  const activeChild = childList.find(c => c.childId === activeId)
  const childName   = activeChild?.childName || activeId || "Unknown"
  const childIdx    = childList.findIndex(c => c.childId === activeId)
  const avatarGrad  = AVATAR_GRADS[childIdx >= 0 ? childIdx % AVATAR_GRADS.length : 0]
  const initials    = getInitials(childName)

  const isLive = useMemo(() => {
    if (!allEvents.length || !sseConnected) return false
    return (Date.now() - new Date(allEvents[0].timestamp).getTime()) < 60_000
  }, [allEvents, sseConnected])

  const high = filteredEvents.filter(e => getSeverity(e) === "HIGH").length
  const med  = filteredEvents.filter(e => getSeverity(e) === "MEDIUM").length
  const safe = filteredEvents.filter(e => getSeverity(e) === "SAFE").length

  const todayStr = useMemo(() =>
    new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long" }), [])

  return (
    <div style={{
      width: "100%", height: "100vh", background: "#0d0f14", color: "#e8eaf0",
      fontFamily: "'IBM Plex Sans',sans-serif", display: "flex", flexDirection: "column", overflow: "hidden",
    }}>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "24px 32px", gap: 16, overflow: "hidden" }}>

        {/* Page title */}
        <div style={{ animation: "in 0.4s ease" }}>
          <div style={{ fontSize: 10, color: "#4b5268", fontFamily: "'IBM Plex Mono',monospace", letterSpacing: "0.1em", marginBottom: 3 }}>MONITOR</div>
          <h1 style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>Session Timeline</h1>
          <p style={{ fontSize: 11, color: "#4b5268", marginTop: 2 }}>
            Today, {todayStr} · {childName}'s session ·{" "}
            {isLive
              ? <span style={{ color: "#ff4757" }}>● LIVE</span>
              : <span style={{ color: "#4b5268" }}>● Offline</span>
            }
          </p>
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
          {isLive && (
            <span style={{ fontSize: 9, fontWeight: 700, color: "#ff4757",
              background: "rgba(255,71,87,0.13)", border: "1px solid rgba(255,71,87,0.28)",
              borderRadius: 4, padding: "2px 6px", fontFamily: "'IBM Plex Mono',monospace" }}>● LIVE</span>
          )}

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
          {filteredEvents.length === 0 ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
              height: "100%", color: "#3a3f58", fontFamily: "'IBM Plex Mono',monospace", fontSize: 12 }}>
              No events found for this date
            </div>
          ) : filteredEvents.map((ev, i) => {
            const severity        = getSeverity(ev)
            const { icon, bg: iconBg } = getAppIcon(ev.to)
            const title = getEventTitle(ev)
            const desc  = getEventDesc(ev)
            const evTime = ev.timestamp
              ? new Date(ev.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
              : "—"
            return (
  <div key={ev.receivedAt || `${ev.timestamp}-${i}`} className="ev-row" style={{
    display: "flex", alignItems: "center", gap: 11, padding: "10px 15px",
    borderBottom: i < filteredEvents.length - 1 ? "1px solid #1a1d28" : "none",
    background: severity === "HIGH" ? "rgba(255,71,87,0.04)" : "transparent",
    transition: "background 0.15s",
  }}>
    <Dot color={typeConfig[severity].color} pulse={severity === "HIGH"} />
    <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11,
      color: "#4b5268", minWidth: 34, flexShrink: 0 }}>{evTime}</span>

    <div style={{ width: 24, height: 24, borderRadius: "50%",
      background: avatarGrad,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 8, fontWeight: 700, color: "#fff", flexShrink: 0 }}>{initials}</div>

    <div style={{ width: 28, height: 28, borderRadius: 7, background: iconBg,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 13, flexShrink: 0 }}>{icon}</div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 2 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#e8eaf0",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 360 }}>{title}</span>
        <Badge risk={severity} />
      </div>
      <div style={{ fontSize: 11, color: "#4b5268",
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 500 }}>{desc}</div>
    </div>
  </div>
            )
          })}
        </div>

      </div>
    </div>
  )
}