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
import { useAuth } from "../context/AuthContext"
import { useChildren } from "../context/ChildrenContext"
import styles from "./Homepage.module.css"

// Thrown from fetchEventSource's onerror to stop reconnection.
// Using a class (not a string) lets the outer .catch() use instanceof
// instead of fragile message-string comparison.
class SseReconnectStop extends Error {
  constructor() { super("SseReconnectStop"); this.name = "SseReconnectStop" }
}

export default function Homepage() {
  const { childList, activeId, setActiveId, childrenError } = useChildren()
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
            const { type: _type, ...event } = msg
            if (event.alertReason === "confirmed_hop") {
              setAllEvents(prev => [event, ...prev])
            }
          }
        } catch (err) {
          console.error("[Homepage] failed to process SSE message:", err, "raw:", ev.data)
        }
      },
      onerror: () => {
        setSseConnected(false)
        authFetch(`/api/events/${activeId}?limit=${config.eventHistoryLimit}`)
          .then(r => r.ok ? r.json() : null)
          .then(data => { if (data) setAllEvents(data.events || []) })
          .catch(err => console.error("[Homepage] event history fallback failed:", err))
        throw new SseReconnectStop()
      },
    }).catch(err => {
      if (!(err instanceof SseReconnectStop)) {
        console.error("[Homepage] unexpected SSE stream error:", err)
      }
    })

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
    // eslint-disable-next-line react-hooks/purity
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
    // eslint-disable-next-line react-hooks/purity
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

  if (childrenError) {
    return <div className={styles.empty}>{childrenError}</div>
  }

  if (!activeId || childList.length === 0) {
    return (
      <div className={styles.empty}>
        No children registered. Start the agent to begin monitoring.
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <div className={styles.inner}>
        <div className={styles.main}>

          {/* Child switcher */}
          <div className={styles.switcher}>
            {childList.map((c, idx) => {
              const isActive  = c.childId === activeId
              const grad      = AVATAR_GRADS[idx % AVATAR_GRADS.length]
              const initials  = getInitials(c.childName)
              const childLive = c.childId === activeId ? isLive : false
              return (
                <button
                  key={c.childId}
                  onClick={() => setActiveId(c.childId)}
                  className={isActive ? `${styles.childBtn} ${styles.childBtnActive}` : styles.childBtn}
                >
                  {/* gradient is per-child computed — stays inline */}
                  <div className={styles.avatar} style={{ background: grad }}>{initials}</div>
                  <span className={isActive ? `${styles.childBtnName} ${styles.childBtnNameActive}` : styles.childBtnName}>
                    {c.childName || c.childId}
                  </span>
                  <Dot color={childLive ? "var(--color-success)" : "var(--color-subtle)"} pulse={childLive} />
                </button>
              )
            })}
          </div>

          {/* Greeting */}
          <div className={styles.greeting}>
            <div className={styles.greetLabel}>{greet}</div>
            <h1 className={styles.greetHeading}>
              Hello, you're looking at{" "}
              <span className={styles.greetAccent}>{childName}</span>
            </h1>
            <p className={styles.greetSub}>
              Today, {todayLabel}
              {status === "live"
                ? <> · Session started {sessionStart} · <span className={styles.greetLive}>● LIVE · {sessionDuration}</span></>
                : <> · <span className={styles.greetOffline}>● Offline</span></>
              }
            </p>
          </div>

          {/* Latest hop banner */}
          {latestHop ? (
            <div className={styles.bannerDanger}>
              <span className={styles.bannerIcon}>🚨</span>
              <div className={styles.bannerBody}>
                <div className={`${styles.bannerMeta} ${styles.bannerMetaDanger}`}>
                  LATEST HOP · {latestHop.time}
                </div>
                <div className={styles.bannerTitle}>{latestHop.title}</div>
                <div className={styles.bannerDesc}>{latestHop.desc}</div>
              </div>
            </div>
          ) : (
            <div className={styles.bannerSafe}>
              <span className={styles.bannerIcon}>✅</span>
              <div className={styles.bannerBody}>
                <div className={`${styles.bannerMeta} ${styles.bannerMetaSafe}`}>ALL CLEAR</div>
                <div className={styles.bannerTitle}>No hops detected for {childName}</div>
                <div className={styles.bannerDesc}>All recent sessions within safe platform boundaries</div>
              </div>
            </div>
          )}

          {/* Stat cards */}
          <div className={styles.stats}>
            <StatCard label="HOPS DETECTED" val={allEvents.length}   color="var(--color-danger)"       sub="Confirmed hops" />
            <StatCard label="APPS TARGETED" val={platforms}          color="var(--color-indigo-light)" sub="Unique platforms" />
            <StatCard label="TODAY'S HOPS"  val={todayEvents.length} color="var(--color-warning)"       sub="Hops today" />
          </div>

          {/* Timeline header */}
          <div className={styles.timelineHeader}>
            <span className={styles.timelineTitle}>HOP TIMELINE</span>
            {isLive && <span className={styles.liveBadge}>● LIVE</span>}
            <div className={styles.timelineControls}>
              <span className={styles.controlLabel}>Date</span>
              <input
                type="date"
                value={selectedDate}
                onChange={e => setSelectedDate(e.target.value)}
                className={styles.dateInput}
              />
            </div>
          </div>

          {/* Timeline */}
          <div className={styles.timeline}>
            {filteredEvents.length === 0 ? (
              <div className={styles.timelineEmpty}>No hops found for this date</div>
            ) : filteredEvents.map((ev, i) => {
              const { icon, bg: iconBg } = getAppIcon(ev.to)
              const title  = getEventTitle(ev)
              const desc   = getEventDesc(ev, "Confirmed hop detected")
              const evTime = ev.timestamp
                ? new Date(ev.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
                : "—"
              return (
                <div
                  key={ev.receivedAt || `${ev.timestamp}-${i}`}
                  className={i < filteredEvents.length - 1 ? `${styles.evRow} ${styles.evRowBorder}` : styles.evRow}
                >
                  <Dot color="var(--color-danger)" pulse={i === 0 && isLive} />
                  <span className={styles.evTime}>{evTime}</span>
                  {/* gradient is per-child computed — stays inline */}
                  <div className={styles.evAvatar} style={{ background: avatarGrad }}>{childInitials}</div>
                  {/* iconBg is derived from app name — stays inline */}
                  <div className={styles.evIcon} style={{ background: iconBg }}>{icon}</div>
                  <div className={styles.evBody}>
                    <div className={styles.evTitleRow}>
                      <span className={styles.evTitle}>{title}</span>
                      <Badge risk="HIGH" />
                    </div>
                    <div className={styles.evDesc}>{desc}</div>
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
