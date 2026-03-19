import { useState, useEffect } from "react"

const CHILDREN = [
  {
    id: 1, name: "Yonatan", initials: "YS", status: "live",
    sessionStart: "19:20", sessionDuration: "2h 14m", platforms: 4, hops: 3,
    avatarGrad: "linear-gradient(135deg,#6366f1,#8b5cf6)",
    alerts: [
      { id: 1, type: "HIGH",   time: "21:34", title: "HOP DETECTED — External server invite", desc: "Roblox chat → discord.gg/xR9k2mP · No moderation", platform: "Discord" },
      { id: 2, type: "MEDIUM", time: "21:08", title: "Switched to Discord (personal)",         desc: "Known friends server · Monitored by school community", platform: "Discord" },
      { id: 3, type: "MEDIUM", time: "20:45", title: "External link in YouTube comments",      desc: "Navigated to third-party site from YouTube comment", platform: "YouTube" },
      { id: 4, type: "SAFE",   time: "20:12", title: "Opened YouTube",                         desc: "youtube.com · SafeSearch enabled · Gaming content", platform: "YouTube" },
      { id: 5, type: "SAFE",   time: "19:45", title: "Browsed roblox.com",                     desc: "roblox.com/games · In-platform · No external links", platform: "Roblox" },
    ],
    initialRead: new Set([4,5]),
  },
  {
    id: 2, name: "Maya", initials: "MA", status: "offline",
    sessionStart: null, sessionDuration: "—", platforms: 2, hops: 0,
    avatarGrad: "linear-gradient(135deg,#f43f5e,#fb7185)",
    alerts: [
      { id: 1, type: "SAFE",   time: "17:30", title: "Opened Khan Academy",  desc: "khanacademy.org · Educational content · Safe", platform: "Web" },
      { id: 2, type: "SAFE",   time: "16:55", title: "Browsed YouTube Kids", desc: "youtube.com/kids · Restricted mode on · Age-appropriate", platform: "YouTube" },
      { id: 3, type: "MEDIUM", time: "16:20", title: "Searched on Google",   desc: "Query included external site link — reviewed", platform: "Web" },
    ],
    initialRead: new Set([1,2]),
  },
  {
    id: 3, name: "Tal", initials: "TL", status: "offline",
    sessionStart: null, sessionDuration: "—", platforms: 1, hops: 0,
    avatarGrad: "linear-gradient(135deg,#0ea5e9,#38bdf8)",
    alerts: [
      { id: 1, type: "SAFE", time: "15:10", title: "Opened Minecraft",     desc: "Minecraft desktop · Moderated server · Age-appropriate", platform: "Minecraft" },
      { id: 2, type: "SAFE", time: "14:50", title: "Browsed YouTube Kids", desc: "youtube.com/kids · Restricted mode · Gaming content", platform: "YouTube" },
    ],
    initialRead: new Set([1,2]),
  },
]

const typeConfig = {
  HIGH:   { label: "HIGH RISK", color: "#ff4757", bg: "rgba(255,71,87,0.13)" },
  MEDIUM: { label: "WARNING",   color: "#ffa502", bg: "rgba(255,165,2,0.13)" },
  SAFE:   { label: "SAFE",      color: "#2ed573", bg: "rgba(46,213,115,0.13)" },
}

function Dot({ color, pulse }) {
  return (
    <span style={{ position:"relative", display:"inline-flex", width:9, height:9, flexShrink:0 }}>
      {pulse && <span style={{ position:"absolute", inset:0, borderRadius:"50%", background:color, animation:"ping 1.8s ease-out infinite", opacity:0.7 }} />}
      <span style={{ position:"absolute", inset:1, borderRadius:"50%", background:color }} />
    </span>
  )
}

