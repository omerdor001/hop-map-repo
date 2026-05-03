import { useState } from "react"
import zxcvbn from "zxcvbn"
import { useAuth } from "../context/AuthContext"
import styles from "./Login.module.css"

const STRENGTH_META = [
  { label: "Too weak",    color: "var(--color-strength-0)" },
  { label: "Weak",        color: "var(--color-strength-1)" },
  { label: "Fair",        color: "var(--color-strength-2)" },
  { label: "Strong",      color: "var(--color-strength-3)" },
  { label: "Very strong", color: "var(--color-strength-4)" },
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

function getPasswordErrors(password) {
  return PASSWORD_RULES.filter(rule => !rule.test(password)).map(rule => rule.label)
}

function PasswordStrengthMeter({ result, errors }) {
  // Show unmet requirements as a checklist while any are failing.
  // Only switch to the entropy strength bar once all requirements pass.
  if (errors.length > 0) {
    return (
      <div className={styles.errorList}>
        {errors.map(label => (
          <div key={label} className={styles.errorItem}>· {label}</div>
        ))}
      </div>
    )
  }

  const score      = result.score
  const meta       = STRENGTH_META[score]
  const width      = `${(score + 1) / 5 * 100}%`
  const suggestion = result.feedback.suggestions[0] ?? result.feedback.warning ?? null

  return (
    <div className={styles.strengthMeter}>
      <div className={styles.strengthTrack}>
        {/* width and background are data-driven — stay inline */}
        <div className={styles.strengthBar} style={{ width, background: meta.color }} />
      </div>
      <div className={styles.strengthMeta}>
        <span className={styles.strengthLabel} style={{ color: meta.color }}>{meta.label}</span>
        {suggestion && <span className={styles.strengthHint}>{suggestion}</span>}
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
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <div className={styles.brandName}>
            hop<span className={styles.brandAccent}>map</span>
          </div>
          <div className={styles.brandSub}>Parent dashboard</div>
        </div>

        <div className={styles.tabs}>
          {["login", "register"].map(t => (
            <button
              key={t}
              onClick={() => switchTab(t)}
              className={tab === t ? `${styles.tab} ${styles.tabActive}` : styles.tab}
            >
              {t === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {isRegister && (
            <div>
              <label className={styles.label}>Display name (optional)</label>
              <input
                className={styles.input}
                type="text"
                autoComplete="name"
                placeholder="Parent name"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
              />
            </div>
          )}

          <div>
            <label className={styles.label}>Email address</label>
            <input
              className={styles.input}
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className={styles.label}>
              Password
              {isRegister && (
                <span className={styles.labelHint}>
                  min 8 chars · uppercase · lowercase · digit · special character
                </span>
              )}
            </label>
            <input
              className={styles.input}
              type="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              placeholder="••••••••"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
            {isRegister && strengthResult && (
              <PasswordStrengthMeter result={strengthResult} errors={passwordErrors} />
            )}
          </div>

          {error && <div className={styles.errorBox}>{error}</div>}

          <button type="submit" disabled={submitDisabled} className={styles.btn}>
            {loading
              ? (isRegister ? "Creating account…" : "Signing in…")
              : (isRegister ? "Create account"    : "Sign in")}
          </button>
        </form>

        <div className={styles.footer}>
          {isRegister
            ? <>Already have an account?{" "}
                <button type="button" className={styles.footerLink} onClick={() => switchTab("login")}>Sign in</button>
              </>
            : <>No account?{" "}
                <button type="button" className={styles.footerLink} onClick={() => switchTab("register")}>Create one</button>
              </>}
        </div>
      </div>
    </div>
  )
}
