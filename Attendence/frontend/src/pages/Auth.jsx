import { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../contexts/AuthContext';
import api from '../services/api';
import { FiUserCheck, FiUserPlus, FiShield, FiBriefcase, FiAperture, FiMail, FiArrowLeft } from 'react-icons/fi';

export const Auth = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [showForgot, setShowForgot] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();

  // Registration State
  const [regData, setRegData] = useState({
    name: '', email: '', password: '', roll_number: '', role: 'student'
  });

  // Login State
  const [logData, setLogData] = useState({ email: '', password: '' });

  // Forgot Password State
  const [forgotEmail, setForgotEmail] = useState('');

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(logData.email, logData.password);
      if (data.role === 'student') navigate('/student');
      else if (data.role === 'admin') navigate('/admin');
      else navigate('/superadmin');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid email or password.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      // Clean payload before sending
      const payload = { ...regData };
      if (payload.role !== 'student') {
        delete payload.roll_number; // Admins don't have roll numbers
      } else if (!payload.roll_number.trim()) {
         throw new Error("Student Roll Number is absolutely required!");
      }

      await api.post('/auth/register', payload);
      setSuccess('Account created successfully! You can now sign in.');
      setIsLogin(true); // Flip back to login view smoothly
      setRegData({ name: '', email: '', password: '', roll_number: '', role: 'student' });
    } catch (err) {
      setError(err.message || err.response?.data?.detail || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const res = await api.post('/auth/forgot-password', { email: forgotEmail });
      setSuccess(res.data.message);
      setForgotEmail('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper d-flex align-items-center justify-content-center" style={{ minHeight: '100vh', backgroundColor: '#f1f5f9' }}>
      <div className="card shadow-lg flex-row border-0 auth-mega-card overflow-hidden" style={{ maxWidth: '900px', width: '100%', borderRadius: '24px' }}>
        
        {/* Left Side: Branding / Gradient panel */}
        <div className="d-none d-md-flex flex-column justify-content-center p-5 text-white" style={{ width: '45%', background: 'linear-gradient(135deg, #0f172a 0%, #3b82f6 100%)' }}>
          <h1 className="fw-bolder mb-3"><FiAperture className="me-2" />Smart</h1>
          <h2 className="fw-light mb-4">Attendance Platform.</h2>
          <p className="opacity-75" style={{ fontSize: '1.1rem' }}>
            Powered by FaceNet AI and real-time biometric synchronization.
          </p>
        </div>

        {/* Right Side: Form Engine */}
        <div className="flex-grow-1 p-5 bg-white position-relative">
          
          {/* Top Toggle Control - hidden during forgot password */}
          {!showForgot && (
            <div className="d-flex justify-content-end mb-4">
               <div className="btn-group shadow-sm bg-light p-1 rounded-pill" role="group">
                 <button 
                   type="button" 
                   className={`btn rounded-pill fw-bold border-0 px-4 ${isLogin ? 'btn-white text-primary shadow' : 'text-muted bg-transparent'}`}
                   onClick={() => { setIsLogin(true); setError(''); setSuccess(''); }}
                   style={isLogin ? {backgroundColor: 'white'} : {}}
                 >
                   Sign In
                 </button>
                 <button 
                   type="button" 
                   className={`btn rounded-pill fw-bold border-0 px-4 ${!isLogin ? 'btn-white text-primary shadow' : 'text-muted bg-transparent'}`}
                   onClick={() => { setIsLogin(false); setError(''); setSuccess(''); }}
                   style={!isLogin ? {backgroundColor: 'white'} : {}}
                 >
                   Register
                 </button>
               </div>
            </div>
          )}

          {/* ===== FORGOT PASSWORD VIEW ===== */}
          {showForgot ? (
            <>
              <button 
                className="btn btn-sm btn-light rounded-pill px-3 mb-3"
                onClick={() => { setShowForgot(false); setError(''); setSuccess(''); }}
              >
                <FiArrowLeft className="me-1" /> Back to Sign In
              </button>
              <h3 className="fw-bolder mb-1">Forgot Password?</h3>
              <p className="text-muted mb-4">Enter your registered email and we'll send you a reset link.</p>

              {error && <div className="alert alert-danger small p-2 border-0 bg-danger text-white bg-opacity-75">{error}</div>}
              {success && <div className="alert alert-success small p-2 border-0 bg-success text-white bg-opacity-75">{success}</div>}

              <form onSubmit={handleForgotPassword}>
                <div className="mb-4">
                  <label className="form-label text-muted small fw-bold">Email Address</label>
                  <div className="input-group">
                    <span className="input-group-text bg-light border-0"><FiMail className="text-primary"/></span>
                    <input 
                      type="email" 
                      className="form-control form-control-lg bg-light border-0" 
                      placeholder="you@example.com"
                      value={forgotEmail}
                      onChange={e => setForgotEmail(e.target.value)}
                      required 
                    />
                  </div>
                </div>
                <button type="submit" className="btn btn-primary btn-lg w-100 fw-bold rounded-3 shadow-sm py-3" disabled={loading}>
                  {loading ? 'Sending...' : '📧 Send Reset Link'}
                </button>
              </form>
            </>
          ) : (
            <>
              <h3 className="fw-bolder mb-1">{isLogin ? 'Welcome Back!' : 'Create an Account'}</h3>
              <p className="text-muted mb-4">{isLogin ? 'Please enter your credentials to proceed.' : 'Choose your role and get started.'}</p>

              {error && <div className="alert alert-danger small p-2 border-0 bg-danger text-white bg-opacity-75">{error}</div>}
              {success && <div className="alert alert-success small p-2 border-0 bg-success text-white bg-opacity-75">{success}</div>}

              {/* ----- LOGIN FORM ----- */}
              {isLogin ? (
                <form onSubmit={handleLoginSubmit}>
                  <div className="mb-3">
                    <label className="form-label text-muted small fw-bold">Email Address</label>
                    <input 
                      type="email" 
                      className="form-control form-control-lg bg-light border-0" 
                      value={logData.email}
                      onChange={e => setLogData({...logData, email: e.target.value})}
                      required 
                    />
                  </div>
                  <div className="mb-2">
                    <label className="form-label text-muted small fw-bold">Password</label>
                    <input 
                      type="password" 
                      className="form-control form-control-lg bg-light border-0" 
                      value={logData.password}
                      onChange={e => setLogData({...logData, password: e.target.value})}
                      required 
                    />
                  </div>
                  <div className="text-end mb-3">
                    <button 
                      type="button"
                      className="btn btn-link text-primary p-0 small fw-bold text-decoration-none"
                      onClick={() => { setShowForgot(true); setError(''); setSuccess(''); }}
                    >
                      Forgot Password?
                    </button>
                  </div>
                  <button type="submit" className="btn btn-primary btn-lg w-100 fw-bold rounded-3 shadow-sm py-3 mt-2" disabled={loading}>
                    {loading ? 'Authenticating...' : 'Secure Sign In'}
                  </button>
                </form>
              ) : (
              /* ----- REGISTER FORM ----- */
                <form onSubmit={handleRegisterSubmit}>
                  
                  {/* Role Capsules Selection */}
                  <div className="mb-4 d-flex gap-2 justify-content-between">
                    {[
                      { id: 'student', label: 'Student', icon: <FiUserCheck className="me-2"/> },
                      { id: 'admin', label: 'Admin', icon: <FiBriefcase className="me-2"/> },
                      { id: 'superadmin', label: 'Superadmin', icon: <FiShield className="me-2"/> }
                    ].map(r => (
                       <div 
                          key={r.id}
                          className={`flex-fill text-center p-2 rounded-3 border cursor-pointer border-1
                            ${regData.role === r.id ? 'border-primary bg-primary bg-opacity-10 text-primary fw-bold shadow-sm' : 'border-light bg-light text-muted'}`}
                          style={{ cursor: 'pointer', transition: 'all 0.2s', fontSize: '0.9rem' }}
                          onClick={() => setRegData({...regData, role: r.id})}
                       >
                         {r.icon} {r.label}
                       </div>
                    ))}
                  </div>

                  <div className="row g-3 mb-3">
                     <div className="col-12">
                       <label className="form-label text-muted small fw-bold">Full Name</label>
                       <input 
                         type="text" 
                         className="form-control bg-light border-0" 
                         value={regData.name}
                         onChange={e => setRegData({...regData, name: e.target.value})}
                         required 
                       />
                     </div>
                     
                     {/* Only show Roll Number if the user is a student! */}
                     {regData.role === 'student' && (
                       <div className="col-12 fade-in">
                         <label className="form-label text-muted small fw-bold d-flex justify-content-between">
                            <span>Roll Number / Face ID</span>
                            <span className="text-primary" style={{fontSize: '0.7rem'}}>* CRITICAL *</span>
                         </label>
                         <input 
                           type="text" 
                           className="form-control bg-light border-0 border-start border-3 border-primary" 
                           placeholder="Must match camera scanner ID"
                           value={regData.roll_number}
                           onChange={e => setRegData({...regData, roll_number: e.target.value})}
                           required 
                         />
                       </div>
                     )}
                     
                     <div className="col-12">
                       <label className="form-label text-muted small fw-bold">Email Address</label>
                       <input 
                         type="email" 
                         className="form-control bg-light border-0" 
                         value={regData.email}
                         onChange={e => setRegData({...regData, email: e.target.value})}
                         required 
                       />
                     </div>
                     <div className="col-12">
                       <label className="form-label text-muted small fw-bold">Password</label>
                       <input 
                         type="password" 
                         className="form-control bg-light border-0" 
                         value={regData.password}
                         onChange={e => setRegData({...regData, password: e.target.value})}
                         required 
                         minLength={6}
                       />
                     </div>
                  </div>

                  <button type="submit" className="btn btn-primary btn-lg w-100 fw-bold rounded-3 shadow-sm py-3 mt-3" disabled={loading}>
                    {loading ? 'Processing...' : 'Create Account'}
                  </button>
                </form>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
