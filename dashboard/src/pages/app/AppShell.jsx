import { Outlet } from "react-router-dom"
import { ChildrenProvider } from "../../context/ChildrenContext"
import AppSidebar from "../../components/app/AppSidebar"
import "./AppShell.css"

export default function AppShell() {
  return (
    <ChildrenProvider>
      <div className="app-shell">
        <AppSidebar />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </ChildrenProvider>
  )
}
