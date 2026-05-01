import { useState, useEffect, useCallback } from "react"
import { useAuth } from "../context/AuthContext"
import { colors, fonts } from "../utils/theme"

export default function Settings() {
  const { authFetch } = useAuth()
  const [telegramChatId, setTelegramChatId] = useState(undefined)
  const [loading, setLoading]               = useState(true)
  const [linking, setLinking]               = useState(false)
  const [unlinking, setUnlinking]           = useState(false)
  const [error, setError]                   = useState("")

  const fetchMe = useCallback(() => {
    setLoading(true)
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) setTelegramChatId(data.telegramChatId ?? null)
      })
      .catch(() => {})
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
    <div style={{ padding: "40px 48px", maxWidth: 700, margin: "0 auto", fontFamily: fonts.sans }}>
      {/* Header */}
      <div style={{ marginBottom: 36 }}>
        <div style={{
          fontSize: 11, fontWeight: 700, letterSpacing: "0.12em",
          color: colors.indigo, marginBottom: 6, fontFamily: fonts.mono,
        }}>
          ACCOUNT
        </div>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: colors.text }}>Settings</h1>
        <p style={{ margin: "8px 0 0", color: colors.muted, fontSize: 14 }}>
          Manage account integrations.
        </p>
      </div>

      {/* Telegram section */}
      <div style={{
        background: colors.surface, border: `1px solid ${colors.border}`,
        borderRadius: 12, padding: "24px 28px",
      }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, flexShrink: 0,
            background: "rgba(37,99,235,0.15)",
            display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
          }}>✈️</div>

          <div style={{ width: "100%", display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: colors.text, marginBottom: 4 }}>
              Telegram Notifications
            </div>
            <div style={{ fontSize: 13, color: colors.muted, marginBottom: 16, maxWidth: 460 }}>
              Get notified on Telegram when your child switches apps. Open the link below and start the bot to connect.
            </div>

            {/* Status badge */}
            {!loading && (
              <div style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                fontSize: 12, fontWeight: 700, fontFamily: fonts.mono,
                color: isConnected ? colors.success : colors.muted,
                background: isConnected ? "rgba(46,213,115,0.1)" : "rgba(75,82,104,0.15)",
                border: `1px solid ${isConnected ? "rgba(46,213,115,0.3)" : colors.border}`,
                borderRadius: 6, padding: "3px 10px", marginBottom: 16,
              }}>
                <span style={{ fontSize: 8, lineHeight: 1 }}>●</span>
                {isConnected ? "Connected" : "Not connected"}
              </div>
            )}

            {error && (
              <div style={{
                background: "rgba(255,71,87,0.08)", border: `1px solid rgba(255,71,87,0.3)`,
                borderRadius: 8, color: colors.danger, fontSize: 13,
                padding: "10px 14px", marginBottom: 16,
              }}>
                {error}
              </div>
            )}

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
              {!isConnected && (
                <button
                  onClick={handleConnect}
                  disabled={linking || loading}
                  style={{
                    background: linking || loading ? colors.surface : colors.indigo,
                    color: linking || loading ? colors.muted : "#fff",
                    border: "none", borderRadius: 8, fontSize: 14, fontWeight: 700,
                    padding: "10px 22px", cursor: linking || loading ? "not-allowed" : "pointer",
                    transition: "background 0.15s",
                  }}
                >
                  {linking ? "Opening…" : "Connect Telegram"}
                </button>
              )}

              {isConnected && (
                <>
                  <button
                    onClick={handleConnect}
                    disabled={linking}
                    style={{
                      background: "transparent",
                      color: linking ? colors.muted : colors.indigoLight,
                      border: `1px solid ${linking ? colors.border : colors.indigo}`,
                      borderRadius: 8, fontSize: 14, fontWeight: 600,
                      padding: "10px 22px", cursor: linking ? "not-allowed" : "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    {linking ? "Opening…" : "Reconnect"}
                  </button>
                  <button
                    onClick={handleDisconnect}
                    disabled={unlinking}
                    style={{
                      background: "transparent",
                      color: unlinking ? colors.muted : colors.danger,
                      border: `1px solid ${unlinking ? colors.border : "rgba(255,71,87,0.4)"}`,
                      borderRadius: 8, fontSize: 14, fontWeight: 600,
                      padding: "10px 22px", cursor: unlinking ? "not-allowed" : "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    {unlinking ? "Disconnecting…" : "Disconnect"}
                  </button>
                </>
              )}
            </div>

            {!isConnected && !loading && (
              <p style={{ margin: "12px 0 0", fontSize: 12, color: colors.muted, maxWidth: 460 }}>
                After clicking "Connect Telegram", a Telegram window will open. Start the bot there to finish linking.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
