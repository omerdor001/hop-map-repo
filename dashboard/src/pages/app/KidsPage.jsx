import { useState, useEffect } from "react"
import { FaTrash, FaDownload } from "react-icons/fa"
import { useAuth } from "../../context/AuthContext"
import { useChildren } from "../../context/ChildrenContext"
import { useTheme } from "../../context/useTheme"
import AddChildModal from "../../components/AddChildModal"
import config from "../../config"
import "./KidsPage.css"

function DeleteChildModal({ childName, onConfirm, onCancel, deleting, error }) {
  return (
    <div className="kids-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title">
      <div className="kids-modal">
        <h3 id="delete-modal-title" className="kids-modal-title">Remove child?</h3>
        <p className="kids-modal-body">
          This will permanently remove <strong>{childName}</strong> and all their monitoring data.
        </p>
        {error && <p className="kids-modal-error">{error}</p>}
        <div className="kids-modal-actions">
          <button className="kid-btn-cancel-modal" onClick={onCancel} disabled={deleting}>Cancel</button>
          <button className="kid-btn-delete-confirm" onClick={onConfirm} disabled={deleting}>
            {deleting ? "Removing…" : "Remove"}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function KidsPage() {
  const { authFetch }                                     = useAuth()
  const { childList: children, refreshChildren, childrenError } = useChildren()
  const { setMode }                                        = useTheme()
  const [maxChildren, setMaxChildren] = useState(null)
  const [fetchError, setFetchError]   = useState(null)
  const [editing, setEditing]         = useState({})
  const [saving, setSaving]           = useState({})
  const [saved, setSaved]             = useState({})
  const [fieldErrors, setFieldErrors] = useState({})
  const [addOpen, setAddOpen]         = useState(false)
  const [deleteModal, setDeleteModal]   = useState(null) // { childId, childName }
  const [deleting, setDeleting]         = useState(false)
  const [deleteError, setDeleteError]   = useState("")
  const [hoveredTrashId, setHoveredTrashId] = useState(null)
  const [matrixChars, setMatrixChars]   = useState([])
  const [downloading, setDownloading]   = useState({})

  useEffect(() => {
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => setMaxChildren(data?.maxChildren ?? 0))
      .catch(err => {
        console.error("[KidsPage] failed to load account data:", err)
        setMaxChildren(0)
        setFetchError("Failed to load account data. Please refresh.")
      })
  }, [authFetch])

  async function downloadInstaller(child) {
    setDownloading(d => ({ ...d, [child.childId]: true }))
    try {
      const params = new URLSearchParams({ childId: child.childId, backendUrl: config.backendUrl })
      const res = await authFetch(`/agent/installer?${params}`)
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement("a")
      a.href     = url
      a.download = `hopmap_${child.childName.replace(/\s+/g, "_").toLowerCase()}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error("Installer download failed:", err)
    } finally {
      setDownloading(d => { const n = { ...d }; delete n[child.childId]; return n })
    }
  }

  function startEdit(child) {
    setEditing(e  => ({ ...e,  [child.childId]: child.childName }))
    setSaved(s    => { const n = { ...s }; delete n[child.childId]; return n })
    setFieldErrors(e => { const n = { ...e }; delete n[child.childId]; return n })
  }

  function cancelEdit(childId) {
    setEditing(e => { const n = { ...e }; delete n[childId]; return n })
  }

  async function saveName(childId) {
    const name = (editing[childId] || "").trim()
    if (!name) return
    setSaving(s => ({ ...s, [childId]: true }))
    try {
      const res = await authFetch(`/api/children/${childId}`, {
        method:  "PATCH",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ childName: name }),
      })
      if (!res.ok) throw new Error("Server error")
      await refreshChildren()
      setEditing(e => { const n = { ...e }; delete n[childId]; return n })
      setSaved(s => ({ ...s, [childId]: true }))
      setTimeout(() => setSaved(s => { const n = { ...s }; delete n[childId]; return n }), 2000)
    } catch {
      setFieldErrors(e => ({ ...e, [childId]: "Failed to save. Please try again." }))
    } finally {
      setSaving(s => { const n = { ...s }; delete n[childId]; return n })
    }
  }

  function closeDeleteModal() {
    setDeleteModal(null)
    setDeleteError("")
    setMode("safe")
  }

  async function confirmDelete() {
    if (!deleteModal) return
    setDeleting(true)
    setDeleteError("")
    try {
      const res = await authFetch(`/api/children/${deleteModal.childId}`, { method: "DELETE" })
      if (!res.ok) throw new Error("Failed to remove child. Please try again.")
      await refreshChildren()
      setMode("safe")
      setDeleteModal(null)
    } catch (err) {
      setDeleteError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  useEffect(() => {
    if (!hoveredTrashId) return
    const generate = () =>
      setMatrixChars(Array.from({ length: 800 }, () => (Math.random() > 0.5 ? "1" : "0")))
    generate()
    const id = setInterval(generate, 700)
    return () => clearInterval(id)
  }, [hoveredTrashId])

  useEffect(() => () => setMode("safe"), [setMode])

  const atLimit = maxChildren !== null && children.length >= maxChildren

  return (
    <>
      <AddChildModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={refreshChildren}
      />

      {deleteModal && (
        <DeleteChildModal
          childName={deleteModal.childName}
          onConfirm={confirmDelete}
          onCancel={closeDeleteModal}
          deleting={deleting}
          error={deleteError}
        />
      )}

      <div className="kids-page">
        {(fetchError || childrenError) && (
          <div className="kids-page-error">{fetchError || childrenError}</div>
        )}

        <div className="kids-header">
          <div className="kids-header-text">
<h1 className="kids-page-title">Kids</h1>
            <p className="kids-page-subtitle">
              Manage your children&apos;s profiles and install the monitoring agent on their PCs.
            </p>
          </div>
          <button
            className="kids-add-btn"
            onClick={() => setAddOpen(true)}
            disabled={atLimit}
            title={atLimit ? "Upgrade your plan to add more children" : undefined}
          >
            + Add child
          </button>
        </div>

        {atLimit && maxChildren > 0 && (
          <p className="kids-limit-msg">
            Child limit reached ({maxChildren}). Upgrade your plan to add more.
          </p>
        )}

        {children.length === 0 ? (
          <div className="kids-empty">
            <div className="kids-empty-icon">👧</div>
            <h3>No children yet</h3>
            <p>Add your first child to start monitoring.</p>
            {!atLimit && (
              <button className="kids-empty-btn" onClick={() => setAddOpen(true)}>
                + Add first child
              </button>
            )}
          </div>
        ) : (
          <div className="kids-grid">
            {children.map(child => {
              const isEditing = editing[child.childId] !== undefined
              return (
                <div key={child.childId} className={`kid-card${hoveredTrashId === child.childId ? " kid-card--danger" : ""}`}>
                  {hoveredTrashId === child.childId && (
                    <div className="kid-matrix-overlay" aria-hidden="true">
                      {matrixChars.map((char, i) => <span key={i}>{char}</span>)}
                    </div>
                  )}

                  <div className="kid-card-top">
                    {isEditing ? (
                      <input
                        autoFocus
                        aria-label={`Rename ${child.childName}`}
                        className="kid-name-input"
                        value={editing[child.childId]}
                        onChange={e => setEditing(ed => ({ ...ed, [child.childId]: e.target.value }))}
                        onKeyDown={e => {
                          if (e.key === "Enter")  { e.preventDefault(); saveName(child.childId) }
                          if (e.key === "Escape") cancelEdit(child.childId)
                        }}
                      />
                    ) : (
                      <div className="kid-avatar">{child.childName}</div>
                    )}
                    {!isEditing && (
                      <button
                        className="kid-btn-trash"
                        onClick={() => setDeleteModal({ childId: child.childId, childName: child.childName })}
                        onMouseEnter={() => { setMode("danger"); setHoveredTrashId(child.childId) }}
                        onMouseLeave={() => { setMode("safe"); setHoveredTrashId(null) }}
                        title="Remove child"
                      >
                        <FaTrash size={13} />
                      </button>
                    )}
                  </div>

                  <div className="kid-info">
                    <div className="kid-id">ID: {child.childId}</div>
                    {fieldErrors[child.childId] && (
                      <div className="kid-field-error">{fieldErrors[child.childId]}</div>
                    )}
                  </div>

                  <div className="kid-actions">
                    {isEditing ? (
                      <>
                        <button
                          className="kid-btn-save"
                          onClick={() => saveName(child.childId)}
                          disabled={saving[child.childId]}
                        >
                          {saving[child.childId] ? "Saving…" : "Save"}
                        </button>
                        <button
                          className="kid-btn-cancel"
                          onClick={() => cancelEdit(child.childId)}
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          className={`kid-btn-rename${saved[child.childId] ? " kid-btn-saved" : ""}`}
                          onClick={() => startEdit(child)}
                        >
                          {saved[child.childId] ? "✓ Saved" : "✎ Rename"}
                        </button>
                        <button
                          className="kid-btn-download"
                          onClick={() => downloadInstaller(child)}
                          disabled={downloading[child.childId]}
                          title="Re-download installer"
                        >
                          <FaDownload size={13} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
