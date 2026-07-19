import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AdminLayout from './components/AdminLayout';
import UserList from './pages/UserList';
import ServiceManager from './pages/ServiceManager';
import LogViewer from './pages/LogViewer';
import ToolManager from './pages/ToolManager';
import TTSCacheManager from './pages/TTSCacheManager';
import ScheduleManager from './pages/ScheduleManager';
import DetectorManager from './pages/DetectorManager';
import ProcessorManager from './pages/ProcessorManager';
import ChatHistory from './pages/ChatHistory';
import MemoryManager from './pages/MemoryManager';
import WakewordManager from './pages/WakewordManager';
import VoiceprintManager from './pages/VoiceprintManager';
import Dashboard from './pages/Dashboard';
import BackupManager from './pages/BackupManager';
import TracePage from './pages/TracePage';
import AIStatusPage from './pages/AIStatusPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/ai-status" element={<AIStatusPage />} />
        <Route element={<AdminLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/users" element={<UserList />} />
          <Route path="/services" element={<ServiceManager />} />
          <Route path="/logs" element={<LogViewer />} />
          <Route path="/tools" element={<ToolManager />} />
          <Route path="/tts-cache" element={<TTSCacheManager />} />
          <Route path="/schedules" element={<ScheduleManager />} />
          <Route path="/detectors" element={<DetectorManager />} />
          <Route path="/processors" element={<ProcessorManager />} />
          <Route path="/chat-history" element={<ChatHistory />} />
          <Route path="/memory" element={<MemoryManager />} />
          <Route path="/wakeword" element={<WakewordManager />} />
          <Route path="/voiceprints" element={<VoiceprintManager />} />
          <Route path="/backup" element={<BackupManager />} />
          <Route path="/traces" element={<TracePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
