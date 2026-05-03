import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import styles from "./Settings.module.css"

export default function Settings() {
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
        if (data) {
          setTelegramChatId(data.telegramChatId ?? null)
          setError("")
        }
      })
      .catch(err => {
        console.error("[Settings] failed to load account data:", err)
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
      window.open(url, "_blank", "noopener,noreferrer")
      // Poll once after a short delay to pick up the chat_id if the user linked fast
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
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.sectionLabel}>ACCOUNT</div>
        <h1 className={styles.heading}>Settings</h1>
        <p className={styles.subheading}>Manage account integrations.</p>
      </div>

      <div className={styles.card}>
        <div className={styles.cardInner}>
          <div className={styles.telegramIcon}>✈️</div>

          <div className={styles.cardContent}>
            <div className={styles.cardTitle}>Telegram Notifications</div>
            <div className={styles.cardDesc}>
              Get notified on Telegram when your child switches apps. Open the link below and start the bot to connect.
            </div>

            {!loading && (
              <div className={`${styles.statusBadge} ${isConnected ? styles.statusConnected : styles.statusDisconnected}`}>
                <span className={styles.statusDot}>●</span>
                {isConnected ? "Connected" : "Not connected"}
              </div>
            )}

            {error && (
              <div className={styles.errorBox}>{error}</div>
            )}

            <div className={styles.actions}>
              {!isConnected && (
                <button
                  onClick={handleConnect}
                  disabled={linking || loading}
                  className={styles.btnPrimary}
                >
                  {linking ? "Opening…" : "Connect Telegram"}
                </button>
              )}

              {isConnected && (
                <>
                  <button
                    onClick={handleConnect}
                    disabled={linking}
                    className={styles.btnOutline}
                  >
                    {linking ? "Opening…" : "Reconnect"}
                  </button>
                  <button
                    onClick={handleDisconnect}
                    disabled={unlinking}
                    className={styles.btnDanger}
                  >
                    {unlinking ? "Disconnecting…" : "Disconnect"}
                  </button>
                </>
              )}
            </div>

            {!isConnected && !loading && (
              <p className={styles.postNote}>
                After clicking "Connect Telegram", a Telegram window will open. Start the bot there to finish linking.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
