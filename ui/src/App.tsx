import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Bundles from "./pages/Bundles";
import BundleLogs from "./pages/BundleLogs";
import Dashboard from "./pages/Dashboard";
import LetsCheckLogs from "./pages/LetsCheckLogs";
import LiveMonitor from "./pages/LiveMonitor";
import Backup from "./pages/Backup";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="live" element={<LiveMonitor />} />
        <Route path="backup" element={<Backup />} />
        <Route path="live-logs" element={<LetsCheckLogs />} />
        <Route path="bundle-logs" element={<BundleLogs />} />
        <Route path="logs" element={<Navigate to="/live-logs" replace />} />
        <Route path="bundles" element={<Bundles />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