export default function Homepage() {
  const [time, setTime]         = useState(new Date())
  const [activeId, setActiveId] = useState(1)
  const [dropOpen, setDropOpen] = useState(false)
  const [readMap, setReadMap]   = useState(() =>
    Object.fromEntries(CHILDREN.map(c => [c.id, new Set(c.initialRead)]))
  )

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const child   = CHILDREN.find(c => c.id === activeId)
  const read    = readMap[activeId]
  const setRead = (fn) => setReadMap(prev => ({ ...prev, [activeId]: fn(prev[activeId]) }))

  const alerts = child.alerts
  const high   = alerts.filter(a => a.type === "HIGH").length
  const med    = alerts.filter(a => a.type === "MEDIUM").length
  const safe   = alerts.filter(a => a.type === "SAFE").length
  const latest = alerts[0]

  const hr    = time.getHours()
  const greet = hr < 12 ? "GOOD MORNING" : hr < 17 ? "GOOD AFTERNOON" : "GOOD EVENING"

  return (
    <div style={{ width:"100%", height:"100vh", background:"#0d0f14", color:"#e8eaf0",
      fontFamily:"'IBM Plex Sans',sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap');
        *{box-sizing:border-box;margin:0;padding:0;}
        @keyframes ping{0%{transform:scale(1);opacity:.7}70%{transform:scale(2.2);opacity:0}100%{transform:scale(1);opacity:0}}
        @keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
        .qbtn:hover{background:rgba(255,255,255,0.04)!important;}
        ::-webkit-scrollbar{width:3px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#2a2d38;border-radius:2px}
      `}</style>

      {/* ── BODY ── */}
      <div style={{ flex:1, display:"flex", overflow:"hidden" }}>

        {/* ── MAIN ── */}
        <div style={{ flex:1, padding:"16px 24px", display:"flex", flexDirection:"column", gap:13, overflow:"hidden" }}>

          {/* Child switcher */}
<div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0, animation: "in 0.4s ease" }}>
  {CHILDREN.map(c => {
    const isActive = c.id === activeId
    return (
      <button key={c.id} onClick={() => setActiveId(c.id)} style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "7px 14px", borderRadius: 20, border: "1px solid",
        borderColor: isActive ? "#6366f1" : "#1e2130",
        background: isActive ? "rgba(99,102,241,0.15)" : "transparent",
        cursor: "pointer", transition: "all 0.15s",
      }}>
        <div style={{ width: 24, height: 24, borderRadius: "50%", background: c.avatarGrad,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 9, fontWeight: 700, color: "#fff", flexShrink: 0 }}>{c.initials}</div>
        <span style={{ fontSize: 12, fontWeight: isActive ? 600 : 400,
          color: isActive ? "#818cf8" : "#9098b8" }}>{c.name}</span>
        <Dot color={c.status === "live" ? "#2ed573" : "#3a3f58"} pulse={c.status === "live"} />
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
              <span style={{ color:"#818cf8" }}>{child.name}</span>
              <span style={{ color:"#4b5268", fontWeight:300 }}>, {child.age}</span>
            </h1>
            <p style={{ fontSize:11, color:"#4b5268", marginTop:2 }}>
              Today, March 19
              {child.status === "live"
                ? <> · Session started {child.sessionStart} IL · <span style={{ color:"#2ed573" }}>● LIVE · {child.sessionDuration}</span></>
                : <> · <span style={{ color:"#4b5268" }}>● Offline</span></>
              }
            </p>
          </div>

          {/* Latest alert banner */}
          {latest.type !== "SAFE" ? (
            <div style={{ background: latest.type==="HIGH" ? "rgba(255,71,87,0.07)" : "rgba(255,165,2,0.07)",
              border:`1px solid ${latest.type==="HIGH" ? "rgba(255,71,87,0.28)" : "rgba(255,165,2,0.28)"}`,
              borderRadius:10, padding:"11px 15px", display:"flex", alignItems:"center", gap:12,
              flexShrink:0, animation:"in 0.35s ease 0.05s both" }}>
              <span style={{ fontSize:18, flexShrink:0 }}>{latest.type==="HIGH" ? "🚨" : "⚠️"}</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:9, color: typeConfig[latest.type].color,
                  fontFamily:"'IBM Plex Mono',monospace", letterSpacing:"0.07em", marginBottom:1 }}>
                  LATEST ALERT · {latest.time}</div>
                <div style={{ fontSize:13, fontWeight:600, color:"#e8eaf0",
                  whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{latest.title}</div>
                <div style={{ fontSize:11, color:"#6b7290",
                  whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{latest.desc}</div>
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
                <div style={{ fontSize:13, fontWeight:600, color:"#e8eaf0" }}>No high-risk activity detected for {child.name}</div>
                <div style={{ fontSize:11, color:"#4b5268" }}>All recent sessions within safe platform boundaries</div>
              </div>
            </div>
          )}

          {/* Stat cards */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:11,
            flexShrink:0, animation:"in 0.35s ease 0.1s both" }}>
            {[
              { label:"DANGEROUS", val:high, color:"#ff4757", sub:"High risk hops" },
              { label:"WARNINGS",  val:med,  color:"#ffa502", sub:"Medium risk" },
              { label:"ALL CLEAR", val:safe, color:"#2ed573", sub:"Safe events" },
              { label:"PLATFORMS", val:child.platforms, color:"#818cf8", sub:"Visited today" },
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

        </div>

        {/* ── RIGHT SIDEBAR ── */}
        <aside style={{ width:210, background:"#111318", borderLeft:"1px solid #1e2130",
          padding:"18px 14px", display:"flex", flexDirection:"column", gap:18, flexShrink:0 }}>

          {/* Child card */}
          <div style={{ background:"#0d0f14", borderRadius:10, padding:"13px", border:"1px solid #1e2130" }}>
            <div style={{ display:"flex", alignItems:"center", gap:9, marginBottom:12 }}>
              <div style={{ width:36, height:36, borderRadius:9, background:child.avatarGrad,
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:11, fontWeight:700, color:"#fff" }}>{child.initials}</div>
              <div>
                <div style={{ fontWeight:600, fontSize:13 }}>{child.name}</div>
              </div>
              <Dot color={child.status==="live" ? "#2ed573" : "#3a3f58"} pulse={child.status==="live"} />
            </div>
            {[
              ["Session",   child.sessionDuration],
              ["Started",   child.sessionStart ? `${child.sessionStart} IL` : "—"],
              ["Platforms", `${child.platforms} visited`],
              ["Hops",      `${child.hops} detected`],
            ].map(([k,v]) => (
              <div key={k} style={{ display:"flex", justifyContent:"space-between", marginBottom:6 }}>
                <span style={{ fontSize:10, color:"#4b5268" }}>{k}</span>
                <span style={{ fontSize:10, fontFamily:"'IBM Plex Mono',monospace", color:"#9098b8" }}>{v}</span>
              </div>
            ))}
          </div>

          {/* Risk bars */}
          <div>
            <div style={{ fontSize:9, color:"#3a3f58", letterSpacing:"0.1em",
              fontFamily:"'IBM Plex Mono',monospace", marginBottom:9 }}>RISK BREAKDOWN</div>
            {[
              { label:"High Risk", count:high, color:"#ff4757" },
              { label:"Warning",   count:med,  color:"#ffa502" },
              { label:"Safe",      count:safe, color:"#2ed573" },
            ].map(r => (
              <div key={r.label} style={{ marginBottom:9 }}>
                <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                  <span style={{ fontSize:11, color:"#9098b8" }}>{r.label}</span>
                  <span style={{ fontSize:11, fontFamily:"'IBM Plex Mono',monospace", color:r.color }}>{r.count}</span>
                </div>
                <div style={{ height:4, background:"#1a1d28", borderRadius:2, overflow:"hidden" }}>
                  <div style={{ height:"100%", width: alerts.length ? `${(r.count/alerts.length)*100}%` : "0%",
                    background:r.color, borderRadius:2, opacity:0.85, transition:"width 0.4s ease" }} />
                </div>
              </div>
            ))}
          </div>

        </aside>
      </div>
    </div>
  )
}