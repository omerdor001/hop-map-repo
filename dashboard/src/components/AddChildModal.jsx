import { useState, useCallback, useEffect, useRef } from "react"
import Modal from "./Modal"
import { useAuth } from "../context/AuthContext"

// ─── Design tokens (match existing dashboard palette) ───────────────────────
const DARK   = "#0d0d0f"
const CARD   = "#16161a"
const BORDER = "#1e1e24"
const INDIGO = "#6366f1"
const MUTED  = "#6b7280"
const ERROR_BG   = "#1f0f0f"
const ERROR_BORDER = "#7f1d1d"

const panelStyle = {
  background: CARD,
  border: `1px solid ${BORDER}`,
  borderRadius: 16,
  padding: "36px 32px",
  width: 440,
  boxSizing: "border-box",
}

const labelStyle = { fontSize: 12, color: MUTED, display: "block", marginBottom: 6 }

const inputStyle = {
  width: "100%",
  background: DARK,
  border: `1px solid ${BORDER}`,
  borderRadius: 8,
  color: "#fff",
  fontSize: 14,
  padding: "10px 14px",
  outline: "none",
  boxSizing: "border-box",
  fontFamily: "inherit",
}

const inputFocusStyle = { ...inputStyle, border: `1px solid ${INDIGO}` }

const btnPrimary = {
  background: INDIGO,
  color: "#fff",
  border: "none",
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 700,
  padding: "10px 20px",
  cursor: "pointer",
}

const btnGhost = {
  background: "transparent",
  color: MUTED,
  border: `1px solid ${BORDER}`,
  borderRadius: 8,
  fontSize: 14,
  padding: "10px 20px",
  cursor: "pointer",
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function generateId() {
  // Use crypto.randomUUID when available (all modern browsers), strip dashes for
  // readability, take first 12 chars as a short child ID.
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, "").slice(0, 12)
  }
  return Math.random().toString(36).slice(2, 14)
}

// ─── Step 1: Creation form ────────────────────────────────────────────────────

function StepForm({ onSuccess, onCancel }) {
  const { authFetch } = useAuth()
  const [childName, setChildName] = useState("")
  const [nameFocused, setNameFocused] = useState(false)
  const [error, setError]         = useState("")
  const [loading, setLoading]     = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")

    const name = childName.trim()
    if (!name) { setError("Child name is required."); return }

    // Generate the ID internally — the parent never needs to see or manage it.
    const id = generateId()

    setLoading(true)
    try {
      const res = await authFetch("/api/children", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ childId: id, childName: name }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || "Failed to register child.")
        return
      }
      onSuccess(data)
    } catch {
      setError("Network error. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: INDIGO, marginBottom: 6 }}>
          ACCOUNT
        </div>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#fff" }}>Add a child</h2>
        <p style={{ margin: "8px 0 0", color: MUTED, fontSize: 13, lineHeight: 1.5 }}>
          Register a child profile and get an agent token to install on their PC.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div>
          <label style={labelStyle}>Child name <span style={{ color: "#ef4444" }}>*</span></label>
          <input
            style={nameFocused ? inputFocusStyle : inputStyle}
            type="text"
            placeholder="e.g. Alex"
            autoFocus
            value={childName}
            onChange={e => setChildName(e.target.value)}
            onFocus={() => setNameFocused(true)}
            onBlur={() => setNameFocused(false)}
            maxLength={64}
          />
        </div>

        {error && (
          <div style={{
            background: ERROR_BG, border: `1px solid ${ERROR_BORDER}`,
            borderRadius: 6, padding: "9px 12px", color: "#f87171", fontSize: 13,
          }}>
            {error}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 4 }}>
          <button type="button" onClick={onCancel} style={btnGhost}>Cancel</button>
          <button
            type="submit"
            disabled={loading}
            style={loading ? { ...btnPrimary, opacity: 0.5, cursor: "not-allowed" } : btnPrimary}
          >
            {loading ? "Creating…" : "Create child"}
          </button>
        </div>
      </form>
    </div>
  )
}

// ─── Step 2: Token reveal ─────────────────────────────────────────────────────

