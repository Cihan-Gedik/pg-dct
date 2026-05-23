import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Bundles from "./pages/Bundles";
import Dashboard from "./pages/Dashboard";
import LetsCheckLogs from "./pages/LetsCheckLogs";
import LiveMonitor from "./pages/LiveMonitor";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="live" element={<LiveMonitor />} />
        <Route path="logs" element={<LetsCheckLogs />} />
        <Route path="bundles" element={<Bundles />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
