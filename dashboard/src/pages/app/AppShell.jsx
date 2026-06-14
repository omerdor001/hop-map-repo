import { Outlet } from "react-router-dom"
import { ChildrenProvider } from "../../context/ChildrenContext"
import { useTheme } from "../../context/ThemeContext"
import AppSidebar from "../../components/app/AppSidebar"
import "./AppShell.css"

export default function AppShell() {
  const { mode } = useTheme()

  return (
    <ChildrenProvider>
      <div className={`app-shell pg ${mode}`}>
        <AppSidebar />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </ChildrenProvider>
  )
}
