import { createContext, useContext, useState, useEffect, useCallback } from "react"
import { useAuth } from "./AuthContext"

const ChildrenContext = createContext(null)

export function ChildrenProvider({ children }) {
  const { authFetch, loading: authLoading } = useAuth()
  const [childList, setChildList]       = useState([])
  const [activeId, setActiveId]         = useState(null)
  const [childrenError, setChildrenError] = useState(null)

  const refreshChildren = useCallback(() => {
    return authFetch("/api/children")
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(data => {
        const list = data?.children || []
        setChildList(list)
        setChildrenError(null)
        // Auto-select first child on initial load only; preserve selection on refresh
        setActiveId(id => id ?? (list.length > 0 ? list[0].childId : null))
      })
      .catch(err => {
        console.error("[ChildrenContext] failed to load children:", err)
        setChildrenError("Failed to load children. Please refresh.")
      })
  }, [authFetch])

  useEffect(() => {
    if (authLoading) return
    refreshChildren()
  }, [authLoading, refreshChildren])

  return (
    <ChildrenContext.Provider value={{ childList, activeId, setActiveId, refreshChildren, childrenError }}>
      {children}
    </ChildrenContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChildren() {
  const ctx = useContext(ChildrenContext)
  if (ctx === null) {
    throw new Error("useChildren must be used inside <ChildrenProvider>")
  }
  return ctx
}
