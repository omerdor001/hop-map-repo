import { useState, useEffect } from "react"
import { useAuth } from "../context/AuthContext"

const DARK   = "#0d0d0f"
const CARD   = "#16161a"
const BORDER = "#1e1e24"
const INDIGO = "#6366f1"
const MUTED  = "#6b7280"

const PLANS = [
  { label: "Free",       maxChildren: 0, description: "No children — just browsing", color: "#4b5563" },
  { label: "Starter",    maxChildren: 1, description: "1 child",                      color: "#6366f1" },
  { label: "Family",     maxChildren: 3, description: "Up to 3 children",             color: "#8b5cf6" },
  { label: "Unlimited",  maxChildren: 10, description: "Up to 10 children",           color: "#ec4899" },
]

export default function Plan() {
  const { authFetch } = useAuth()
  const [current, setCurrent] = useState(null)   // current maxChildren from server
  const [selected, setSelected] = useState(null) // what user picked in UI
  const [saving, setSaving] = useState(false)
  const [saved, setSaved]   = useState(false)
  const [error, setError]   = useState("")

  useEffect(() => {
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setCurrent(data.maxChildren ?? 0)
          setSelected(data.maxChildren ?? 0)
        }
      })
      .catch(() => {})
  }, [authFetch])

  async function handleSave() {
    if (selected === current) return
    setSaving(true)
    setError("")
    setSaved(false)
    try {
      const res = await authFetch("/api/me/plan", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ maxChildren: selected }),
      })
      if (!res.ok) throw new Error("Failed to update plan")
      setCurrent(selected)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const activePlan = PLANS.find(p => p.maxChildren === current)

  return (
    <div style={{ padding: "40px 48px", maxWidth: 700, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: 36 }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: INDIGO, marginBottom: 6 }}>
          ACCOUNT
        </div>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#fff" }}>Plan</h1>
        <p style={{ margin: "8px 0 0", color: MUTED, fontSize: 14 }}>
          Simulate choosing a plan to unlock child slots.
        </p>
      </div>

      {/* Current status */}
      {current !== null && (
        <div style={{
          background: CARD, border: `1px solid ${BORDER}`, borderRadius: 12,
          padding: "16px 20px", marginBottom: 28, display: "flex", alignItems: "center", gap: 12,
        }}>
          <span style={{ fontSize: 20 }}>📋</span>
          <div>
            <div style={{ fontSize: 13, color: MUTED }}>Current plan</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#e5e7eb" }}>
              {activePlan?.label ?? "Custom"}{" "}
              <span style={{ fontWeight: 400, color: MUTED, fontSize: 13 }}>
                — {current === 0 ? "no children allowed" : `up to ${current} ${current === 1 ? "child" : "children"}`}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Plan cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 28 }}>
        {PLANS.map(plan => {
          const isSelected = selected === plan.maxChildren
          return (
            <button
              key={plan.label}
              onClick={() => setSelected(plan.maxChildren)}
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: isSelected ? `${plan.color}18` : CARD,
                border: `2px solid ${isSelected ? plan.color : BORDER}`,
                borderRadius: 12, padding: "18px 22px", cursor: "pointer", textAlign: "left",
                transition: "border-color 0.15s, background 0.15s",
              }}
            >
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: isSelected ? "#fff" : "#e5e7eb" }}>
                  {plan.label}
                </div>
                <div style={{ fontSize: 13, color: MUTED, marginTop: 2 }}>{plan.description}</div>
              </div>
              {/* Simulated price badge */}
              <div style={{
                fontSize: 13, fontWeight: 700,
                color: isSelected ? plan.color : MUTED,
                background: isSelected ? `${plan.color}22` : "transparent",
                border: `1px solid ${isSelected ? plan.color : BORDER}`,
                borderRadius: 8, padding: "4px 12px",
              }}>
                {plan.maxChildren === 0 ? "Free" : plan.maxChildren === 1 ? "$4/mo" : plan.maxChildren === 3 ? "$9/mo" : "$15/mo"}
              </div>
            </button>
          )
        })}
      </div>

      {/* Save */}
      {error && (
        <div style={{
          background: "#2d1515", border: "1px solid #7f1d1d", borderRadius: 8,
          color: "#fca5a5", fontSize: 13, padding: "10px 14px", marginBottom: 16,
        }}>
          {error}
        </div>
      )}
      <button
        onClick={handleSave}
        disabled={saving || selected === current || current === null}
        style={{
          background: (saving || selected === current || current === null) ? "#2a2a35" : INDIGO,
          color: (saving || selected === current || current === null) ? MUTED : "#fff",
          border: "none", borderRadius: 8, fontSize: 14, fontWeight: 700,
          padding: "11px 28px", cursor: (saving || selected === current || current === null) ? "not-allowed" : "pointer",
          transition: "background 0.15s",
        }}
      >
        {saving ? "Saving…" : saved ? "✓ Plan updated" : "Apply plan"}
      </button>
      <p style={{ fontSize: 12, color: "#374151", marginTop: 12 }}>
        This is a simulation — no real payment is processed.
      </p>
    </div>
  )
}
