import { useState, useEffect, useMemo } from "react"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { useAuth } from "../context/AuthContext"
import config from "../config"
import {
  AVATAR_GRADS,
  getInitials,
  getAppIcon,
  getEventDesc,
  getEventTitle,
  getSeverity,
  todayDefault,
  typeConfig,
  Badge,
  StatCard,
  Dot,
} from "../utils/eventHelpers"
import { colors, fonts, pageRoot, timelineContainer, timelineEmpty, liveBadge, dateInput } from "../utils/theme"

export default function Alerts({ childList, activeId }) {
  const { accessToken, authFetch } = useAuth()
  const [selectedDate, setSelectedDate] = useState(todayDefault)
  const [allEvents, setAllEvents]       = useState([])
  const [sseConnected, setSseConnected] = useState(false)

  useEffect(() => {
    if (!activeId || !accessToken) return
    setAllEvents([])
    setSseConnected(false)

    const controller = new AbortController()

    fetchEventSource(`/stream/${activeId}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      signal: controller.signal,
      onopen: async (res) => {
        if (!res.ok) throw new Error(`SSE open failed: ${res.status}`)
        setSseConnected(true)
      },
      onmessage: (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === "history") {
            setAllEvents(msg.events || [])
          } else if (msg.type === "event") {
            const { type, ...event } = msg
            setAllEvents(prev => [event, ...prev])
          }
        } catch {}
      },
      onerror: () => {
        setSseConnected(false)
        authFetch(`/api/events/${activeId}?limit=${config.eventHistoryLimit}`)
          .then(r => r.ok ? r.json() : null)
          .then(data => { if (data) setAllEvents(data.events || []) })
          .catch(() => {})
        throw new Error("SSE error")
      },
    }).catch(() => {})

    return () => controller.abort()
  }, [activeId, accessToken, authFetch])

  const filteredEvents = useMemo(() => {
    if (!selectedDate) return allEvents
    return allEvents.filter(e => e.timestamp && e.timestamp.startsWith(selectedDate))
  }, [allEvents, selectedDate])

  const activeChild = childList.find(c => c.childId === activeId)
  const childName   = activeChild?.childName || activeId || "Unknown"
  const childIdx    = childList.findIndex(c => c.childId === activeId)
  const avatarGrad  = AVATAR_GRADS[childIdx >= 0 ? childIdx % AVATAR_GRADS.length : 0]
  const initials    = getInitials(childName)

  const isLive = useMemo(() => {
    if (!allEvents.length || !sseConnected) return false
    return (Date.now() - new Date(allEvents[0].timestamp).getTime()) < config.liveThresholdMs
  }, [allEvents, sseConnected])

  const high = filteredEvents.filter(e => getSeverity(e) === "HIGH").length
  const med  = filteredEvents.filter(e => getSeverity(e) === "MEDIUM").length
  const safe = filteredEvents.filter(e => getSeverity(e) === "SAFE").length

  const todayStr = useMemo(() =>
    new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long" }), [])

  return (
    <div style={pageRoot}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "24px 32px", gap: 16, overflow: "hidden" }}>

        {/* Page title */}
        <div style={{ animation: "in 0.4s ease" }}>
          <div style={{ fontSize: 10, color: colors.muted, fontFamily: fonts.mono, letterSpacing: "0.1em", marginBottom: 3 }}>MONITOR</div>
          <h1 style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>Session Timeline</h1>
          <p style={{ fontSize: 11, color: colors.muted, marginTop: 2 }}>
            Today, {todayStr} · {childName}'s session ·{" "}
            {isLive
              ? <span style={{ color: colors.danger }}>● LIVE</span>
              : <span style={{ color: colors.muted }}>● Offline</span>
            }
          </p>
        </div>

        {/* Stat cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 11, flexShrink: 0, animation: "in 0.35s ease 0.05s both" }}>
          <StatCard label="HIGH RISK" val={high} color={colors.danger}  sub="Hops detected" />
          <StatCard label="WARNINGS"  val={med}  color={colors.warning} sub="Medium risk events" />
          <StatCard label="ALL CLEAR" val={safe} color={colors.success} sub="Safe events" />
        </div>

        {/* Timeline header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0, animation: "in 0.35s ease 0.1s both" }}>
          <span style={{ fontSize: 11, fontWeight: 700, fontFamily: fonts.mono, letterSpacing: "0.1em" }}>
            SESSION TIMELINE
          </span>
          {isLive && <span style={liveBadge}>● LIVE</span>}

          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: colors.muted, fontFamily: fonts.mono }}>Data from</span>
            <input
              type="date"
              value={selectedDate}
              onChange={e => setSelectedDate(e.target.value)}
              style={dateInput}
            />
            <span style={{ fontSize: 11, color: colors.muted, fontFamily: fonts.mono }}>backwards</span>
            <button style={{
              padding: "5px 13px", borderRadius: 6, border: "none", cursor: "pointer",
              fontSize: 11, fontWeight: 700, letterSpacing: "0.05em",
              background: colors.indigo, color: "#fff",
            }}>GO</button>
          </div>
        </div>

        {/* Timeline events */}
        <div style={{ ...timelineContainer, animation: "in 0.35s ease 0.15s both" }}>
          {filteredEvents.length === 0 ? (
            <div style={timelineEmpty}>No events found for this date</div>
          ) : filteredEvents.map((ev, i) => {
            const severity         = getSeverity(ev)
            const { icon, bg: iconBg } = getAppIcon(ev.to)
            const title  = getEventTitle(ev)
            const desc   = getEventDesc(ev)
            const evTime = ev.timestamp
              ? new Date(ev.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
              : "—"
            return (
              <div key={ev.receivedAt || `${ev.timestamp}-${i}`} className="ev-row" style={{
                display: "flex", alignItems: "center", gap: 11, padding: "10px 15px",
                borderBottom: i < filteredEvents.length - 1 ? `1px solid ${colors.rowDivider}` : "none",
                background: severity === "HIGH" ? "rgba(255,71,87,0.04)" : "transparent",
                transition: "background 0.15s",
              }}>
                <Dot color={typeConfig[severity].color} pulse={severity === "HIGH"} />
                <span style={{ fontFamily: fonts.mono, fontSize: 11,
                  color: colors.muted, minWidth: 34, flexShrink: 0 }}>{evTime}</span>

                <div style={{ width: 24, height: 24, borderRadius: "50%", background: avatarGrad,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 8, fontWeight: 700, color: "#fff", flexShrink: 0 }}>{initials}</div>

                <div style={{ width: 28, height: 28, borderRadius: 7, background: iconBg,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 13, flexShrink: 0 }}>{icon}</div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 2 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: colors.text,
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 360 }}>{title}</span>
                    <Badge risk={severity} />
                  </div>
                  <div style={{ fontSize: 11, color: colors.muted,
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
