import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [accessToken, setAccessToken] = useState(null)
  const [user, setUser]               = useState(null)
  const [loading, setLoading]         = useState(true)

  // Ref mirrors the current token so authFetch always reads the latest value
  // without forming stale closures. Updated synchronously alongside state.
  const tokenRef = useRef(null)

  function setToken(token) {
    tokenRef.current = token
    setAccessToken(token)
  }

  // Restore session on mount via httpOnly refresh cookie
  useEffect(() => {
    fetch("/auth/refresh", { method: "POST", credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.accessToken) setToken(data.accessToken)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/auth/refresh", { method: "POST", credentials: "include" })
      if (!res.ok) { setToken(null); setUser(null); return null }
      const data = await res.json()
      setToken(data.accessToken)
      return data.accessToken
    } catch {
      setToken(null); setUser(null); return null
    }
  }, [])

  const login = useCallback(async (email, password) => {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      credentials: "include",
      body: new URLSearchParams({ username: email, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || "Login failed")
    }
    const data = await res.json()
    setToken(data.accessToken)
    setUser(data.user ?? null)
    return data
  }, [])

  const register = useCallback(async (email, password, displayName) => {
    const res = await fetch("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password, displayName }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || "Registration failed")
    }
    const data = await res.json()
    setToken(data.accessToken)
    setUser(data.user ?? null)
    return data
  }, [])

  const logout = useCallback(async () => {
    await fetch("/auth/logout", { method: "POST", credentials: "include" }).catch(() => {})
    setToken(null)
    setUser(null)
  }, [])

  // Authenticated fetch — injects Bearer token and retries once after a 401
  // by attempting a silent token refresh.
  const authFetch = useCallback(async (url, options = {}) => {
    const makeRequest = (token) => fetch(url, {
      ...options,
      credentials: "include",
      headers: {
        ...(options.headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })

    let res = await makeRequest(tokenRef.current)
    if (res.status === 401) {
      const newToken = await refresh()
      if (!newToken) return res
      res = await makeRequest(newToken)
    }
    return res
  }, [refresh])

  return (
    <AuthContext.Provider value={{ accessToken, user, loading, login, register, logout, authFetch }}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Consume auth context. Throws a clear error when used outside AuthProvider
 * rather than silently returning null.
 */
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (ctx === null) {
    throw new Error("useAuth must be used inside <AuthProvider>")
  }
  return ctx
}
