import { useState, useEffect } from "react"
import { getInitials } from "../utils/eventHelpers"

const card = {
  background: "#16161a", border: "1px solid #1e1e24", borderRadius: 12,
  padding: "20px 24px", display: "flex", alignItems: "center", gap: 16,
}

export default function Kids({ setChildList }) {
  const [children, setChildren]   = useState([])
  const [editing, setEditing]     = useState({})   // { childId: draftName }
  const [saving, setSaving]       = useState({})   // { childId: true }
  const [saved, setSaved]         = useState({})   // { childId: true }
  const [error, setError]         = useState({})   // { childId: msg }

  useEffect(() => {
    fetch("/api/children")
      .then(r => r.json())
      .then(data => setChildren(data.children || []))
      .catch(() => {})
  }, [])

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
      const res = await fetch(`/api/children/${childId}`, {
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

  return (
    <div style={{ padding: "40px 48px", maxWidth: 700 }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: "#6366f1", marginBottom: 6 }}>
          ACCOUNT
        </div>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#fff" }}>Kids Management</h1>
        <p style={{ margin: "8px 0 0", color: "#6b7280", fontSize: 14 }}>
          Rename monitored children as they appear on the dashboard.
        </p>
      </div>

      {/* List */}
      {children.length === 0 ? (
        <div style={{ color: "#4b5563", fontSize: 14, padding: "32px 0" }}>
          No children registered yet. Start the agent to register a child automatically.
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
                  <div style={{ fontSize: 11, color: "#4b5563", marginBottom: 2 }}>ID: {child.childId}</div>
                  {isEditing ? (
                    <input
                      autoFocus
                      value={editing[child.childId]}
                      onChange={e => setEditing(ed => ({ ...ed, [child.childId]: e.target.value }))}
                      onKeyDown={e => { if (e.key === "Enter") saveName(child.childId); if (e.key === "Escape") setEditing(ed => { const n = { ...ed }; delete n[child.childId]; return n }) }}
                      style={{
                        background: "#0d0d0f", border: "1px solid #6366f1", borderRadius: 6,
                        color: "#fff", fontSize: 15, fontWeight: 600, padding: "4px 10px",
                        outline: "none", width: "100%", maxWidth: 260,
                      }}
                    />
                  ) : (
                    <div style={{ fontSize: 15, fontWeight: 600, color: "#e5e7eb" }}>{child.childName}</div>
                  )}
                  {error[child.childId] && (
                    <div style={{ fontSize: 12, color: "#ef4444", marginTop: 3 }}>{error[child.childId]}</div>
                  )}
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                  {isEditing ? (
                    <>
                      <button onClick={() => saveName(child.childId)} disabled={saving[child.childId]} style={{
                        background: "#6366f1", color: "#fff", border: "none", borderRadius: 7,
                        padding: "6px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer",
                      }}>
                        {saving[child.childId] ? "Saving…" : "Save"}
                      </button>
                      <button onClick={() => setEditing(ed => { const n = { ...ed }; delete n[child.childId]; return n })} style={{
                        background: "transparent", color: "#6b7280", border: "1px solid #2a2a35",
                        borderRadius: 7, padding: "6px 12px", fontSize: 13, cursor: "pointer",
                      }}>
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button onClick={() => startEdit(child)} style={{
                      background: "transparent", color: "#818cf8", border: "1px solid #2a2a35",
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
  )
}
