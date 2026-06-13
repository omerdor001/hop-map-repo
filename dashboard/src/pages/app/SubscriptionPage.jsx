import { useState, useEffect, useCallback } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { FaCrown, FaUser } from "react-icons/fa"
import { useAuth } from "../../context/AuthContext"
import "./SubscriptionPage.css"

export default function SubscriptionPage() {
  const { authFetch }  = useAuth()
  const navigate       = useNavigate()
  const [searchParams] = useSearchParams()

  const [showUpgradeBanner] = useState(() => searchParams.get("upgrade") === "1")
  useEffect(() => {
    if (showUpgradeBanner) {
      navigate("/app/subscription", { replace: true })
    }
  }, [showUpgradeBanner, navigate])

  const [plan, setPlan]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState("")

  const fetchMe = useCallback(() => {
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        setPlan(data?.plan ?? "free")
        setError("")
      })
      .catch(err => {
        console.error("[SubscriptionPage] failed to load account data:", err)
        setError("Failed to load account data. Please refresh.")
      })
      .finally(() => setLoading(false))
  }, [authFetch])

  useEffect(() => {
    fetchMe()
  }, [fetchMe])

  const isPremium = plan === "premium"

  return (
    <div className="sub-page">
<h1 className="sub-page-title">Subscription</h1>
      <p className="sub-page-subtitle">
        Manage your plan and unlock more features for your family.
      </p>

      {showUpgradeBanner && (
        <div className="sub-upgrade-banner">
          Account created. Upgrade below to unlock Premium.
        </div>
      )}

      {error && <div className="sub-error" role="alert">{error}</div>}

      <div className="sub-cards">
        <div className={`sub-card${isPremium ? " sub-card--premium" : ""}`}>
          <div className="sub-card-icon">
            {isPremium ? <FaCrown size={22} /> : <FaUser size={22} />}
          </div>

          <div className="sub-card-body">
            <div className="sub-card-header">
              <h3 className="sub-card-title">
                {loading ? "Loading…" : isPremium ? "Premium" : "Basic"}
              </h3>
              {!loading && (
                <span className={`sub-plan-badge${isPremium ? " sub-plan-badge--premium" : ""}`}>
                  {isPremium ? "Active" : "Free tier"}
                </span>
              )}
            </div>

            {!loading && <ul className="sub-features">
              {isPremium ? (
                <>
                  <li className="sub-feature sub-feature--on">✓ Unlimited children monitored</li>
                  <li className="sub-feature sub-feature--on">✓ Unlimited alerts to parent</li>
                  <li className="sub-feature sub-feature--on">✓ Real-time alerts</li>
                  <li className="sub-feature sub-feature--on">✓ Monthly activity summary</li>
                  <li className="sub-feature sub-feature--on">✓ Priority support</li>
                </>
              ) : (
                <>
                  <li className="sub-feature sub-feature--on">✓ 1 child monitored</li>
                  <li className="sub-feature sub-feature--on">✓ Up to 10 alerts</li>
                  <li className="sub-feature sub-feature--on">✓ Real-time alerts</li>
                  <li className="sub-feature sub-feature--off">✕ Monthly summary</li>
                  <li className="sub-feature sub-feature--off">✕ Additional children</li>
                </>
              )}
            </ul>}

            {!isPremium && !loading && (
              <div className="sub-actions">
                <button className="sub-btn-primary" disabled>
                  Upgrade to Premium — coming soon
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
