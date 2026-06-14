import { useState } from "react"
import Modal from "./Modal"
import { useAuth } from "../context/AuthContext"
import config from "../config"
import styles from "./AddChildModal.module.css"

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
  const [error, setError]         = useState("")
  const [loading, setLoading]     = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError("")

    const name = childName.trim()
    if (!name) { setError("Child name is required."); return }

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
    <div className={styles.panel}>
      <div className={styles.header}>
<h2 className={styles.heading}>Add a child</h2>
        <p className={styles.subheading}>
          Register a child profile and get an agent token to install on their PC.
        </p>
      </div>

      <form onSubmit={handleSubmit} className={styles.form}>
        <div>
          <label className={styles.label}>
            Child name <span className={styles.required}>*</span>
          </label>
          <input
            className={styles.input}
            type="text"
            placeholder="e.g. Alex"
            autoFocus
            value={childName}
            onChange={e => setChildName(e.target.value)}
            maxLength={64}
          />
        </div>

        {error && <div className={styles.errorBox}>{error}</div>}

        <div className={styles.formActions}>
          <button type="button" onClick={onCancel} className={styles.btnGhost}>
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className={styles.btnPrimary}
          >
            {loading ? "Creating…" : "Create child"}
          </button>
        </div>
      </form>
    </div>
  )
}

// ─── Step 2: Installer download ──────────────────────────────────────────────

const INSTALL_STEPS = [
  { n: 1, text: "Download the ZIP below and extract it to the child's PC (USB, shared folder, etc.)." },
  { n: 2, text: 'Double-click "hopmap_install.bat" and click Yes when Windows asks for admin permission.' },
  { n: 3, text: "The installer sets everything up and starts the agent immediately - no further steps needed." },
]

function StepInstaller({ result, onDone }) {
  const { authFetch } = useAuth()
  const [downloading, setDownloading] = useState(false)

  const { childName, childId } = result

  async function downloadInstaller() {
    setDownloading(true)
    try {
      const params = new URLSearchParams({ childId, backendUrl: config.backendUrl })
      const res = await authFetch(`/agent/installer?${params}`)
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement("a")
      a.href     = url
      a.download = `hopmap_${childName.replace(/\s+/g, "_").toLowerCase()}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error("Installer download failed:", err)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className={styles.panel}>
      <div className={styles.installerHeader}>
        <div className={styles.successIcon}>✓</div>
        <h2 className={styles.heading}>{childName} added</h2>
        <p className={styles.subheading}>
          Download the installer and run it on {childName}&apos;s PC to complete setup.
        </p>
      </div>

      <div className={styles.stepsSection}>
        <div className={styles.stepsLabel}>SETUP INSTRUCTIONS</div>
        {INSTALL_STEPS.map(({ n, text }) => (
          <div key={n} className={styles.stepItem}>
            <span className={styles.stepNum}>{n}</span>
            <span className={styles.stepText}>{text}</span>
          </div>
        ))}
      </div>

      <div className={styles.installerActions}>
        <button
          onClick={downloadInstaller}
          disabled={downloading}
          className={`${styles.btnGhost} ${styles.btnFlex}`}
        >
          {downloading ? "Preparing…" : "↓ Download Installer (.zip)"}
        </button>
        <button onClick={onDone} className={`${styles.btnPrimary} ${styles.btnFlex}`}>
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
  const [result, setResult] = useState(null)  // null = step 1, object = step 2

  function handleSuccess(data) {
    setResult(data)
    onCreated(data)
  }

  function handleDone() {
    setResult(null)
    onClose()
  }

  return (
    <Modal open={open} onClose={handleDone}>
      {result
        ? <StepInstaller result={result} onDone={handleDone} />
        : <StepForm onSuccess={handleSuccess} onCancel={handleDone} />
      }
    </Modal>
  )
}
