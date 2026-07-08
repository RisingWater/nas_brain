import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AdminLayout from './components/AdminLayout';
import UserList from './pages/UserList';
import ServiceManager from './pages/ServiceManager';
import LogViewer from './pages/LogViewer';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AdminLayout />}>
          <Route path="/users" element={<UserList />} />
          <Route path="/services" element={<ServiceManager />} />
          <Route path="/logs" element={<LogViewer />} />
          <Route path="/" element={<Navigate to="/users" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
