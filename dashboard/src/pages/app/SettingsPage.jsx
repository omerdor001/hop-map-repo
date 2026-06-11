import { useState, useEffect, useCallback } from "react"
import { FaTelegram } from "react-icons/fa"
import { useAuth } from "../../context/AuthContext"
import "./SettingsPage.css"

export default function SettingsPage() {
  const { authFetch } = useAuth()
  const [telegramChatId, setTelegramChatId] = useState(null)
  const [loading, setLoading]               = useState(true)
  const [linking, setLinking]               = useState(false)
  const [unlinking, setUnlinking]           = useState(false)
  const [error, setError]                   = useState("")

  const fetchMe = useCallback(() => {
    setLoading(true)
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        setTelegramChatId(data?.telegramChatId ?? null)
        setError("")
      })
      .catch(err => {
        console.error("[SettingsPage] failed to load account data:", err)
        setError("Failed to load account data. Please refresh.")
      })
      .finally(() => setLoading(false))
  }, [authFetch])

  useEffect(() => { fetchMe() }, [fetchMe])

  async function handleConnect() {
    setLinking(true)
    setError("")
    try {
      const res = await authFetch("/api/me/telegram/link", { method: "POST" })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || "Failed to generate link")
      }
      const { url } = await res.json()
      const win = window.open(url, "_blank", "noopener,noreferrer")
      if (!win) {
        setError("Popup blocked. Please allow popups for this site and try again.")
        return
      }
      // Poll once after a delay in case the user linked immediately
      setTimeout(fetchMe, 5000)
    } catch (e) {
      setError(e.message)
    } finally {
      setLinking(false)
    }
  }

  async function handleDisconnect() {
    setUnlinking(true)
    setError("")
    try {
      const res = await authFetch("/api/me/telegram", { method: "DELETE" })
      if (!res.ok) throw new Error("Failed to disconnect")
      setTelegramChatId(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setUnlinking(false)
    }
  }

  const isConnected = Boolean(telegramChatId)

  return (
    <div className="settings-page">
      <p className="settings-page-label">Account</p>
      <h1 className="settings-page-title">Settings</h1>
      <p className="settings-page-subtitle">Manage your account integrations.</p>

      <div className="settings-card">
        <div className="settings-card-icon">
          <FaTelegram size={22} />
        </div>

        <div className="settings-card-body">
          <h3 className="settings-card-title">Telegram Notifications</h3>
          <p className="settings-card-desc">
            Receive an instant alert on Telegram every time your child attempts a platform hop —
            including the app name, time, and risk level.
          </p>

          {!loading && (
            <div className={`settings-status${isConnected ? " settings-status--on" : " settings-status--off"}`}>
              <span className="settings-status-dot" />
              {isConnected ? "Connected" : "Not connected"}
            </div>
          )}

          {error && <div className="settings-error">{error}</div>}

          <div className="settings-actions">
            {!isConnected && (
              <button
                className="settings-btn-primary"
                onClick={handleConnect}
                disabled={linking || loading}
              >
                {linking ? "Opening…" : "Connect Telegram"}
              </button>
            )}

            {isConnected && (
              <>
                <button
                  className="settings-btn-outline"
                  onClick={handleConnect}
                  disabled={linking}
                >
                  {linking ? "Opening…" : "Reconnect"}
                </button>
                <button
                  className="settings-btn-danger"
                  onClick={handleDisconnect}
                  disabled={unlinking}
                >
                  {unlinking ? "Disconnecting…" : "Disconnect"}
                </button>
              </>
            )}
          </div>

          {!isConnected && !loading && (
            <p className="settings-hint">
              A Telegram window will open — click <strong>Start</strong> on the bot to finish linking.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
