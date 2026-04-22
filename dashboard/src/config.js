const config = {
  backendUrl:        import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000",
  eventHistoryLimit: 500,
  liveThresholdMs:   60_000,
}

export default config
