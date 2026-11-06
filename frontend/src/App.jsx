import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Onboarding from "./pages/Onboarding";
import Dashboard from "./pages/Dashboard";
import DeploymentAnalysis from "./pages/DeploymentAnalysis";
import IncidentHistory from "./pages/IncidentHistory";
import IncidentDetail from "./pages/IncidentDetail";
import MemoryExplorer from "./pages/MemoryExplorer";
import RiskPrediction from "./pages/RiskPrediction";
import AIAssistant from "./pages/AIAssistant";
import Settings from "./pages/Settings";

function Protected({ children, needOnboarded = true }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-wrap"><span className="spinner dark" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (needOnboarded && !user.onboarded) return <Navigate to="/onboarding" replace />;
  if (!needOnboarded && user.onboarded) return <Navigate to="/" replace />;
  return children;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to="/" replace /> : children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/onboarding" element={<Protected needOnboarded={false}><Onboarding /></Protected>} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analyze" element={<DeploymentAnalysis />} />
        <Route path="/incidents" element={<IncidentHistory />} />
        <Route path="/incidents/:id" element={<IncidentDetail />} />
        <Route path="/memory" element={<MemoryExplorer />} />
        <Route path="/risk" element={<RiskPrediction />} />
        <Route path="/assistant" element={<AIAssistant />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
