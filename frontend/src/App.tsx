import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AdminLayout from './components/AdminLayout';
import UserList from './pages/UserList';
import ServiceManager from './pages/ServiceManager';
import LogViewer from './pages/LogViewer';
import ToolManager from './pages/ToolManager';
import TTSCacheManager from './pages/TTSCacheManager';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AdminLayout />}>
          <Route path="/users" element={<UserList />} />
          <Route path="/services" element={<ServiceManager />} />
          <Route path="/logs" element={<LogViewer />} />
          <Route path="/tools" element={<ToolManager />} />
          <Route path="/tts-cache" element={<TTSCacheManager />} />
          <Route path="/" element={<Navigate to="/users" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
