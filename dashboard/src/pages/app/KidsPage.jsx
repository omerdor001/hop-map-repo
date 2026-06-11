import { useState, useEffect } from "react"
import { getInitials } from "../../utils/eventHelpers"
import { useAuth } from "../../context/AuthContext"
import { useChildren } from "../../context/ChildrenContext"
import AddChildModal from "../../components/AddChildModal"
import "./KidsPage.css"

export default function KidsPage() {
  const { authFetch }                                     = useAuth()
  const { childList: children, refreshChildren, childrenError } = useChildren()
  const [maxChildren, setMaxChildren] = useState(null)
  const [fetchError, setFetchError]   = useState(null)
  const [editing, setEditing]         = useState({})
  const [saving, setSaving]           = useState({})
  const [saved, setSaved]             = useState({})
  const [fieldErrors, setFieldErrors] = useState({})
  const [addOpen, setAddOpen]         = useState(false)

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

  const atLimit = maxChildren !== null && children.length >= maxChildren

  return (
    <>
      <AddChildModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={refreshChildren}
      />

      <div className="kids-page">
        {(fetchError || childrenError) && (
          <div className="kids-page-error">{fetchError || childrenError}</div>
        )}

        <div className="kids-header">
          <div className="kids-header-text">
            <p className="kids-page-label">Account</p>
            <h1 className="kids-page-title">Kids</h1>
            <p className="kids-page-subtitle">
              Manage your children&apos;s profiles and install the monitoring agent on their PCs.
            </p>
          </div>
          <button
            className="kids-add-btn"
            onClick={() => !atLimit && setAddOpen(true)}
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
          <div className="kids-list">
            {children.map(child => {
              const isEditing = editing[child.childId] !== undefined
              return (
                <div key={child.childId} className="kid-card">
                  <div className="kid-avatar">{getInitials(child.childName)}</div>

                  <div className="kid-info">
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
                      <div className="kid-name">{child.childName}</div>
                    )}
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
                      <button
                        className={`kid-btn-rename${saved[child.childId] ? " kid-btn-saved" : ""}`}
                        onClick={() => startEdit(child)}
                      >
                        {saved[child.childId] ? "✓ Saved" : "Rename"}
                      </button>
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
