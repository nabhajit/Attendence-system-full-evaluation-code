import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import api from '../services/api';
import { FiLock, FiCheckCircle, FiAlertTriangle } from 'react-icons/fi';

export const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleReset = async (e) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: newPassword });
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reset password. The link may have expired.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh', backgroundColor: '#f1f5f9' }}>
        <div className="card p-5 border-0 shadow-lg text-center" style={{ maxWidth: '460px', borderRadius: '20px' }}>
          <FiAlertTriangle size={48} className="text-warning mx-auto mb-3" />
          <h4 className="fw-bold mb-2">Invalid Reset Link</h4>
          <p className="text-muted mb-4">This password reset link is invalid or missing. Please request a new one from the login page.</p>
          <button className="btn btn-primary fw-bold rounded-3 px-4 py-2" onClick={() => navigate('/login')}>
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh', backgroundColor: '#f1f5f9' }}>
        <div className="card p-5 border-0 shadow-lg text-center" style={{ maxWidth: '460px', borderRadius: '20px' }}>
          <FiCheckCircle size={56} className="text-success mx-auto mb-3" />
          <h4 className="fw-bold mb-2">Password Reset Successfully!</h4>
          <p className="text-muted mb-4">Your password has been updated. You can now sign in with your new credentials.</p>
          <button className="btn btn-primary btn-lg fw-bold rounded-3 px-4 py-3 shadow-sm" onClick={() => navigate('/login')}>
            Sign In Now
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh', backgroundColor: '#f1f5f9' }}>
      <div className="card p-5 border-0 shadow-lg" style={{ maxWidth: '480px', width: '100%', borderRadius: '20px' }}>
        <div className="text-center mb-4">
          <div className="d-inline-flex align-items-center justify-content-center rounded-circle mb-3"
               style={{ width: '64px', height: '64px', background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)' }}>
            <FiLock size={28} className="text-white" />
          </div>
          <h3 className="fw-bolder mb-1">Set New Password</h3>
          <p className="text-muted">Choose a strong password for your account.</p>
        </div>

        {error && <div className="alert alert-danger small p-2 border-0 bg-danger text-white bg-opacity-75 mb-3">{error}</div>}

        <form onSubmit={handleReset}>
          <div className="mb-3">
            <label className="form-label text-muted small fw-bold">New Password</label>
            <input
              type="password"
              className="form-control form-control-lg bg-light border-0"
              placeholder="Minimum 8 characters"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>
          <div className="mb-4">
            <label className="form-label text-muted small fw-bold">Confirm Password</label>
            <input
              type="password"
              className="form-control form-control-lg bg-light border-0"
              placeholder="Re-enter your password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>

          {/* Password rules hint */}
          <div className="mb-4 p-3 rounded-3" style={{ backgroundColor: '#f8fafc' }}>
            <p className="small text-muted mb-1 fw-bold">Password must contain:</p>
            <ul className="small text-muted mb-0 ps-3">
              <li className={newPassword.length >= 8 ? 'text-success' : ''}>At least 8 characters</li>
              <li className={/\d/.test(newPassword) ? 'text-success' : ''}>At least one number</li>
              <li className={/[a-zA-Z]/.test(newPassword) ? 'text-success' : ''}>At least one letter</li>
            </ul>
          </div>

          <button type="submit" className="btn btn-primary btn-lg w-100 fw-bold rounded-3 shadow-sm py-3" disabled={loading}>
            {loading ? 'Resetting...' : '🔐 Reset Password'}
          </button>
        </form>
      </div>
    </div>
  );
};
