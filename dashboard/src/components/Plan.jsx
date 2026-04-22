import { useState, useEffect } from "react"
import { useAuth } from "../context/AuthContext"
import { colors, fonts } from "../utils/theme"

const PLANS = [
  { label: "Free",      maxChildren: 0,  description: "No children — just browsing", color: colors.muted   },
  { label: "Starter",   maxChildren: 1,  description: "1 child",                     color: colors.indigo  },
  { label: "Family",    maxChildren: 3,  description: "Up to 3 children",            color: "#8b5cf6"      },
  { label: "Unlimited", maxChildren: 10, description: "Up to 10 children",           color: "#ec4899"      },
]

export default function Plan() {
  const { authFetch } = useAuth()
  const [current, setCurrent]   = useState(null)
  const [selected, setSelected] = useState(null)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [error, setError]       = useState("")

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

  const activePlan    = PLANS.find(p => p.maxChildren === current)
  const saveDisabled  = saving || selected === current || current === null

  return (
    <div style={{ padding: "40px 48px", maxWidth: 700, margin: "0 auto", fontFamily: fonts.sans }}>
      {/* Header */}
      <div style={{ marginBottom: 36 }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", color: colors.indigo, marginBottom: 6, fontFamily: fonts.mono }}>
          ACCOUNT
        </div>
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: colors.text }}>Plan</h1>
        <p style={{ margin: "8px 0 0", color: colors.muted, fontSize: 14 }}>
          Simulate choosing a plan to unlock child slots.
        </p>
      </div>

      {/* Current status */}
      {current !== null && (
        <div style={{
          background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 12,
          padding: "16px 20px", marginBottom: 28, display: "flex", alignItems: "center", gap: 12,
        }}>
          <span style={{ fontSize: 20 }}>📋</span>
          <div>
            <div style={{ fontSize: 13, color: colors.muted }}>Current plan</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: colors.text }}>
              {activePlan?.label ?? "Custom"}{" "}
              <span style={{ fontWeight: 400, color: colors.muted, fontSize: 13 }}>
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
                background: isSelected ? `${plan.color}18` : colors.surface,
                border: `2px solid ${isSelected ? plan.color : colors.border}`,
                borderRadius: 12, padding: "18px 22px", cursor: "pointer", textAlign: "left",
                transition: "border-color 0.15s, background 0.15s",
                fontFamily: fonts.sans,
              }}
            >
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: isSelected ? colors.text : colors.text }}>
                  {plan.label}
                </div>
                <div style={{ fontSize: 13, color: colors.muted, marginTop: 2 }}>{plan.description}</div>
              </div>
              <div style={{
                fontSize: 13, fontWeight: 700,
                color: isSelected ? plan.color : colors.muted,
                background: isSelected ? `${plan.color}22` : "transparent",
                border: `1px solid ${isSelected ? plan.color : colors.border}`,
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
          background: "rgba(255,71,87,0.08)", border: `1px solid rgba(255,71,87,0.3)`, borderRadius: 8,
          color: colors.danger, fontSize: 13, padding: "10px 14px", marginBottom: 16,
        }}>
          {error}
        </div>
      )}
      <button
        onClick={handleSave}
        disabled={saveDisabled}
        style={{
          background: saveDisabled ? colors.surface : colors.indigo,
          color: saveDisabled ? colors.muted : "#fff",
          border: "none", borderRadius: 8, fontSize: 14, fontWeight: 700,
          padding: "11px 28px", cursor: saveDisabled ? "not-allowed" : "pointer",
          transition: "background 0.15s",
        }}
      >
        {saving ? "Saving…" : saved ? "✓ Plan updated" : "Apply plan"}
      </button>
      <p style={{ fontSize: 12, color: colors.muted, marginTop: 12 }}>
        This is a simulation — no real payment is processed.
      </p>
    </div>
  )
}
