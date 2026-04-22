import { useState, useEffect, useMemo } from "react"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import config from "../config"
import {
  AVATAR_GRADS,
  getInitials,
  getAppIcon,
  getEventDesc,
  getEventTitle,
  todayDefault,
  Badge,
  StatCard,
  Dot,
} from "../utils/eventHelpers"
import { colors, fonts, pageRoot, timelineContainer, timelineEmpty, liveBadge, dateInput } from "../utils/theme"
import { useAuth } from "../context/AuthContext"

export default function Homepage({ childList, activeId, setActiveId }) {
  const { accessToken, authFetch } = useAuth()
  const [time, setTime]             = useState(new Date())
  const [allEvents, setAllEvents]   = useState([])
  const [sseConnected, setSseConnected] = useState(false)
  const [selectedDate, setSelectedDate] = useState(todayDefault)

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

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
            if (event.alertReason === "confirmed_hop") {
              setAllEvents(prev => [event, ...prev])
            }
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

  const activeChild = useMemo(() =>
    childList.find(c => c.childId === activeId) || null, [childList, activeId])

  const platforms = useMemo(() =>
    new Set(allEvents.map(e => e.to).filter(Boolean)).size, [allEvents])

  const isLive = useMemo(() => {
    if (!allEvents.length || !sseConnected) return false
    return (Date.now() - new Date(allEvents[0].timestamp).getTime()) < config.liveThresholdMs
  }, [allEvents, sseConnected])

  const todayEvents = useMemo(() => {
    const today = todayDefault()
    return allEvents.filter(e => e.timestamp && e.timestamp.startsWith(today))
  }, [allEvents])

  const sessionStart = useMemo(() => {
    if (!todayEvents.length) return null
    const oldest = new Date(todayEvents[todayEvents.length - 1].timestamp)
    return oldest.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
  }, [todayEvents])

  const sessionDuration = useMemo(() => {
    if (!todayEvents.length) return "—"
    const oldest = new Date(todayEvents[todayEvents.length - 1].timestamp)
    const diffMs = Date.now() - oldest.getTime()
    const h = Math.floor(diffMs / 3600000)
    const m = Math.floor((diffMs % 3600000) / 60000)
    return h > 0 ? `${h}h ${m}m` : `${m}m`
  }, [todayEvents])

  const latestHop = useMemo(() => {
    if (!allEvents.length) return null
    const e = allEvents[0]
    return {
      time:  new Date(e.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
      title: e.toTitle || e.to || "Unknown",
      desc:  e.classifyReason || e.context || "Confirmed hop detected",
    }
  }, [allEvents])

  const childName     = activeChild?.childName || activeId || "—"
  const childInitials = getInitials(childName)
  const childIdx      = childList.findIndex(c => c.childId === activeId)
  const avatarGrad    = AVATAR_GRADS[childIdx >= 0 ? childIdx % AVATAR_GRADS.length : 0]
  const status        = isLive ? "live" : "offline"

  const hr         = time.getHours()
  const greet      = hr < 12 ? "GOOD MORNING" : hr < 17 ? "GOOD AFTERNOON" : "GOOD EVENING"
  const todayLabel = time.toLocaleDateString("en-GB", { day: "numeric", month: "long" })

  if (!activeId || childList.length === 0) {
    return (
      <div style={{ ...pageRoot, alignItems: "center", justifyContent: "center",
        color: colors.muted, fontFamily: fonts.mono, fontSize: 13 }}>
        No children registered. Start the agent to begin monitoring.
      </div>
    )
  }

  return (
    <div style={pageRoot}>
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <div style={{ flex: 1, padding: "16px 24px", display: "flex", flexDirection: "column", gap: 13, overflow: "hidden" }}>

          {/* Child switcher */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0, animation: "in 0.4s ease" }}>
            {childList.map((c, idx) => {
              const isActive  = c.childId === activeId
              const grad      = AVATAR_GRADS[idx % AVATAR_GRADS.length]
              const initials  = getInitials(c.childName)
              const childLive = c.childId === activeId ? isLive : false
              return (
                <button key={c.childId} onClick={() => setActiveId(c.childId)} style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "7px 14px", borderRadius: 20, border: "1px solid",
                  borderColor: isActive ? colors.indigo : colors.border,
                  background: isActive ? "rgba(99,102,241,0.15)" : "transparent",
                  cursor: "pointer", transition: "all 0.15s",
                }}>
                  <div style={{ width: 24, height: 24, borderRadius: "50%", background: grad,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 9, fontWeight: 700, color: "#fff", flexShrink: 0 }}>{initials}</div>
                  <span style={{ fontSize: 12, fontWeight: isActive ? 600 : 400,
                    color: isActive ? colors.indigoLight : colors.muted }}>{c.childName || c.childId}</span>
                  <Dot color={childLive ? colors.success : colors.subtle} pulse={childLive} />
                </button>
              )
            })}
          </div>

          {/* Greeting */}
          <div style={{ animation: "in 0.4s ease" }}>
            <div style={{ fontSize: 10, color: colors.muted, fontFamily: fonts.mono,
              letterSpacing: "0.1em", marginBottom: 3 }}>{greet}</div>
            <h1 style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em" }}>
              Hello, you're looking at{" "}
              <span style={{ color: colors.indigoLight }}>{childName}</span>
            </h1>
            <p style={{ fontSize: 11, color: colors.muted, marginTop: 2 }}>
              Today, {todayLabel}
              {status === "live"
                ? <> · Session started {sessionStart} · <span style={{ color: colors.success }}>● LIVE · {sessionDuration}</span></>
                : <> · <span style={{ color: colors.muted }}>● Offline</span></>
              }
            </p>
          </div>

          {/* Latest hop banner */}
          {latestHop ? (
            <div style={{ background: "rgba(255,71,87,0.07)", border: "1px solid rgba(255,71,87,0.28)",
              borderRadius: 10, padding: "11px 15px", display: "flex", alignItems: "center", gap: 12,
              flexShrink: 0, animation: "in 0.35s ease 0.05s both" }}>
              <span style={{ fontSize: 18, flexShrink: 0 }}>🚨</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 9, color: colors.danger, fontFamily: fonts.mono,
                  letterSpacing: "0.07em", marginBottom: 1 }}>LATEST HOP · {latestHop.time}</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: colors.text,
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{latestHop.title}</div>
                <div style={{ fontSize: 11, color: colors.muted,
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{latestHop.desc}</div>
              </div>
            </div>
          ) : (
            <div style={{ background: "rgba(46,213,115,0.06)", border: "1px solid rgba(46,213,115,0.2)",
              borderRadius: 10, padding: "11px 15px", display: "flex", alignItems: "center", gap: 12,
              flexShrink: 0, animation: "in 0.35s ease 0.05s both" }}>
              <span style={{ fontSize: 18 }}>✅</span>
              <div>
                <div style={{ fontSize: 9, color: colors.success, fontFamily: fonts.mono,
                  letterSpacing: "0.07em", marginBottom: 1 }}>ALL CLEAR</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: colors.text }}>No hops detected for {childName}</div>
                <div style={{ fontSize: 11, color: colors.muted }}>All recent sessions within safe platform boundaries</div>
              </div>
            </div>
          )}

          {/* Stat cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 11,
            flexShrink: 0, animation: "in 0.35s ease 0.1s both" }}>
            <StatCard label="HOPS DETECTED" val={allEvents.length}   color={colors.danger}      sub="Confirmed hops" />
            <StatCard label="APPS TARGETED" val={platforms}          color={colors.indigoLight} sub="Unique platforms" />
            <StatCard label="TODAY'S HOPS"  val={todayEvents.length} color={colors.warning}     sub="Hops today" />
          </div>

          {/* Timeline header */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0, animation: "in 0.35s ease 0.15s both" }}>
            <span style={{ fontSize: 11, fontWeight: 700, fontFamily: fonts.mono, letterSpacing: "0.1em" }}>
              HOP TIMELINE
            </span>
            {isLive && <span style={liveBadge}>● LIVE</span>}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, color: colors.muted, fontFamily: fonts.mono }}>Date</span>
              <input
                type="date"
                value={selectedDate}
                onChange={e => setSelectedDate(e.target.value)}
                style={dateInput}
              />
            </div>
          </div>

          {/* Timeline events */}
          <div style={{ ...timelineContainer, animation: "in 0.35s ease 0.2s both" }}>
            {filteredEvents.length === 0 ? (
              <div style={timelineEmpty}>No hops found for this date</div>
            ) : filteredEvents.map((ev, i) => {
              const { icon, bg: iconBg } = getAppIcon(ev.to)
              const title  = getEventTitle(ev)
              const desc   = getEventDesc(ev, "Confirmed hop detected")
              const evTime = ev.timestamp
                ? new Date(ev.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
                : "—"
              return (
                <div key={ev.receivedAt || `${ev.timestamp}-${i}`} className="ev-row" style={{
                  display: "flex", alignItems: "center", gap: 11, padding: "10px 15px",
                  borderBottom: i < filteredEvents.length - 1 ? `1px solid ${colors.rowDivider}` : "none",
                  background: "rgba(255,71,87,0.04)", transition: "background 0.15s",
                }}>
                  <Dot color={colors.danger} pulse={i === 0 && isLive} />
                  <span style={{ fontFamily: fonts.mono, fontSize: 11,
                    color: colors.muted, minWidth: 34, flexShrink: 0 }}>{evTime}</span>
                  <div style={{ width: 24, height: 24, borderRadius: "50%", background: avatarGrad,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 8, fontWeight: 700, color: "#fff", flexShrink: 0 }}>{childInitials}</div>
                  <div style={{ width: 28, height: 28, borderRadius: 7, background: iconBg,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 13, flexShrink: 0 }}>{icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 2 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: colors.text,
                        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 360 }}>{title}</span>
                      <Badge risk="HIGH" />
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
    </div>
  )
}
