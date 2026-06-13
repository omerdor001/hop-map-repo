import { useState } from "react"
import { ThemeContext } from "./themeContext"

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState("safe")

  return (
    <ThemeContext.Provider value={{ mode, setMode }}>
      {children}
    </ThemeContext.Provider>
  )
}
