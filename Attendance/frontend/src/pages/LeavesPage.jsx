import { useState, useEffect, useContext } from 'react';
import api from '../services/api';
import { AuthContext } from '../contexts/AuthContext';
import { Toast, useToast } from '../components/Toast';
import { FiCalendar, FiCheckCircle, FiXCircle, FiClock, FiPlus, FiFileText } from 'react-icons/fi';

/* ============================
   STUDENT VIEW
   ============================ */
const StudentLeavesView = () => {
  const [leaves, setLeaves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ date_start: '', date_end: '', reason: '' });
  const { toast, showToast, closeToast } = useToast();

  const fetchLeaves = async () => {
    setLoading(true);
    try {
      const res = await api.get('/student/leaves');
      setLeaves(res.data);
    } catch (err) {
      console.error('Error fetching leaves', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLeaves(); }, []);

  const handleApply = async (e) => {
    e.preventDefault();
    try {
      await api.post('/student/leaves', form);
      setForm({ date_start: '', date_end: '', reason: '' });
      showToast('Leave application submitted successfully!', 'success');
      fetchLeaves();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to submit leave.', 'error');
    }
  };

  const statusConfig = {
    pending:  { cls: 'text-warning bg-warning',   icon: <FiClock size={13}/>,       label: 'Pending' },
    approved: { cls: 'text-success bg-success',   icon: <FiCheckCircle size={13}/>, label: 'Approved' },
    rejected: { cls: 'text-danger bg-danger',     icon: <FiXCircle size={13}/>,     label: 'Rejected' },
  };

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary" /></div>;

  return (
    <div>
      <Toast message={toast.message} type={toast.type} onClose={closeToast} />

      <h2 className="fw-bold mb-1">Leave Requests 📅</h2>
      <p className="text-muted mb-4">Apply for leave and track your application status.</p>

      <div className="row">
        {/* Application Form */}
        <div className="col-md-5 mb-4">
          <div className="card p-4 border-0 h-100">
            <h5 className="fw-bold mb-3 d-flex align-items-center">
              <FiPlus className="me-2 text-primary"/> Apply for Leave
            </h5>
            <form onSubmit={handleApply}>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">From Date</label>
                <input type="date" className="form-control bg-light border-0" required
                  value={form.date_start} onChange={e => setForm({...form, date_start: e.target.value})} />
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">To Date</label>
                <input type="date" className="form-control bg-light border-0" required
                  value={form.date_end} onChange={e => setForm({...form, date_end: e.target.value})} />
              </div>
              <div className="mb-4">
                <label className="form-label text-muted small fw-bold">Reason for Leave</label>
                <textarea className="form-control bg-light border-0" rows={4} required placeholder="Briefly describe your reason..."
                  value={form.reason} onChange={e => setForm({...form, reason: e.target.value})} />
              </div>
              <button type="submit" className="btn btn-primary w-100 py-2 fw-bold rounded-3">
                <FiCalendar className="me-2"/> Submit Leave Application
              </button>
            </form>
          </div>
        </div>

        {/* Applications List */}
        <div className="col-md-7 mb-4">
          <div className="card p-4 border-0">
            <h5 className="fw-bold mb-3 d-flex align-items-center">
              <FiFileText className="me-2 text-primary"/> My Applications
            </h5>
            {leaves.length > 0 ? leaves.map((l, i) => {
              const s = statusConfig[l.status] || statusConfig.pending;
              return (
                <div key={i} className="mb-3 p-3 rounded-3" style={{border: '1px solid #f0f0f0', backgroundColor: '#fafafa'}}>
                  <div className="d-flex justify-content-between align-items-start mb-2">
                    <span className="fw-bold">{l.date_start} → {l.date_end}</span>
                    <span className={`badge ${s.cls} bg-opacity-10 px-3 py-2 rounded-pill d-flex align-items-center gap-1`}>
                      {s.icon} {s.label}
                    </span>
                  </div>
                  <p className="text-muted mb-0 small">{l.reason}</p>
                </div>
              );
            }) : (
              <div className="text-center text-muted py-5">
                <FiCalendar size={40} className="opacity-25 mb-3 d-block mx-auto"/>
                No leave applications yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

/* ============================
   ADMIN VIEW
   ============================ */
const AdminLeavesView = () => {
  const [leaves, setLeaves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const { toast, showToast, closeToast } = useToast();

  const fetchLeaves = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/leaves');
      setLeaves(res.data);
    } catch (err) {
      console.error('Error fetching leaves', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchLeaves(); }, []);

  const handleAction = async (id, status) => {
    try {
      await api.patch(`/admin/leaves/${id}?status=${status}`);
      showToast(`Leave ${status} successfully.`, status === 'approved' ? 'success' : 'error');
      fetchLeaves();
    } catch (err) {
      showToast('Action failed.', 'error');
    }
  };

  const filtered = leaves.filter(l => filter === 'all' || l.status === filter);
  const pending = leaves.filter(l => l.status === 'pending').length;

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary" /></div>;

  return (
    <div>
      <Toast message={toast.message} type={toast.type} onClose={closeToast} />

      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="fw-bold mb-1">Leave Management 📅</h2>
          <p className="text-muted mb-0">Review and respond to student leave applications.</p>
        </div>
        {pending > 0 && (
          <span className="badge bg-warning text-dark fs-6 px-3 py-2 rounded-pill">
            <FiClock className="me-1"/> {pending} pending
          </span>
        )}
      </div>

      {/* Filter Tabs */}
      <div className="btn-group mb-4 shadow-sm" role="group">
        {['all', 'pending', 'approved', 'rejected'].map(f => (
          <button
            key={f}
            type="button"
            className={`btn ${filter === f ? 'btn-primary' : 'btn-outline-secondary'} text-capitalize`}
            onClick={() => setFilter(f)}
          >
            {f}
            <span className="badge ms-2 bg-white text-dark">
              {f === 'all' ? leaves.length : leaves.filter(l => l.status === f).length}
            </span>
          </button>
        ))}
      </div>

      {/* Leave Cards */}
      {filtered.length === 0 ? (
        <div className="text-center text-muted py-5">
          <FiCalendar size={48} className="opacity-25 mb-3 d-block mx-auto"/>
          No {filter === 'all' ? '' : filter} leave requests found.
        </div>
      ) : (
        <div className="row g-3">
          {filtered.map((l, i) => (
            <div key={i} className="col-md-6">
              <div className="card border-0 p-4 h-100">
                <div className="d-flex justify-content-between align-items-start mb-3">
                  <div>
                    <h6 className="fw-bold mb-0">{l.student_name || 'Unknown Student'}</h6>
                    <small className="text-muted">Roll: {l.roll_number}</small>
                  </div>
                  <span className={`badge px-3 py-2 rounded-pill small ${
                    l.status === 'approved' ? 'bg-success bg-opacity-10 text-success' :
                    l.status === 'rejected' ? 'bg-danger bg-opacity-10 text-danger' :
                    'bg-warning bg-opacity-10 text-warning'
                  }`}>
                    {l.status === 'pending'  && <FiClock size={12} className="me-1"/>}
                    {l.status === 'approved' && <FiCheckCircle size={12} className="me-1"/>}
                    {l.status === 'rejected' && <FiXCircle size={12} className="me-1"/>}
                    {l.status}
                  </span>
                </div>

                <div className="mb-2 small text-muted d-flex align-items-center gap-2">
                  <FiCalendar size={13}/>
                  <span>{l.date_start} → {l.date_end}</span>
                </div>

                <p className="text-dark small mb-3">{l.reason}</p>

                {l.status === 'pending' && (
                  <div className="d-flex gap-2 mt-auto">
                    <button
                      className="btn btn-success flex-fill rounded-3 fw-bold"
                      onClick={() => handleAction(l._id, 'approved')}
                    >
                      <FiCheckCircle className="me-1"/> Approve
                    </button>
                    <button
                      className="btn btn-outline-danger flex-fill rounded-3 fw-bold"
                      onClick={() => handleAction(l._id, 'rejected')}
                    >
                      <FiXCircle className="me-1"/> Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ============================
   SMART ROUTER - renders correct view based on role
   ============================ */
export const LeavesPage = () => {
  const { user } = useContext(AuthContext);
  return user?.role === 'student' ? <StudentLeavesView /> : <AdminLeavesView />;
};
