import { useState, useEffect } from "react"
import { getInitials } from "../utils/eventHelpers"
import { useAuth } from "../context/AuthContext"
import { useChildren } from "../context/ChildrenContext"
import AddChildModal from "./AddChildModal"
import styles from "./Kids.module.css"

export default function Kids() {
  const { authFetch } = useAuth()
  const { childList: children, refreshChildren, childrenError } = useChildren()
  const [maxChildren, setMaxChildren] = useState(null)
  const [fetchError, setFetchError]   = useState(null)
  const [editing, setEditing]         = useState({})
  const [saving, setSaving]           = useState({})
  const [saved, setSaved]             = useState({})
  const [error, setError]             = useState({})
  const [addOpen, setAddOpen]         = useState(false)

  useEffect(() => {
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => setMaxChildren(data?.maxChildren ?? 0))
      .catch(err => {
        console.error("[Kids] failed to load account data:", err)
        setMaxChildren(0) // fail-safe: disable Add until data loads
        setFetchError("Failed to load account data. Please refresh.")
      })
  }, [authFetch])

  function startEdit(child) {
    setEditing(e => ({ ...e, [child.childId]: child.childName }))
    setSaved(s => { const n = { ...s }; delete n[child.childId]; return n })
    setError(e => { const n = { ...e }; delete n[child.childId]; return n })
  }

  async function saveName(childId) {
    const name = (editing[childId] || "").trim()
    if (!name) return
    setSaving(s => ({ ...s, [childId]: true }))
    try {
      const res = await authFetch(`/api/children/${childId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ childName: name }),
      })
      if (!res.ok) throw new Error("Server error")
      await refreshChildren()
      setEditing(e => { const n = { ...e }; delete n[childId]; return n })
      setSaved(s => ({ ...s, [childId]: true }))
      setTimeout(() => setSaved(s => { const n = { ...s }; delete n[childId]; return n }), 2000)
    } catch {
      setError(e => ({ ...e, [childId]: "Failed to save" }))
    } finally {
      setSaving(s => { const n = { ...s }; delete n[childId]; return n })
    }
  }

  const atLimit = maxChildren !== null && children.length >= maxChildren
  const canAdd  = !atLimit

  return (
    <>
      <AddChildModal open={addOpen} onClose={() => setAddOpen(false)} onCreated={refreshChildren} />

      <div className={styles.page}>
        {(fetchError || childrenError) && (
          <div className={styles.pageError}>{fetchError || childrenError}</div>
        )}
        <div className={styles.header}>
          <div className={styles.sectionLabel}>ACCOUNT</div>
          <h1 className={styles.heading}>Kids Management</h1>
          <p className={styles.subheading}>
            Manage monitored children and install the agent on their PCs.
          </p>
          <button
            onClick={() => canAdd && setAddOpen(true)}
            disabled={!canAdd}
            title={atLimit ? "Upgrade your plan to add more children" : undefined}
            className={styles.addBtn}
          >
            + Add child
          </button>
          {atLimit && maxChildren === 0 && (
            <div className={styles.limitMsg}>
              You're on the Free plan.{" "}
              <a href="/plan" className={styles.limitLink}>Upgrade</a>{" "}to add children.
            </div>
          )}
          {atLimit && maxChildren > 0 && (
            <div className={styles.limitMsg}>
              Child limit reached ({maxChildren}).{" "}
              <a href="/plan" className={styles.limitLink}>Upgrade your plan</a>{" "}to add more.
            </div>
          )}
        </div>

        {children.length === 0 ? (
          <div className={styles.emptyMsg}>
            No children yet.{" "}
            {canAdd ? (
              <span className={styles.emptyLink} onClick={() => setAddOpen(true)}>
                Add your first child
              </span>
            ) : (
              <a href="/plan" className={styles.limitLink}>Upgrade your plan</a>
            )}{" "}
            to get started.
          </div>
        ) : (
          <div className={styles.childList}>
            {children.map(child => {
              const isEditing = editing[child.childId] !== undefined
              return (
                <div key={child.childId} className={styles.card}>
                  <div className={styles.avatar}>{getInitials(child.childName)}</div>

                  <div className={styles.cardBody}>
                    <div className={styles.childId}>ID: {child.childId}</div>
                    {isEditing ? (
                      <input
                        autoFocus
                        className={styles.nameInput}
                        value={editing[child.childId]}
                        onChange={e => setEditing(ed => ({ ...ed, [child.childId]: e.target.value }))}
                        onKeyDown={e => {
                          if (e.key === "Enter") saveName(child.childId)
                          if (e.key === "Escape") setEditing(ed => { const n = { ...ed }; delete n[child.childId]; return n })
                        }}
                      />
                    ) : (
                      <div className={styles.childName}>{child.childName}</div>
                    )}
                    {error[child.childId] && (
                      <div className={styles.fieldError}>{error[child.childId]}</div>
                    )}
                  </div>

                  <div className={styles.cardActions}>
                    {isEditing ? (
                      <>
                        <button
                          onClick={() => saveName(child.childId)}
                          disabled={saving[child.childId]}
                          className={styles.btnSave}
                        >
                          {saving[child.childId] ? "Saving…" : "Save"}
                        </button>
                        <button
                          onClick={() => setEditing(ed => { const n = { ...ed }; delete n[child.childId]; return n })}
                          className={styles.btnCancel}
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button onClick={() => startEdit(child)} className={styles.btnRename}>
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
