import { useState, useEffect } from "react"
import { getInitials } from "../utils/eventHelpers"
import { useAuth } from "../context/AuthContext"
import { colors, fonts } from "../utils/theme"
import AddChildModal from "./AddChildModal"

const card = {
  background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 12,
  padding: "20px 24px", display: "flex", alignItems: "center", gap: 16,
}

export default function Kids({ setChildList }) {
  const { authFetch } = useAuth()
  const [children, setChildren]       = useState([])
  const [maxChildren, setMaxChildren] = useState(null)
  const [editing, setEditing]         = useState({})
  const [saving, setSaving]           = useState({})
  const [saved, setSaved]             = useState({})
  const [error, setError]             = useState({})
  const [addOpen, setAddOpen]         = useState(false)

  useEffect(() => {
    authFetch("/api/children")
      .then(r => r.ok ? r.json() : null)
      .then(data => setChildren(data?.children || []))
      .catch(() => {})
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : null)
      .then(data => setMaxChildren(data?.maxChildren ?? 0))
      .catch(() => {})
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
      setChildren(c => c.map(ch => ch.childId === childId ? { ...ch, childName: name } : ch))
      if (setChildList) setChildList(c => c.map(ch => ch.childId === childId ? { ...ch, childName: name } : ch))
      setEditing(e => { const n = { ...e }; delete n[childId]; return n })
      setSaved(s => ({ ...s, [childId]: true }))
      setTimeout(() => setSaved(s => { const n = { ...s }; delete n[childId]; return n }), 2000)
    } catch {
      setError(e => ({ ...e, [childId]: "Failed to save" }))
    } finally {
      setSaving(s => { const n = { ...s }; delete n[childId]; return n })
    }
  }

  function handleChildCreated(newChild) {
    const child = { childId: newChild.childId, childName: newChild.childName }
    setChildren(c => [child, ...c])
    if (setChildList) setChildList(c => [child, ...c])
  }

  const atLimit = maxChildren !== null && children.length >= maxChildren
  const canAdd  = !atLimit

  return (
    <>
      <AddChildModal open={addOpen} onClose={() => setAddOpen(false)} onCreated={handleChildCreated} />

      <div style={{ padding: "40px 48px", maxWidth: 700, margin: "0 auto", fontFamily: fonts.sans }}>
        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: colors.indigo, marginBottom: 6, fontFamily: fonts.mono }}>
            ACCOUNT
          </div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: colors.text }}>Kids Management</h1>
          <p style={{ margin: "8px 0 0", color: colors.muted, fontSize: 14 }}>
            Manage monitored children and install the agent on their PCs.
          </p>
          <button
            onClick={() => canAdd && setAddOpen(true)}
            disabled={!canAdd}
            title={atLimit ? "Upgrade your plan to add more children" : undefined}
            style={{
              background: canAdd ? colors.indigo : colors.surface,
              color: canAdd ? "#fff" : colors.muted,
              border: "none", borderRadius: 8, fontSize: 13, fontWeight: 700,
              padding: "9px 18px", cursor: canAdd ? "pointer" : "not-allowed", marginTop: 20,
            }}
          >
            + Add child
          </button>
          {atLimit && maxChildren === 0 && (
            <div style={{ fontSize: 13, color: colors.warning, marginTop: 10 }}>
              You're on the Free plan.{" "}
              <a href="/plan" style={{ color: colors.indigo }}>Upgrade</a>{" "}to add children.
            </div>
          )}
          {atLimit && maxChildren > 0 && (
            <div style={{ fontSize: 13, color: colors.warning, marginTop: 10 }}>
              Child limit reached ({maxChildren}).{" "}
              <a href="/plan" style={{ color: colors.indigo }}>Upgrade your plan</a>{" "}to add more.
            </div>
          )}
        </div>

        {/* List */}
        {children.length === 0 ? (
          <div style={{ color: colors.muted, fontSize: 14, padding: "32px 0" }}>
            No children yet.{" "}
            {canAdd ? (
              <span
                style={{ color: colors.indigo, cursor: "pointer", textDecoration: "underline" }}
                onClick={() => setAddOpen(true)}
              >
                Add your first child
              </span>
            ) : (
              <a href="/plan" style={{ color: colors.indigo }}>Upgrade your plan</a>
            )}{" "}
            to get started.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {children.map(child => {
              const isEditing = editing[child.childId] !== undefined
              return (
                <div key={child.childId} style={card}>
                  {/* Avatar */}
                  <div style={{
                    width: 40, height: 40, borderRadius: "50%", flexShrink: 0,
                    background: "linear-gradient(135deg, #6366f1, #818cf8)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 15, fontWeight: 700, color: "#fff",
                  }}>
                    {getInitials(child.childName)}
                  </div>

                  {/* Name / input */}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: colors.muted, marginBottom: 2, fontFamily: fonts.mono }}>
                      ID: {child.childId}
                    </div>
                    {isEditing ? (
                      <input
                        autoFocus
                        value={editing[child.childId]}
                        onChange={e => setEditing(ed => ({ ...ed, [child.childId]: e.target.value }))}
                        onKeyDown={e => {
                          if (e.key === "Enter") saveName(child.childId)
                          if (e.key === "Escape") setEditing(ed => { const n = { ...ed }; delete n[child.childId]; return n })
                        }}
                        style={{
                          background: colors.bg, border: `1px solid ${colors.indigo}`, borderRadius: 6,
                          color: colors.text, fontSize: 15, fontWeight: 600, padding: "4px 10px",
                          outline: "none", width: "100%", maxWidth: 260, fontFamily: fonts.sans,
                        }}
                      />
                    ) : (
                      <div style={{ fontSize: 15, fontWeight: 600, color: colors.text }}>{child.childName}</div>
                    )}
                    {error[child.childId] && (
                      <div style={{ fontSize: 12, color: colors.danger, marginTop: 3 }}>{error[child.childId]}</div>
                    )}
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                    {isEditing ? (
                      <>
                        <button onClick={() => saveName(child.childId)} disabled={saving[child.childId]} style={{
                          background: colors.indigo, color: "#fff", border: "none", borderRadius: 7,
                          padding: "6px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer",
                        }}>
                          {saving[child.childId] ? "Saving…" : "Save"}
                        </button>
                        <button onClick={() => setEditing(ed => { const n = { ...ed }; delete n[child.childId]; return n })} style={{
                          background: "transparent", color: colors.muted, border: `1px solid ${colors.border}`,
                          borderRadius: 7, padding: "6px 12px", fontSize: 13, cursor: "pointer",
                        }}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button onClick={() => startEdit(child)} style={{
                        background: "transparent", color: colors.indigoLight, border: `1px solid ${colors.border}`,
                        borderRadius: 7, padding: "6px 14px", fontSize: 13, fontWeight: 500, cursor: "pointer",
                      }}>
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
