// ─── Color tokens ─────────────────────────────────────────────────────────────
export const colors = {
  // Surfaces
  bg:         "#0d0f14",
  surface:    "#111318",
  border:     "#1e2130",
  rowDivider: "#1a1d28",

  // Text
  text:   "#e8eaf0",
  muted:  "#4b5268",
  subtle: "#3a3f58",

  // Brand
  indigo:      "#6366f1",
  indigoLight: "#818cf8",

  // Semantic
  danger:  "#ff4757",
  success: "#2ed573",
  warning: "#ffa502",
}

// ─── Font tokens ──────────────────────────────────────────────────────────────
export const fonts = {
  sans: "'IBM Plex Sans',sans-serif",
  mono: "'IBM Plex Mono',monospace",
}

// ─── Shared style objects ─────────────────────────────────────────────────────
export const pageRoot = {
  width: "100%", height: "100vh",
  background: colors.bg, color: colors.text,
  fontFamily: fonts.sans,
  display: "flex", flexDirection: "column", overflow: "hidden",
}

export const timelineContainer = {
  flex: 1,
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: 10,
  overflowY: "auto",
}

export const timelineEmpty = {
  display: "flex", alignItems: "center", justifyContent: "center",
  height: "100%",
  color: colors.subtle,
  fontFamily: fonts.mono,
  fontSize: 12,
}

export const liveBadge = {
  fontSize: 9, fontWeight: 700,
  color: colors.danger,
  background: "rgba(255,71,87,0.13)",
  border: "1px solid rgba(255,71,87,0.28)",
  borderRadius: 4, padding: "2px 6px",
  fontFamily: fonts.mono,
}

export const dateInput = {
  background: colors.surface,
  border: `1px solid ${colors.border}`,
  borderRadius: 7, padding: "5px 10px",
  color: colors.text,
  fontSize: 11, fontFamily: fonts.mono,
  outline: "none", colorScheme: "dark",
}
