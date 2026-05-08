import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { DashboardLayout } from './components/DashboardLayout';
import { Auth } from './pages/Auth';
import { StudentDashboard } from './pages/StudentDashboard';
import { AdminDashboard } from './pages/AdminDashboard';
import { SuperadminDashboard } from './pages/SuperadminDashboard';
import { StudentRoster } from './pages/StudentRoster';
import { LeavesPage } from './pages/LeavesPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { TimetableScheduler } from './pages/TimetableScheduler';
import { ResetPassword } from './pages/ResetPassword';
import 'bootstrap/dist/css/bootstrap.min.css';
import './index.css';

// Forced Update for Camera Logic v2.0
function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Public Unified Auth Route */}
          <Route path="/login" element={<Auth />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          
          {/* App Redirection Gateway */}
          <Route path="/" element={<ProtectedRoute><Navigate to="/login" replace /></ProtectedRoute>} />

          {/* Protected Dashboards wrapped with consistent Layout */}
          <Route element={<DashboardLayout />}>
             {/* Student Portal */}
             <Route 
                path="/student" 
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <StudentDashboard />
                  </ProtectedRoute>
                } 
             />
             <Route 
                path="/student/leaves" 
                element={
                  <ProtectedRoute allowedRoles={['student']}>
                    <LeavesPage />
                  </ProtectedRoute>
                } 
             />
             
             {/* Admin Portal */}
             <Route 
                path="/admin" 
                element={
                  <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
                    <AdminDashboard />
                  </ProtectedRoute>
                } 
             />
             
             {/* Superadmin Portal */}
             <Route 
                path="/superadmin" 
                element={
                  <ProtectedRoute allowedRoles={['superadmin']}>
                    <SuperadminDashboard />
                  </ProtectedRoute>
                } 
             />

             {/* Shared Admin/Superadmin Student Roster Page */}
             <Route 
                path="/admin/roster" 
                element={
                  <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
                    <StudentRoster />
                  </ProtectedRoute>
                } 
             />

             {/* Admin Analytics Page */}
             <Route 
                path="/admin/analytics" 
                element={
                  <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
                    <AnalyticsPage />
                  </ProtectedRoute>
                } 
             />

             {/* Admin Timetable Scheduler */}
             <Route 
                path="/admin/timetables" 
                element={
                  <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
                    <TimetableScheduler />
                  </ProtectedRoute>
                } 
             />

             {/* Admin Leave Management Page */}
             <Route 
                path="/admin/leaves" 
                element={
                  <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
                    <LeavesPage />
                  </ProtectedRoute>
                } 
             />
          </Route>
          
          {/* Catch-all 404 falling back to root gateway */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