function StepToken({ result, onDone, confirmClose, onConfirmDiscard, onCancelDiscard }) {
  const [copied, setCopied] = useState(false)
  const copyTimeoutRef = useRef(null)

  // Clear any pending timeout on unmount to avoid setState on unmounted component
  useEffect(() => () => clearTimeout(copyTimeoutRef.current), [])

  const { agentToken, childName } = result

  function copyToken() {
    navigator.clipboard.writeText(agentToken).then(() => {
      setCopied(true)
      clearTimeout(copyTimeoutRef.current)
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2500)
    })
  }

  function downloadConfig() {
    // Produce a ready-to-use agent_config.json — token is the only credential needed
    const config = {
      backend_url: window.location.origin,
      ollama_model: "qwen2.5:7b",
      scan_interval_seconds: 5.0,
      context_lines: 10,
      agent_token: agentToken,
    }
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement("a")
    a.href     = url
    a.download = `agent_config_${childName.replace(/\s+/g, "_").toLowerCase()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{
          width: 44, height: 44, borderRadius: "50%",
          background: "linear-gradient(135deg,#22c55e,#16a34a)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 22, marginBottom: 16,
        }}>✓</div>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: "#fff" }}>
          {childName} added
        </h2>
        <p style={{ margin: "8px 0 0", color: MUTED, fontSize: 13, lineHeight: 1.5 }}>
          Copy the agent token below and install it on {childName}&apos;s PC.
        </p>
      </div>

      {/* Warning banner */}
      <div style={{
        display: "flex", alignItems: "flex-start", gap: 10,
        background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.3)",
        borderRadius: 8, padding: "10px 14px", marginBottom: 20,
      }}>
        <span style={{ fontSize: 15, flexShrink: 0, marginTop: 1 }}>⚠️</span>
        <span style={{ fontSize: 13, color: "#fbbf24", lineHeight: 1.5 }}>
          This token will <strong>not</strong> be shown again. Copy it now or download the config file.
        </span>
      </div>

      {/* Token box */}
      <div style={{ marginBottom: 12 }}>
        <label style={labelStyle}>Agent token</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            readOnly
            value={agentToken}
            style={{
              ...inputStyle,
              fontFamily: "'IBM Plex Mono', 'Courier New', monospace",
              fontSize: 12,
              color: "#a5b4fc",
              flex: 1,
              cursor: "text",
            }}
            onFocus={e => e.target.select()}
          />
          <button
            onClick={copyToken}
            style={{
              ...btnPrimary,
              padding: "10px 16px",
              flexShrink: 0,
              background: copied ? "#16a34a" : INDIGO,
              transition: "background 0.2s",
            }}
          >
            {copied ? "✓ Copied" : "Copy"}
          </button>
        </div>
      </div>

      {/* Install instructions */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#4b5563", marginBottom: 10, letterSpacing: "0.08em" }}>
          SETUP INSTRUCTIONS
        </div>
        {[
          { n: 1, text: "Download the config file below or copy the token above." },
          { n: 2, text: "On the child's PC, place agent_config.json next to agent.py." },
          { n: 3, text: "Run: python agent.py — the agent will connect automatically." },
        ].map(({ n, text }) => (
          <div key={n} style={{ display: "flex", gap: 12, marginBottom: 8, alignItems: "flex-start" }}>
            <span style={{
              width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
              background: "rgba(99,102,241,0.2)", border: `1px solid rgba(99,102,241,0.4)`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontWeight: 700, color: "#818cf8",
            }}>{n}</span>
            <span style={{ fontSize: 13, color: MUTED, lineHeight: 1.5 }}>{text}</span>
          </div>
        ))}
      </div>

      {/* Inline discard confirmation — replaces window.confirm() */}
      {confirmClose && (
        <div style={{
          background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.35)",
          borderRadius: 8, padding: "12px 14px", marginBottom: 16,
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        }}>
          <span style={{ fontSize: 13, color: "#fca5a5" }}>
            The token won&apos;t be shown again. Close anyway?
          </span>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <button onClick={onCancelDiscard} style={{ ...btnGhost, padding: "6px 12px", fontSize: 12 }}>
              Stay
            </button>
            <button onClick={onConfirmDiscard} style={{ ...btnPrimary, background: "#ef4444", padding: "6px 12px", fontSize: 12 }}>
              Close
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={downloadConfig} style={{ ...btnGhost, flex: 1 }}>
          ↓ Download agent_config.json
        </button>
        <button onClick={onDone} style={{ ...btnPrimary, flex: 1 }}>
          Done
        </button>
      </div>
    </div>
  )
}

// ─── Exported modal ───────────────────────────────────────────────────────────

/**
 * Two-step modal for registering a new child.
 *
 * Props:
 *   open      {boolean}   — whether modal is shown
 *   onClose   {function}  — close callback (no args)
 *   onCreated {function}  — called with the new child object after registration
 */
export default function AddChildModal({ open, onClose, onCreated }) {
  const [result, setResult]           = useState(null)  // null = step 1, object = step 2
  const [confirmClose, setConfirmClose] = useState(false)

  function handleSuccess(data) {
    setResult(data)
    onCreated(data)
  }

  // When on the token step, show an inline confirmation banner instead of
  // a blocking window.confirm() dialog.
  const handleClose = useCallback(() => {
    if (result) {
      setConfirmClose(true)
    } else {
      setResult(null)
      onClose()
    }
  }, [result, onClose])

  function handleDone() {
    setResult(null)
    setConfirmClose(false)
    onClose()
  }

  function handleConfirmDiscard() {
    setResult(null)
    setConfirmClose(false)
    onClose()
  }

  return (
    <Modal open={open} onClose={handleClose}>
      {result
        ? <StepToken
            result={result}
            onDone={handleDone}
            confirmClose={confirmClose}
            onConfirmDiscard={handleConfirmDiscard}
            onCancelDiscard={() => setConfirmClose(false)}
          />
        : <StepForm onSuccess={handleSuccess} onCancel={handleClose} />
      }
    </Modal>
  )
}
