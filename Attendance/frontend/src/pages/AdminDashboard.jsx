import { useState, useEffect } from 'react';
import api from '../services/api';
import { FiAlertTriangle, FiFileText, FiCamera, FiUsers, FiCheckCircle, FiVideo, FiActivity, FiDownload } from 'react-icons/fi';
import { FaceRegistrationModal } from '../components/FaceRegistrationModal';
import { VideoUploadModal, LiveScannerModal } from '../components/AttendanceModals';
import { Toast, useToast } from '../components/Toast';

export const AdminDashboard = () => {
  const [defaulters, setDefaulters] = useState([]);
  const [students, setStudents] = useState([]);
  const [remarkForm, setRemarkForm] = useState({ roll_number: '', remark: '' });
  const [loading, setLoading] = useState(true);
  const [showFaceModal, setShowFaceModal] = useState(false);
  const [showVideoModal, setShowVideoModal] = useState(false);
  const [showLiveModal, setShowLiveModal] = useState(false);
  const { toast, showToast, closeToast } = useToast();

  const handleExport = async (format) => {
    try {
      const res = await api.get(`/admin/export/${format}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Attendance_Report_${new Date().toISOString().slice(0,10)}.${format === 'excel' ? 'xlsx' : 'pdf'}`);
      document.body.appendChild(link);
      link.click();
      showToast(`${format.toUpperCase()} report downloaded!`, 'success');
    } catch (err) {
      showToast('Export failed.', 'error');
    }
  };

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [defRes, stuRes] = await Promise.all([
        api.get('/admin/defaulters'),
        api.get('/admin/students')
      ]);
      setDefaulters(defRes.data);
      setStudents(stuRes.data);
    } catch (err) {
      console.error('Error fetching admin data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const atRisk = students.filter(s => s.percentage < 75).length;
  const avg = students.length
    ? (students.reduce((acc, s) => acc + s.percentage, 0) / students.length).toFixed(1)
    : 0;

  const handleRemarkSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post('/admin/remarks', remarkForm);
      setRemarkForm({ roll_number: '', remark: '' });
      showToast('Remark added successfully!', 'success');
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to add remark.', 'error');
    }
  };

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary" /></div>;

  return (
    <div>
      <Toast message={toast.message} type={toast.type} onClose={closeToast} />

      <div className="d-flex justify-content-between align-items-center mb-4 text-wrap">
        <h2 className="fw-bold mb-0">Admin Command Center 🛡️</h2>
        <div className="d-flex gap-2 flex-wrap">
          <div className="btn-group shadow-sm">
            <button className="btn btn-outline-success fw-bold border-2" onClick={() => handleExport('excel')}>
              Excel
            </button>
            <button className="btn btn-outline-danger fw-bold border-2" onClick={() => handleExport('pdf')}>
              PDF
            </button>
          </div>
          <button className="btn btn-outline-primary px-3 py-2 rounded-3 shadow-sm fw-bold border-2" onClick={() => setShowLiveModal(true)}>
            <FiActivity className="me-2"/> Live Scan
          </button>
          <button className="btn btn-outline-info px-3 py-2 rounded-3 shadow-sm fw-bold border-2" onClick={() => setShowVideoModal(true)}>
            <FiVideo className="me-2"/> Upload Video
          </button>
          <button className="btn btn-primary px-3 py-2 rounded-3 shadow-sm fw-bold" onClick={() => setShowFaceModal(true)}>
            <FiCamera className="me-2"/> Register student
          </button>
        </div>
      </div>

      <FaceRegistrationModal
        show={showFaceModal}
        onClose={() => setShowFaceModal(false)}
        onSuccess={(data) => {
          setShowFaceModal(false);
          showToast(`✅ ${data.message}`, 'success');
          fetchAll();
        }}
      />

      <VideoUploadModal
        show={showVideoModal}
        onClose={() => setShowVideoModal(false)}
        onSuccess={(data) => {
          setShowVideoModal(false);
          showToast(`🎬 ${data.message}`, 'success');
        }}
      />

      <LiveScannerModal
        show={showLiveModal}
        onClose={() => {
          setShowLiveModal(false);
          fetchAll(); // Refresh attendance stats
        }}
      />


      {/* Quick Stats */}
      <div className="row mb-4">
        <div className="col-md-4 mb-3">
          <div className="card p-4 border-0 h-100">
            <div className="d-flex align-items-center gap-3">
              <div className="p-3 bg-primary bg-opacity-10 rounded-circle text-primary"><FiUsers size={22}/></div>
              <div>
                <p className="text-muted small mb-0">Total Students</p>
                <h3 className="fw-bold mb-0">{students.length}</h3>
              </div>
            </div>
          </div>
        </div>
        <div className="col-md-4 mb-3">
          <div className="card p-4 border-0 h-100">
            <div className="d-flex align-items-center gap-3">
              <div className="p-3 bg-success bg-opacity-10 rounded-circle text-success"><FiCheckCircle size={22}/></div>
              <div>
                <p className="text-muted small mb-0">Avg. Attendance</p>
                <h3 className="fw-bold mb-0">{avg}%</h3>
              </div>
            </div>
          </div>
        </div>
        <div className="col-md-4 mb-3">
          <div className="card p-4 border-0 h-100">
            <div className="d-flex align-items-center gap-3">
              <div className="p-3 bg-danger bg-opacity-10 rounded-circle text-danger"><FiAlertTriangle size={22}/></div>
              <div>
                <p className="text-muted small mb-0">At Risk (&lt;75%)</p>
                <h3 className={`fw-bold mb-0 ${atRisk > 0 ? 'text-danger' : 'text-success'}`}>{atRisk}</h3>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="row">
        {/* Defaulters Table */}
        <div className="col-md-8">
          <div className="card p-4 border-0">
            <h5 className="fw-bold mb-3 d-flex align-items-center">
              <FiAlertTriangle className="me-2 text-warning"/> Attendance Defaulters (&lt;75%)
            </h5>
            <div className="table-responsive">
              <table className="modern-table">
                <thead>
                  <tr><th>Student Name</th><th>Days Present</th><th>Percentage</th></tr>
                </thead>
                <tbody>
                  {defaulters.length > 0 ? defaulters.map((d, i) => (
                    <tr key={i}>
                      <td className="fw-bold">{d.student_name}</td>
                      <td>{d.present_days}</td>
                      <td>
                        <span className="badge bg-danger bg-opacity-10 text-danger px-3 py-2 rounded-pill">
                          {d.percentage}%
                        </span>
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan="3" className="text-center text-muted py-4">
                        No defaulters right now! Great attendance. 🎉
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Add Remark */}
        <div className="col-md-4">
          <div className="card p-4 border-0 h-100">
            <h5 className="fw-bold mb-3 d-flex align-items-center">
              <FiFileText className="me-2 text-info"/> Add Remark
            </h5>
            <form onSubmit={handleRemarkSubmit}>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Student Roll Number</label>
                <input type="text" className="form-control bg-light border-0" required
                  value={remarkForm.roll_number}
                  onChange={e => setRemarkForm({...remarkForm, roll_number: e.target.value})} />
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Remark Content</label>
                <textarea className="form-control bg-light border-0" rows={4} required
                  value={remarkForm.remark}
                  onChange={e => setRemarkForm({...remarkForm, remark: e.target.value})} />
              </div>
              <button type="submit" className="btn btn-primary w-100 rounded-3">Add Remark</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
