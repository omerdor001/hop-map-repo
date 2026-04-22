import { useState } from "react"
import zxcvbn from "zxcvbn"
import { useAuth } from "../context/AuthContext"

const DARK   = "#0d0d0f"
const CARD   = "#16161a"
const BORDER = "#1e1e24"
const INDIGO = "#6366f1"
const MUTED  = "#6b7280"

const STRENGTH_META = [
  { label: "Too weak",    color: "#ef4444" },
  { label: "Weak",        color: "#f97316" },
  { label: "Fair",        color: "#eab308" },
  { label: "Strong",      color: "#22c55e" },
  { label: "Very strong", color: "#16a34a" },
]

// Must match server/auth/schemas.py _validate_complexity exactly.
const PASSWORD_RULES = [
  { test: v => v.length >= 8,            label: "At least 8 characters"   },
  { test: v => /[A-Z]/.test(v),          label: "One uppercase letter"    },
  { test: v => /[a-z]/.test(v),          label: "One lowercase letter"    },
  { test: v => /\d/.test(v),             label: "One digit"               },
  { test: v => /[^A-Za-z0-9]/.test(v),  label: "One special character"   },
]

// Minimum zxcvbn score (0–4) required to enable the submit button.
// Score 2 ("Fair") is the widely-used threshold (GitHub, Notion, etc.).
const MIN_SCORE = 2

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

function getPasswordErrors(password) {
  return PASSWORD_RULES.filter(rule => !rule.test(password)).map(rule => rule.label)
}

function PasswordStrengthMeter({ result, errors }) {
  // Show unmet requirements as a checklist while any are failing.
  // Only switch to the entropy strength bar once all requirements pass.
  if (errors.length > 0) {
    return (
      <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 2 }}>
        {errors.map(label => (
          <div key={label} style={{ fontSize: 11, color: "#ef4444" }}>· {label}</div>
        ))}
      </div>
    )
  }

  const score      = result.score
  const meta       = STRENGTH_META[score]
  const width      = `${(score + 1) / 5 * 100}%`
  const suggestion = result.feedback.suggestions[0] ?? result.feedback.warning ?? null

  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ height: 4, borderRadius: 2, background: BORDER, overflow: "hidden" }}>
        <div style={{
          height: "100%", width, borderRadius: 2,
          background: meta.color,
          transition: "width 200ms ease, background 200ms ease",
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
        <span style={{ fontSize: 11, color: meta.color, fontWeight: 600 }}>{meta.label}</span>
        {suggestion && <span style={{ fontSize: 11, color: MUTED }}>{suggestion}</span>}
      </div>
    </div>
  )
}

export default function Login() {
  const { login, register } = useAuth()
  const [tab, setTab]                 = useState("login")
  const [email, setEmail]             = useState("")
  const [password, setPassword]       = useState("")
  const [displayName, setDisplayName] = useState("")
  const [error, setError]             = useState("")
  const [loading, setLoading]         = useState(false)

  const isRegister     = tab === "register"
  const strengthResult = isRegister && password ? zxcvbn(password) : null
  const passwordErrors = isRegister && password ? getPasswordErrors(password) : []
  const requirementsMet = passwordErrors.length === 0
  const submitDisabled  = loading || (isRegister && password.length > 0 && (!requirementsMet || strengthResult.score < MIN_SCORE))

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      if (isRegister) {
        await register(email, password, displayName)
      } else {
        await login(email, password)
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
    <div style={{ minHeight: "100vh", background: DARK, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 16, padding: "40px 36px", width: 380, boxSizing: "border-box" }}>
        {/* Brand */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 28, fontWeight: 900, color: "#fff", letterSpacing: "-0.5px" }}>
            hop<span style={{ color: INDIGO }}>map</span>
          </div>
          <div style={{ fontSize: 13, color: MUTED, marginTop: 4 }}>Parent dashboard</div>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", background: "#0d0d0f", borderRadius: 8, padding: 4, marginBottom: 24, gap: 4 }}>
          {["login", "register"].map(t => (
            <button key={t} onClick={() => switchTab(t)} style={{
              flex: 1,
              background: tab === t ? CARD : "transparent",
              border: tab === t ? `1px solid ${BORDER}` : "1px solid transparent",
              borderRadius: 6,
              color: tab === t ? "#fff" : MUTED,
              fontSize: 13, fontWeight: 600, padding: "7px 0", cursor: "pointer",
            }}>
              {t === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {isRegister && (
            <div>
              <label style={{ fontSize: 12, color: MUTED, display: "block", marginBottom: 6 }}>
                Display name (optional)
              </label>
              <input style={input} type="text" autoComplete="name" placeholder="Parent name"
                value={displayName} onChange={e => setDisplayName(e.target.value)} />
            </div>
          )}

          <div>
            <label style={{ fontSize: 12, color: MUTED, display: "block", marginBottom: 6 }}>
              Email address
            </label>
            <input style={input} type="email" autoComplete="email" placeholder="you@example.com"
              required value={email} onChange={e => setEmail(e.target.value)} />
          </div>

          <div>
            <label style={{ fontSize: 12, color: MUTED, display: "block", marginBottom: 6 }}>
              Password
              {isRegister && (
                <span style={{ color: "#4b5563", marginLeft: 6 }}>
                  min 8 chars · uppercase · lowercase · digit · special character
                </span>
              )}
            </label>
            <input style={input} type="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              placeholder="••••••••" required
              value={password} onChange={e => setPassword(e.target.value)} />
            {isRegister && strengthResult && (
              <PasswordStrengthMeter result={strengthResult} errors={passwordErrors} />
            )}
          </div>

          {error && (
            <div style={{ background: "#1f0f0f", border: "1px solid #7f1d1d", borderRadius: 6, padding: "9px 12px", color: "#f87171", fontSize: 13 }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={submitDisabled} style={submitDisabled ? btnDisabled : btn}>
            {loading
              ? (isRegister ? "Creating account…" : "Signing in…")
              : (isRegister ? "Create account"    : "Sign in")}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: 20, fontSize: 12, color: MUTED }}>
          {isRegister
            ? <>Already have an account?{" "}
                <span style={{ color: INDIGO, cursor: "pointer" }} onClick={() => switchTab("login")}>Sign in</span>
              </>
            : <>No account?{" "}
                <span style={{ color: INDIGO, cursor: "pointer" }} onClick={() => switchTab("register")}>Create one</span>
              </>}
        </div>
      </div>
    </div>
  )
}
