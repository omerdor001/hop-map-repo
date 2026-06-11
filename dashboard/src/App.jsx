import { Routes, Route, Navigate } from "react-router-dom"
import LandingPage from "./pages/LandingPage"
import LoginPage from "./pages/LoginPage"
import RequireAuth from "./components/auth/RequireAuth"
import AppShell from "./pages/app/AppShell"
import KidsPage from "./pages/app/KidsPage"
import SettingsPage from "./pages/app/SettingsPage"
import ErrorBoundary from "./components/ErrorBoundary"

export default function App() {
  return (
    <ErrorBoundary>
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/app" element={<Navigate to="/app/kids" replace />} />
          <Route path="/app/kids" element={<KidsPage />} />
          <Route path="/app/settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </ErrorBoundary>
  )
}
