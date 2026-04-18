import { useEffect, useRef } from "react"
import { createPortal } from "react-dom"

/**
 * Generic modal portal. Renders `children` inside a full-screen backdrop
 * that is mounted on `document.body` — avoids z-index / overflow clipping bugs.
 *
 * Props:
 *   open     {boolean}  — show/hide
 *   onClose  {function} — called when user clicks backdrop or presses Escape
 *   children {node}
 */
export default function Modal({ open, onClose, children }) {
  const panelRef = useRef(null)

  // Close on Escape key
  useEffect(() => {
    if (!open) return
    function handleKey(e) {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [open, onClose])

  // Prevent body scroll while open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = prev }
  }, [open])

  // Move focus into the panel on open; restore it to the trigger on close
  useEffect(() => {
    if (!open) return
    const trigger = document.activeElement
    // Focus the first focusable element inside the panel, or the panel itself
    const focusable = panelRef.current?.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    ;(focusable ?? panelRef.current)?.focus()
    return () => trigger?.focus()
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      role="presentation"
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.65)",
        display: "flex", alignItems: "center", justifyContent: "center",
        backdropFilter: "blur(2px)",
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        onClick={e => e.stopPropagation()}
        // Catch Tab to keep focus inside the modal
        onKeyDown={e => {
          if (e.key !== "Tab") return
          const focusable = panelRef.current.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'
          )
          if (!focusable.length) return
          const first = focusable[0]
          const last  = focusable[focusable.length - 1]
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault(); last.focus()
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault(); first.focus()
          }
        }}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
