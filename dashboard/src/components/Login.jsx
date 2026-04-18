import { useState } from "react"
import { useAuth } from "../context/AuthContext"

const DARK  = "#0d0d0f"
const CARD  = "#16161a"
const BORDER = "#1e1e24"
const INDIGO = "#6366f1"
const MUTED = "#6b7280"

const input = {
  width: "100%",
  background: "#0d0d0f",
  border: `1px solid ${BORDER}`,
  borderRadius: 8,
  color: "#fff",
  fontSize: 14,
  padding: "10px 14px",
  outline: "none",
  boxSizing: "border-box",
}

const btn = {
  width: "100%",
  background: INDIGO,
  color: "#fff",
  border: "none",
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 700,
  padding: "11px 0",
  cursor: "pointer",
  marginTop: 8,
}

const btnDisabled = { ...btn, opacity: 0.5, cursor: "not-allowed" }

export default function Login() {
  const { login, register } = useAuth()
  const [tab, setTab]           = useState("login")  // "login" | "register"
  const [email, setEmail]       = useState("")
  const [password, setPassword] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [error, setError]       = useState("")
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      if (tab === "login") {
        await login(email, password)
      } else {
        if (password.length < 8) { setError("Password must be at least 8 characters."); return }
        await register(email, password, displayName)
      }
    } catch (err) {
      setError(err.message || "Something went wrong.")
    } finally {
      setLoading(false)
    }
  }

  function switchTab(t) {
    setTab(t)
    setError("")
    setEmail("")
    setPassword("")
    setDisplayName("")
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: DARK,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    }}>
      <div style={{
        background: CARD,
        border: `1px solid ${BORDER}`,
        borderRadius: 16,
        padding: "40px 36px",
        width: 380,
        boxSizing: "border-box",
      }}>
        {/* Logo / brand */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 28, fontWeight: 900, color: "#fff", letterSpacing: "-0.5px" }}>
            hop<span style={{ color: INDIGO }}>map</span>
          </div>
          <div style={{ fontSize: 13, color: MUTED, marginTop: 4 }}>
            Parent dashboard
          </div>
        </div>

        {/* Tabs */}
        <div style={{
          display: "flex",
          background: "#0d0d0f",
          borderRadius: 8,
          padding: 4,
          marginBottom: 24,
          gap: 4,
        }}>
          {["login", "register"].map(t => (
            <button
              key={t}
              onClick={() => switchTab(t)}
              style={{
                flex: 1,
                background: tab === t ? CARD : "transparent",
                border: tab === t ? `1px solid ${BORDER}` : "1px solid transparent",
                borderRadius: 6,
                color: tab === t ? "#fff" : MUTED,
                fontSize: 13,
                fontWeight: 600,
                padding: "7px 0",
                cursor: "pointer",
              }}
            >
              {t === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {tab === "register" && (
            <div>
              <label style={{ fontSize: 12, color: MUTED, display: "block", marginBottom: 6 }}>
                Display name (optional)
              </label>
              <input
                style={input}
                type="text"
                autoComplete="name"
                placeholder="Parent name"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
              />
            </div>
          )}

          <div>
            <label style={{ fontSize: 12, color: MUTED, display: "block", marginBottom: 6 }}>
              Email address
            </label>
            <input
              style={input}
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, color: MUTED, display: "block", marginBottom: 6 }}>
              Password {tab === "register" && <span style={{ color: "#4b5563" }}>(min 8 chars)</span>}
            </label>
            <input
              style={input}
              type="password"
              autoComplete={tab === "login" ? "current-password" : "new-password"}
              placeholder="••••••••"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>

          {error && (
            <div style={{
              background: "#1f0f0f",
              border: "1px solid #7f1d1d",
              borderRadius: 6,
              padding: "9px 12px",
              color: "#f87171",
              fontSize: 13,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={loading ? btnDisabled : btn}
          >
            {loading
              ? (tab === "login" ? "Signing in…" : "Creating account…")
              : (tab === "login" ? "Sign in" : "Create account")}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: 20, fontSize: 12, color: MUTED }}>
          {tab === "login"
            ? <>No account?{" "}
                <span style={{ color: INDIGO, cursor: "pointer" }} onClick={() => switchTab("register")}>
                  Create one
                </span>
              </>
            : <>Already have an account?{" "}
                <span style={{ color: INDIGO, cursor: "pointer" }} onClick={() => switchTab("login")}>
                  Sign in
                </span>
              </>}
        </div>
      </div>
    </div>
  )
}
