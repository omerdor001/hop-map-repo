import { useState, useEffect } from "react"
import { useNavigate, useSearchParams, Link } from "react-router-dom"
import zxcvbn from "zxcvbn"
import { BsEye, BsEyeSlash } from "react-icons/bs"
import { useAuth } from "../context/AuthContext"
import ForgotPasswordModal from "./ForgotPasswordModal"
import logo from "../assets/hopemap_logo_v3.svg"
import "./LoginPage.css"

const STRENGTH_META = [
  { label: "Too weak",    color: "#c0112a" },
  { label: "Weak",        color: "#e05a1a" },
  { label: "Fair",        color: "#d4a017" },
  { label: "Strong",      color: "#2a9d3f" },
  { label: "Very strong", color: "#1a7a30" },
]

const PASSWORD_RULES = [
  { test: v => v.length >= 8,           label: "At least 8 characters"  },
  { test: v => /[A-Z]/.test(v),         label: "One uppercase letter"   },
  { test: v => /[a-z]/.test(v),         label: "One lowercase letter"   },
  { test: v => /\d/.test(v),            label: "One digit"              },
  { test: v => /[^A-Za-z0-9]/.test(v), label: "One special character"  },
]

const MIN_SCORE = 2

function PasswordStrengthMeter({ result, errors }) {
  if (errors.length > 0) {
    return (
      <div className="lp-error-list">
        {errors.map(label => (
          <div key={label} className="lp-error-item">· {label}</div>
        ))}
      </div>
    )
  }
  const { score, feedback } = result
  const meta       = STRENGTH_META[score]
  const width      = `${(score + 1) / 5 * 100}%`
  const suggestion = feedback.suggestions[0] ?? feedback.warning ?? null
  return (
    <div className="lp-strength">
      <div className="lp-strength-track">
        <div className="lp-strength-bar" style={{ width, background: meta.color }} />
      </div>
      <div className="lp-strength-meta">
        <span style={{ color: meta.color, fontSize: 12, fontWeight: 500 }}>{meta.label}</span>
        {suggestion && <span className="lp-strength-hint">{suggestion}</span>}
      </div>
    </div>
  )
}

export default function LoginPage() {
  const { login, register, accessToken } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const isPremium = searchParams.get("plan") === "premium"

  const [tab, setTab]                 = useState(searchParams.get("tab") === "register" ? "register" : "login")
  const [email, setEmail]             = useState("")
  const [password, setPassword]       = useState("")
  const [displayName, setDisplayName] = useState("")
  const [error, setError]             = useState("")
  const [loading, setLoading]         = useState(false)
  const [showForgot, setShowForgot]   = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    if (accessToken) navigate("/app/kids", { replace: true })
  }, [accessToken, navigate])

  const isRegister     = tab === "register"
  const strengthResult = isRegister && password ? zxcvbn(password) : null
  const passwordErrors = isRegister && password
    ? PASSWORD_RULES.filter(r => !r.test(password)).map(r => r.label)
    : []
  const submitDisabled = loading || (
    isRegister && password.length > 0 && (passwordErrors.length > 0 || strengthResult?.score < MIN_SCORE)
  )

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      if (isRegister) {
        await register(email, password, displayName)
        navigate(isPremium ? "/app/settings?upgrade=1" : "/app/kids", { replace: true })
      } else {
        await login(email, password)
        navigate("/app/kids", { replace: true })
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
    setShowPassword(false)
  }

  return (
    <div className="lp-page">
      <div className="lp-card">
        <div className="lp-logo">
          <Link to="/" aria-label="Go to home page">
            <img src={logo} alt="HopMap" width={150} />
          </Link>
        </div>

        <div className="lp-tabs" role="tablist" aria-label="Authentication mode">
          {["login", "register"].map(t => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              onClick={() => switchTab(t)}
              className={`lp-tab${tab === t ? " lp-tab--active" : ""}`}
            >
              {t === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="lp-form">
          {isRegister && (
            <div className="lp-field">
              <label className="lp-label">Display name <span className="lp-optional">(optional)</span></label>
              <input
                className="lp-input"
                type="text"
                autoComplete="name"
                placeholder="Your name"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
              />
            </div>
          )}

          <div className="lp-field">
            <label className="lp-label">Email address</label>
            <input
              className="lp-input"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>

          <div className="lp-field">
            <label className="lp-label">Password</label>
            <div className="lp-pw-wrap">
              <input
                className="lp-input"
                type={showPassword ? "text" : "password"}
                autoComplete={isRegister ? "new-password" : "current-password"}
                placeholder="••••••••"
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="lp-pw-toggle"
                onClick={() => setShowPassword(p => !p)}
                disabled={loading}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <BsEyeSlash /> : <BsEye />}
              </button>
            </div>
            {isRegister && strengthResult && (
              <PasswordStrengthMeter result={strengthResult} errors={passwordErrors} />
            )}
          </div>

          {error && <div className="lp-error-box">{error}</div>}

          <button type="submit" disabled={submitDisabled} className="lp-submit">
            {loading
              ? (isRegister ? "Creating account…" : "Signing in…")
              : (isRegister ? "Create account"    : "Sign in")}
          </button>

          {!isRegister && (
            <button
              type="button"
              className="lp-footer-link"
              style={{ textAlign: "center", marginTop: 4 }}
              onClick={() => setShowForgot(true)}
            >
              Forgot password?
            </button>
          )}
        </form>

        <p className="lp-footer">
          {isRegister
            ? <>Already have an account?{" "}
                <button type="button" className="lp-footer-link" onClick={() => switchTab("login")}>Sign in</button>
              </>
            : <>No account?{" "}
                <button type="button" className="lp-footer-link" onClick={() => switchTab("register")}>Create one</button>
              </>}
        </p>
      </div>

      {showForgot && <ForgotPasswordModal onClose={() => setShowForgot(false)} />}
    </div>
  )
}
