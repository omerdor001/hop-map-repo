import { useState, useEffect, useMemo } from "react"

const AVATAR_GRADS = [
  "linear-gradient(135deg,#6366f1,#8b5cf6)",
  "linear-gradient(135deg,#f43f5e,#fb7185)",
  "linear-gradient(135deg,#0ea5e9,#38bdf8)",
  "linear-gradient(135deg,#10b981,#34d399)",
  "linear-gradient(135deg,#f59e0b,#fbbf24)",
]

function getAppIcon(to) {
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

function getEventTitle(event) {
  return `HOP DETECTED — ${event.toTitle || event.to || "external link"}`
}

function getEventDesc(event) {
  if (event.classifyReason && event.classifyReason !== "server_unreachable") return event.classifyReason
  if (event.context) return String(event.context).replace(/^\[clipboard\] /, "")
  if (event.from)    return `${event.from} → ${event.to || "—"}`
  return "Confirmed hop detected"
}

function todayDefault() {
  const d  = new Date()
  const dd = String(d.getDate()).padStart(2, "0")
  const mm = String(d.getMonth() + 1).padStart(2, "0")
  return `${dd}/${mm}/${d.getFullYear()}`
}

function getInitials(name) {
  if (!name) return "??"
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

function Dot({ color, pulse }) {
  return (
    <span style={{ position:"relative", display:"inline-flex", width:9, height:9, flexShrink:0 }}>
      {pulse && <span style={{ position:"absolute", inset:0, borderRadius:"50%", background:color, animation:"ping 1.8s ease-out infinite", opacity:0.7 }} />}
      <span style={{ position:"absolute", inset:1, borderRadius:"50%", background:color }} />
    </span>
  )
}

export default function Homepage({ childList, activeId, setActiveId }) {
  const [time, setTime]             = useState(new Date())
  const [allEvents, setAllEvents]   = useState([])
  const [sseConnected, setSseConnected] = useState(false)
  const [selectedDate, setSelectedDate] = useState(todayDefault)

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

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
          // Only show confirmed hops in the timeline
          if (event.alertReason === "confirmed_hop") {
            setAllEvents(prev => [event, ...prev])
          }
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

  const activeChild = useMemo(() =>
    childList.find(c => c.childId === activeId) || null, [childList, activeId])

  const platforms = useMemo(() =>
    new Set(allEvents.map(e => e.to).filter(Boolean)).size, [allEvents])

  const isLive = useMemo(() => {
    if (!allEvents.length || !sseConnected) return false
    return (Date.now() - new Date(allEvents[0].timestamp).getTime()) < 60_000
  }, [allEvents, sseConnected])

  const todayEvents = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10)
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
      <div style={{ width:"100%", height:"100vh", background:"#0d0f14", color:"#4b5268",
        display:"flex", alignItems:"center", justifyContent:"center",
        fontFamily:"'IBM Plex Mono',monospace", fontSize:13 }}>
        No children registered. Start the agent to begin monitoring.
      </div>
    )
  }

  return (
    <div style={{ width:"100%", height:"100vh", background:"#0d0f14", color:"#e8eaf0",
      fontFamily:"'IBM Plex Sans',sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');
        *{box-sizing:border-box;margin:0;padding:0;}
        @keyframes ping{0%{transform:scale(1);opacity:.7}70%{transform:scale(2.2);opacity:0}100%{transform:scale(1);opacity:0}}
        @keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
        .ev-row:hover{background:rgba(255,255,255,0.03)!important;cursor:pointer;}
        ::-webkit-scrollbar{width:3px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#2a2d38;border-radius:2px}
      `}</style>

      <div style={{ flex:1, display:"flex", overflow:"hidden" }}>
        <div style={{ flex:1, padding:"16px 24px", display:"flex", flexDirection:"column", gap:13, overflow:"hidden" }}>

          {/* Child switcher */}
          <div style={{ display:"flex", alignItems:"center", gap:10, flexShrink:0, animation:"in 0.4s ease" }}>
            {childList.map((c, idx) => {
              const isActive  = c.childId === activeId
              const grad      = AVATAR_GRADS[idx % AVATAR_GRADS.length]
              const initials  = getInitials(c.childName)
              const childLive = c.childId === activeId ? isLive : false
              return (
                <button key={c.childId} onClick={() => setActiveId(c.childId)} style={{
                  display:"flex", alignItems:"center", gap:8,
                  padding:"7px 14px", borderRadius:20, border:"1px solid",
                  borderColor: isActive ? "#6366f1" : "#1e2130",
                  background: isActive ? "rgba(99,102,241,0.15)" : "transparent",
                  cursor:"pointer", transition:"all 0.15s",
                }}>
                  <div style={{ width:24, height:24, borderRadius:"50%", background:grad,
                    display:"flex", alignItems:"center", justifyContent:"center",
                    fontSize:9, fontWeight:700, color:"#fff", flexShrink:0 }}>{initials}</div>
                  <span style={{ fontSize:12, fontWeight: isActive ? 600 : 400,
                    color: isActive ? "#818cf8" : "#9098b8" }}>{c.childName || c.childId}</span>
                  <Dot color={childLive ? "#2ed573" : "#3a3f58"} pulse={childLive} />
                </button>
              )
            })}
          </div>

          {/* Greeting */}
          <div style={{ animation:"in 0.4s ease" }}>
            <div style={{ fontSize:10, color:"#4b5268", fontFamily:"'IBM Plex Mono',monospace",
              letterSpacing:"0.1em", marginBottom:3 }}>{greet}</div>
            <h1 style={{ fontSize:20, fontWeight:700, letterSpacing:"-0.02em" }}>
              Hello, you're looking at{" "}
              <span style={{ color:"#818cf8" }}>{childName}</span>
            </h1>
            <p style={{ fontSize:11, color:"#4b5268", marginTop:2 }}>
              Today, {todayLabel}
              {status === "live"
                ? <> · Session started {sessionStart} · <span style={{ color:"#2ed573" }}>● LIVE · {sessionDuration}</span></>
                : <> · <span style={{ color:"#4b5268" }}>● Offline</span></>
              }
            </p>
          </div>

          {/* Latest hop banner */}
          {latestHop ? (
            <div style={{ background:"rgba(255,71,87,0.07)", border:"1px solid rgba(255,71,87,0.28)",
              borderRadius:10, padding:"11px 15px", display:"flex", alignItems:"center", gap:12,
              flexShrink:0, animation:"in 0.35s ease 0.05s both" }}>
              <span style={{ fontSize:18, flexShrink:0 }}>🚨</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:9, color:"#ff4757", fontFamily:"'IBM Plex Mono',monospace",
                  letterSpacing:"0.07em", marginBottom:1 }}>LATEST HOP · {latestHop.time}</div>
                <div style={{ fontSize:13, fontWeight:600, color:"#e8eaf0",
                  whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{latestHop.title}</div>
                <div style={{ fontSize:11, color:"#6b7290",
                  whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{latestHop.desc}</div>
              </div>
            </div>
          ) : (
            <div style={{ background:"rgba(46,213,115,0.06)", border:"1px solid rgba(46,213,115,0.2)",
              borderRadius:10, padding:"11px 15px", display:"flex", alignItems:"center", gap:12,
              flexShrink:0, animation:"in 0.35s ease 0.05s both" }}>
              <span style={{ fontSize:18 }}>✅</span>
              <div>
                <div style={{ fontSize:9, color:"#2ed573", fontFamily:"'IBM Plex Mono',monospace",
                  letterSpacing:"0.07em", marginBottom:1 }}>ALL CLEAR</div>
                <div style={{ fontSize:13, fontWeight:600, color:"#e8eaf0" }}>No hops detected for {childName}</div>
                <div style={{ fontSize:11, color:"#4b5268" }}>All recent sessions within safe platform boundaries</div>
              </div>
            </div>
          )}

          {/* Stat cards */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:11,
            flexShrink:0, animation:"in 0.35s ease 0.1s both" }}>
            {[
              { label:"HOPS DETECTED", val:allEvents.length,   color:"#ff4757", sub:"Confirmed hops" },
              { label:"APPS TARGETED", val:platforms,          color:"#818cf8", sub:"Unique platforms" },
              { label:"TODAY'S HOPS",  val:todayEvents.length, color:"#ffa502", sub:"Hops today" },
            ].map(s => (
              <div key={s.label} style={{ background:"#111318", border:"1px solid #1e2130",
                borderTop:`3px solid ${s.color}`, borderRadius:10, padding:"12px 14px" }}>
                <div style={{ fontSize:9, color:"#4b5268", letterSpacing:"0.1em",
                  fontFamily:"'IBM Plex Mono',monospace", marginBottom:5 }}>{s.label}</div>
                <div style={{ fontSize:30, fontWeight:700, color:s.color, lineHeight:1,
                  fontFamily:"'IBM Plex Mono',monospace", marginBottom:3 }}>{s.val}</div>
                <div style={{ fontSize:10, color:"#4b5268" }}>{s.sub}</div>
              </div>
            ))}
          </div>

          {/* Timeline header */}
          <div style={{ display:"flex", alignItems:"center", gap:10, flexShrink:0, animation:"in 0.35s ease 0.15s both" }}>
            <span style={{ fontSize:11, fontWeight:700, fontFamily:"'IBM Plex Mono',monospace", letterSpacing:"0.1em" }}>
              HOP TIMELINE
            </span>
            {isLive && (
              <span style={{ fontSize:9, fontWeight:700, color:"#ff4757",
                background:"rgba(255,71,87,0.13)", border:"1px solid rgba(255,71,87,0.28)",
                borderRadius:4, padding:"2px 6px", fontFamily:"'IBM Plex Mono',monospace" }}>● LIVE</span>
            )}
            <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:8 }}>
              <span style={{ fontSize:11, color:"#4b5268", fontFamily:"'IBM Plex Mono',monospace" }}>Date</span>
              <input
                type="text"
                value={selectedDate}
                onChange={handleDateChange}
                placeholder="DD/MM/YYYY"
                maxLength={10}
                style={{
                  background:"#111318", border:"1px solid #1e2130",
                  borderRadius:7, padding:"5px 10px", color:"#e8eaf0",
                  fontSize:11, fontFamily:"'IBM Plex Mono',monospace",
                  outline:"none", width:100, letterSpacing:"0.05em",
                }}
              />
            </div>
          </div>

          {/* Timeline events */}
          <div style={{ flex:1, background:"#111318", border:"1px solid #1e2130",
            borderRadius:10, overflowY:"auto", animation:"in 0.35s ease 0.2s both" }}>
            {filteredEvents.length === 0 ? (
              <div style={{ display:"flex", alignItems:"center", justifyContent:"center",
                height:"100%", color:"#3a3f58", fontFamily:"'IBM Plex Mono',monospace", fontSize:12 }}>
                No hops found for this date
              </div>
            ) : filteredEvents.map((ev, i) => {
              const { icon, bg: iconBg } = getAppIcon(ev.to)
              const title  = getEventTitle(ev)
              const desc   = getEventDesc(ev)
              const evTime = ev.timestamp
                ? new Date(ev.timestamp).toLocaleTimeString("en-GB", { hour:"2-digit", minute:"2-digit" })
                : "—"
              return (
                <div key={ev._id || i} className="ev-row" style={{
                  display:"flex", alignItems:"center", gap:11, padding:"10px 15px",
                  borderBottom: i < filteredEvents.length - 1 ? "1px solid #1a1d28" : "none",
                  background:"rgba(255,71,87,0.04)", transition:"background 0.15s",
                }}>
                  <Dot color="#ff4757" pulse={i === 0 && isLive} />
                  <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:11,
                    color:"#4b5268", minWidth:34, flexShrink:0 }}>{evTime}</span>
                  <div style={{ width:24, height:24, borderRadius:"50%", background:avatarGrad,
                    display:"flex", alignItems:"center", justifyContent:"center",
                    fontSize:8, fontWeight:700, color:"#fff", flexShrink:0 }}>{childInitials}</div>
                  <div style={{ width:28, height:28, borderRadius:7, background:iconBg,
                    display:"flex", alignItems:"center", justifyContent:"center",
                    fontSize:13, flexShrink:0 }}>{icon}</div>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:"flex", alignItems:"center", gap:7, marginBottom:2 }}>
                      <span style={{ fontSize:12, fontWeight:600, color:"#e8eaf0",
                        whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", maxWidth:360 }}>{title}</span>
                      <span style={{
                        fontSize:9, fontWeight:700, letterSpacing:"0.07em",
                        color:"#ff4757", background:"rgba(255,71,87,0.13)",
                        border:"1px solid rgba(255,71,87,0.33)", borderRadius:4, padding:"2px 6px",
                        fontFamily:"'IBM Plex Mono',monospace", whiteSpace:"nowrap",
                      }}>HIGH RISK</span>
                    </div>
                    <div style={{ fontSize:11, color:"#4b5268",
                      whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", maxWidth:500 }}>{desc}</div>
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