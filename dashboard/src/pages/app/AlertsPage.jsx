import { useState, useCallback, useEffect, useRef } from "react"
import { FaTelegram } from "react-icons/fa"
import { useAuth } from "../../context/AuthContext"
import "./AlertsPage.css"

const POLL_INTERVAL_MS = 3_000
const POLL_TIMEOUT_MS  = 120_000

export default function AlertsPage() {
  const { authFetch } = useAuth()

  const pollIntervalRef = useRef(null)
  const pollTimeoutRef  = useRef(null)
  const isPollingRef    = useRef(false)
  const authFetchRef    = useRef(authFetch)
  useEffect(() => { authFetchRef.current = authFetch }, [authFetch])

  const [telegramChatId, setTelegramChatId] = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [linking,     setLinking]     = useState(false)
  const [polling,     setPolling]     = useState(false)
  const [unlinking,   setUnlinking]   = useState(false)
  const [error,       setError]       = useState("")
  const [fallbackUrl, setFallbackUrl] = useState(null)

  const stopPolling = useCallback(() => {
    clearInterval(pollIntervalRef.current)
    clearTimeout(pollTimeoutRef.current)
    isPollingRef.current = false
    setPolling(false)
  }, [])

  const runPoll = useCallback(async () => {
    if (!isPollingRef.current) return
    try {
      const r = await authFetchRef.current("/api/me")
      if (!r.ok) return
      const data = await r.json()
      if (data?.telegramChatId) {
        setTelegramChatId(data.telegramChatId)
        setFallbackUrl(null)
        stopPolling()
      }
    } catch {
      // transient error — keep polling
    }
  }, [stopPolling])

  const fetchMe = useCallback(() => {
    setLoading(true)
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        setTelegramChatId(data?.telegramChatId ?? null)
        setError("")
      })
      .catch(err => {
        console.error("[AlertsPage] failed to load account data:", err)
        setError("Failed to load account data. Please refresh.")
      })
      .finally(() => setLoading(false))
  }, [authFetch])

  useEffect(() => { fetchMe() }, [fetchMe])

  // Immediate poll when user tabs back after clicking /start in Telegram
  useEffect(() => {
    const onVisible = () => { if (isPollingRef.current) runPoll() }
    document.addEventListener("visibilitychange", onVisible)
    return () => document.removeEventListener("visibilitychange", onVisible)
  }, [runPoll])

  useEffect(() => () => stopPolling(), [stopPolling])

  function startPolling() {
    isPollingRef.current    = true
    setPolling(true)
    pollIntervalRef.current = setInterval(runPoll, POLL_INTERVAL_MS)
    pollTimeoutRef.current  = setTimeout(() => {
      stopPolling()
      setError("Connection timed out. Please try again.")
    }, POLL_TIMEOUT_MS)
  }

  const handleConnect = useCallback(async () => {
    setLinking(true)
    setError("")
    setFallbackUrl(null)
    stopPolling()
    try {
      const res = await authFetch("/api/me/telegram/link", { method: "POST" })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || "Failed to generate link")
      }
      const { url } = await res.json()
      const win = window.open(url, "_blank")
      if (!win) {
        setFallbackUrl(url)
        setError("Popup blocked — open the link below instead.")
      }
      // Start polling regardless; user may open the link via the fallback
      startPolling()
    } catch (e) {
      setError(e.message)
    } finally {
      setLinking(false)
    }
  }, [authFetch, stopPolling]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleCancel = useCallback(() => {
    stopPolling()
    setFallbackUrl(null)
    setError("")
  }, [stopPolling])

  const handleDisconnect = useCallback(async () => {
    setUnlinking(true)
    setError("")
    try {
      const res = await authFetch("/api/me/telegram", { method: "DELETE" })
      if (!res.ok) throw new Error("Failed to disconnect. Please try again.")
      setTelegramChatId(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setUnlinking(false)
    }
  }, [authFetch])

  const isConnected = Boolean(telegramChatId)

  return (
    <div className="alerts-page">
      <h1 className="alerts-page-title">Alerts</h1>
      <p className="alerts-page-subtitle">
        Connect a notification channel to get instant alerts when a platform hop is detected.
      </p>

      <div className="alerts-cards">
        <div className="alerts-card">
          <div className="alerts-card-icon">
            <FaTelegram size={22} />
          </div>

          <div className="alerts-card-body">
            <h3 className="alerts-card-title">Telegram Notifications</h3>
            <p className="alerts-card-desc">
              Receive an instant alert on Telegram every time your child attempts a platform
              hop — including the app name, time, and risk level.
            </p>

            {!loading && (
              <div className={`alerts-status${isConnected ? " alerts-status--on" : " alerts-status--off"}`}>
                <span className="alerts-status-dot" />
                {isConnected ? "Connected" : polling ? "Connecting…" : "Not connected"}
              </div>
            )}

            {error && (
              <div className="alerts-error" role="alert">
                {error}
                {fallbackUrl && (
                  <a
                    href={fallbackUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="alerts-error-link"
                  >
                    Open Telegram manually →
                  </a>
                )}
              </div>
            )}

            <div className="alerts-actions">
              {!isConnected && !polling && (
                <button
                  className="alerts-btn-primary"
                  onClick={handleConnect}
                  disabled={linking || loading}
                >
                  {linking ? "Opening…" : "Connect Telegram"}
                </button>
              )}

              {!isConnected && polling && (
                <button className="alerts-btn-outline" onClick={handleCancel}>
                  Cancel
                </button>
              )}

              {isConnected && (
                <>
                  <button
                    className="alerts-btn-outline"
                    onClick={handleConnect}
                    disabled={linking || polling}
                  >
                    {linking ? "Opening…" : polling ? "Waiting…" : "Reconnect"}
                  </button>
                  <button
                    className="alerts-btn-danger"
                    onClick={handleDisconnect}
                    disabled={unlinking}
                  >
                    {unlinking ? "Disconnecting…" : "Disconnect"}
                  </button>
                </>
              )}
            </div>

            {!isConnected && !loading && (
              <p className="alerts-hint">
                {polling
                  ? <>Waiting for you to click <strong>Start</strong> in the Telegram bot…</>
                  : <>A Telegram window will open — click <strong>Start</strong> on the bot to finish linking.</>
                }
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
