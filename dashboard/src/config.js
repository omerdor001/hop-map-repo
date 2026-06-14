const config = {
  backendUrl:        import.meta.env.VITE_BACKEND_URL || (typeof window !== "undefined" ? window.location.origin : ""),
  eventHistoryLimit: 500,
  liveThresholdMs:   60_000,
}

export default config
