import { useState, useEffect } from "react"
import { useAuth } from "../context/AuthContext"
import styles from "./Plan.module.css"

const PLANS = [
  { label: "Free",      maxChildren: 0,  description: "No children — just browsing", color: "var(--color-plan-free)"      },
  { label: "Starter",   maxChildren: 1,  description: "1 child",                     color: "var(--color-plan-starter)"   },
  { label: "Family",    maxChildren: 3,  description: "Up to 3 children",            color: "var(--color-plan-family)"    },
  { label: "Unlimited", maxChildren: 10, description: "Up to 10 children",           color: "var(--color-plan-unlimited)" },
]

function planPrice(maxChildren) {
  if (maxChildren === 0) return "Free"
  if (maxChildren === 1) return "$4/mo"
  if (maxChildren === 3) return "$9/mo"
  return "$15/mo"
}

export default function Plan() {
  const { authFetch } = useAuth()
  const [current, setCurrent]   = useState(null)
  const [selected, setSelected] = useState(null)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [error, setError]       = useState("")

  useEffect(() => {
    authFetch("/api/me")
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        if (data) {
          setCurrent(data.maxChildren ?? 0)
          setSelected(data.maxChildren ?? 0)
        }
      })
      .catch(err => {
        console.error("[Plan] failed to load plan data:", err)
        setError("Failed to load plan. Please refresh.")
      })
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

  const activePlan   = PLANS.find(p => p.maxChildren === current)
  const saveDisabled = saving || selected === current || current === null

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.sectionLabel}>ACCOUNT</div>
        <h1 className={styles.heading}>Plan</h1>
        <p className={styles.subheading}>Simulate choosing a plan to unlock child slots.</p>
      </div>

      {current !== null && (
        <div className={styles.currentPlan}>
          <span className={styles.currentPlanIcon}>📋</span>
          <div>
            <div className={styles.currentPlanLabel}>Current plan</div>
            <div className={styles.currentPlanName}>
              {activePlan?.label ?? "Custom"}{" "}
              <span className={styles.currentPlanDetail}>
                — {current === 0 ? "no children allowed" : `up to ${current} ${current === 1 ? "child" : "children"}`}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className={styles.planList}>
        {PLANS.map(plan => {
          const isSelected = selected === plan.maxChildren
          // Per-plan accent colour is data-driven — border and background stay inline when selected
          return (
            <button
              key={plan.label}
              onClick={() => setSelected(plan.maxChildren)}
              className={styles.planCard}
              style={isSelected ? {
                borderColor: plan.color,
                background: `${plan.color}18`,
              } : undefined}
            >
              <div>
                <div className={styles.planCardName}>{plan.label}</div>
                <div className={styles.planCardDesc}>{plan.description}</div>
              </div>
              <div
                className={styles.planCardPrice}
                style={isSelected ? {
                  color: plan.color,
                  borderColor: plan.color,
                  background: `${plan.color}22`,
                } : undefined}
              >
                {planPrice(plan.maxChildren)}
              </div>
            </button>
          )
        })}
      </div>

      {error && <div className={styles.errorBox}>{error}</div>}

      <button onClick={handleSave} disabled={saveDisabled} className={styles.saveBtn}>
        {saving ? "Saving…" : saved ? "✓ Plan updated" : "Apply plan"}
      </button>
      <p className={styles.saveNote}>This is a simulation — no real payment is processed.</p>
    </div>
  )
}
