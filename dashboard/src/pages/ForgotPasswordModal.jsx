import { useState } from "react"
import { useAuth } from "../context/AuthContext"
import "./ForgotPasswordModal.css"

export default function ForgotPasswordModal({ onClose }) {
  const { forgotPassword } = useAuth()
  const [email, setEmail]             = useState("")
  const [submittedEmail, setSubmittedEmail] = useState("")
  const [error, setError]             = useState("")
  const [loading, setLoading]         = useState(false)
  const [success, setSuccess]         = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await forgotPassword(email.toLowerCase())
      setSubmittedEmail(email.toLowerCase())
      setSuccess(true)
    } catch (err) {
      setError(err.message || "Failed to process password reset request")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fp-overlay" onClick={onClose}>
      <div className="fp-modal" role="dialog" aria-modal="true" aria-labelledby="fp-modal-title" onClick={e => e.stopPropagation()}>
        <button className="fp-close" onClick={onClose} aria-label="Close">✕</button>

        {success ? (
          <div className="fp-content">
            <h2 id="fp-modal-title" className="fp-title">Check your email</h2>
            <p className="fp-desc">
              If an account exists for <strong>{submittedEmail}</strong>, you will receive a
              password reset link shortly.
            </p>
            <p className="fp-hint">The link expires soon — check your inbox now.</p>
            <button className="fp-submit" onClick={onClose}>Back to sign in</button>
          </div>
        ) : (
          <div className="fp-content">
            <h2 id="fp-modal-title" className="fp-title">Reset password</h2>
            <p className="fp-desc">
              Enter your email address and we'll send you a link to reset your password.
            </p>

            <form className="fp-form" onSubmit={handleSubmit}>
              {error && <div className="fp-error">{error}</div>}

              <div className="fp-field">
                <label className="fp-label">Email address</label>
                <input
                  className="fp-input"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoFocus
                  disabled={loading}
                />
              </div>

              <button type="submit" className="fp-submit" disabled={loading}>
                {loading ? "Sending…" : "Send reset link"}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
