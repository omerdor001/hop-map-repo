import { Routes, Route, Navigate } from "react-router-dom"
import LandingPage from "./pages/LandingPage"
import LoginPage from "./pages/LoginPage"
import ResetPasswordPage from "./pages/ResetPasswordPage"
import RequireAuth from "./components/auth/RequireAuth"
import AppShell from "./pages/app/AppShell"
import KidsPage from "./pages/app/KidsPage"
import AlertsPage from "./pages/app/AlertsPage"
import SubscriptionPage from "./pages/app/SubscriptionPage"
import ErrorBoundary from "./components/ErrorBoundary"

export default function App() {
  return (
    <ErrorBoundary>
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/app" element={<Navigate to="/app/kids" replace />} />
          <Route path="/app/kids" element={<KidsPage />} />
          <Route path="/app/alerts" element={<AlertsPage />} />
          <Route path="/app/subscription" element={<SubscriptionPage />} />
          <Route path="/app/settings" element={<Navigate to="/app/alerts" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </ErrorBoundary>
  )
}
