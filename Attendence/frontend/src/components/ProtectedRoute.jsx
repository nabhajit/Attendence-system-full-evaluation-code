import { Navigate } from 'react-router-dom';
import { useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';

export const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user } = useContext(AuthContext);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // If role doesn't match, send them to their respectful dashboard
    if (user.role === 'student') return <Navigate to="/student" replace />;
    if (user.role === 'admin') return <Navigate to="/admin" replace />;
    if (user.role === 'superadmin') return <Navigate to="/superadmin" replace />;
  }

  return children;
};
