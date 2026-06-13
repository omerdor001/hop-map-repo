import { useState, useEffect, useRef } from "react"
import { useSearchParams, useNavigate, Link } from "react-router-dom"
import { BsEye, BsEyeSlash } from "react-icons/bs"
import { useAuth } from "../context/AuthContext"
import logo from "../assets/hopemap_logo_v3.svg"
import "./ResetPasswordPage.css"

const PASSWORD_RULES = [
  { test: v => v.length >= 8,           label: "At least 8 characters"  },
  { test: v => /[A-Z]/.test(v),         label: "One uppercase letter"   },
  { test: v => /[a-z]/.test(v),         label: "One lowercase letter"   },
  { test: v => /\d/.test(v),            label: "One digit"              },
  { test: v => /[^A-Za-z0-9]/.test(v), label: "One special character"  },
]

export default function ResetPasswordPage() {
  const { validateResetToken, resetPassword } = useAuth()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const token = searchParams.get("token") ?? ""

  const [validating, setValidating]           = useState(true)
  const [tokenValid, setTokenValid]           = useState(false)
  const [password, setPassword]               = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword]       = useState(false)
  const [showConfirm, setShowConfirm]         = useState(false)
  const [error, setError]                     = useState("")
  const [loading, setLoading]                 = useState(false)
  const [success, setSuccess]                 = useState(false)
  const redirectTimerRef                      = useRef(null)

  useEffect(() => {
    return () => { if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current) }
  }, [])

  useEffect(() => {
    if (!token) {
      setError("No reset token provided. Please check your email link.")
      setValidating(false)
      return
    }
    validateResetToken(token)
      .then(() => setTokenValid(true))
      .catch(err => setError(err.message || "Invalid or expired reset link. Please request a new one."))
      .finally(() => setValidating(false))
  }, [token, validateResetToken])

  const passwordErrors = password
    ? PASSWORD_RULES.filter(r => !r.test(password)).map(r => r.label)
    : []

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")

    if (password !== confirmPassword) {
      setError("Passwords do not match")
      return
    }
    if (passwordErrors.length > 0) {
      setError(passwordErrors[0])
      return
    }

    setLoading(true)
    try {
      await resetPassword(token, password)
      setSuccess(true)
      redirectTimerRef.current = setTimeout(() => navigate("/login", { replace: true }), 3000)
    } catch (err) {
      setError(err.message || "Failed to reset password")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rp-page">
      <div className="rp-card">
        <div className="rp-logo">
          <Link to="/" aria-label="Go to home page">
            <img src={logo} alt="HopMap" width={150} />
          </Link>
        </div>

        {validating && (
          <p className="rp-status">Validating reset link…</p>
        )}

        {!validating && !tokenValid && (
          <>
            <div className="rp-error-box">{error}</div>
            <button className="rp-submit" onClick={() => navigate("/login")}>
              Back to sign in
            </button>
          </>
        )}

        {!validating && tokenValid && !success && (
          <>
            <h1 className="rp-title">Reset password</h1>
            <p className="rp-desc">Enter your new password below.</p>

            <form onSubmit={handleSubmit} className="rp-form">
              {error && <div className="rp-error-box">{error}</div>}

              <div className="rp-field">
                <label className="rp-label">New password</label>
                <div className="rp-pw-wrap">
                  <input
                    className="rp-input"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    autoComplete="new-password"
                    required
                    autoFocus
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className="rp-pw-toggle"
                    onClick={() => setShowPassword(p => !p)}
                    disabled={loading}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <BsEyeSlash /> : <BsEye />}
                  </button>
                </div>
                {password.length > 0 && (
                  <div className="rp-rules">
                    {PASSWORD_RULES.map(rule => {
                      const met = rule.test(password)
                      return (
                        <div key={rule.label} className={`rp-rule${met ? " rp-rule--met" : ""}`}>
                          {met ? "✓" : "·"} {rule.label}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="rp-field">
                <label className="rp-label">Confirm password</label>
                <div className="rp-pw-wrap">
                  <input
                    className="rp-input"
                    type={showConfirm ? "text" : "password"}
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                    required
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className="rp-pw-toggle"
                    onClick={() => setShowConfirm(p => !p)}
                    disabled={loading}
                    aria-label={showConfirm ? "Hide password" : "Show password"}
                  >
                    {showConfirm ? <BsEyeSlash /> : <BsEye />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="rp-submit"
                disabled={loading || passwordErrors.length > 0}
              >
                {loading ? "Resetting…" : "Reset password"}
              </button>
            </form>
          </>
        )}

        {success && (
          <div className="rp-success">
            <h2 className="rp-title">Password reset!</h2>
            <p className="rp-desc">Your password has been updated successfully.</p>
            <p className="rp-hint">Redirecting to sign in…</p>
          </div>
        )}
      </div>
    </div>
  )
}
