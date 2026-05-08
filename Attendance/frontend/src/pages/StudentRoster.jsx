import { useState, useEffect } from 'react';
import api from '../services/api';
import { FiUsers, FiFilter, FiTrendingUp, FiTrendingDown, FiSearch, FiCamera, FiEdit2, FiTrash2, FiX, FiCheck } from 'react-icons/fi';
import { FaceRegistrationModal } from '../components/FaceRegistrationModal';
import { Toast, useToast } from '../components/Toast';

export const StudentRoster = () => {
  const [students, setStudents] = useState([]);
  const [coursesList, setCoursesList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showFaceModal, setShowFaceModal] = useState(false);
  const { toast, showToast, closeToast } = useToast();

  // Filters
  const [search, setSearch] = useState('');
  const [filterCourse, setFilterCourse] = useState('');
  const [filterClass, setFilterClass] = useState('');
  const [sortBy, setSortBy] = useState('name');

  // Edit state
  const [editStudent, setEditStudent] = useState(null); // student being edited
  const [editForm, setEditForm] = useState({});
  const [editLoading, setEditLoading] = useState(false);

  // Delete state
  const [deleteTarget, setDeleteTarget] = useState(null); // roll of student to delete
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchStudents = async () => {
    setLoading(true);
    try {
      const [stuRes, courseRes] = await Promise.all([
        api.get('/admin/students'),
        api.get('/faculty/courses/search')
      ]);
      setStudents(stuRes.data);
      setCoursesList(courseRes.data);
    } catch (err) {
      console.error('Error fetching students', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStudents(); }, []);

  const courses = [...new Set(students.map(s => s.course).filter(Boolean))];
  const classes  = [...new Set(students.map(s => s.class).filter(Boolean))];

  const filtered = students
    .filter(s => !search || s.name?.toLowerCase().includes(search.toLowerCase()) || s.roll?.toLowerCase().includes(search.toLowerCase()))
    .filter(s => !filterCourse || s.course === filterCourse)
    .filter(s => !filterClass  || s.class  === filterClass)
    .sort((a, b) => {
      if (sortBy === 'attendance_asc')  return a.percentage - b.percentage;
      if (sortBy === 'attendance_desc') return b.percentage - a.percentage;
      return a.name?.localeCompare(b.name);
    });

  const resetFilters = () => { setSearch(''); setFilterCourse(''); setFilterClass(''); setSortBy('name'); };
  const hasFilters = search || filterCourse || filterClass || sortBy !== 'name';

  // Summary stats
  const avg    = students.length ? (students.reduce((acc, s) => acc + s.percentage, 0) / students.length).toFixed(1) : 0;
  const atRisk = students.filter(s => s.percentage < 75).length;

  // Open edit modal
  const openEdit = (s) => {
    setEditStudent(s);
    setEditForm({ name: s.name, course: s.course || '', class: s.class || '', contact: s.contact || '' });
  };

  const handleEditSave = async () => {
    setEditLoading(true);
    try {
      await api.patch(`/admin/students/${editStudent.roll}`, editForm);
      showToast('Student updated successfully!', 'success');
      setEditStudent(null);
      fetchStudents();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Update failed.', 'error');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDelete = async () => {
    setDeleteLoading(true);
    try {
      await api.delete(`/admin/students/${deleteTarget.roll}`);
      showToast(`Student '${deleteTarget.name}' removed.`, 'success');
      setDeleteTarget(null);
      fetchStudents();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Delete failed.', 'error');
    } finally {
      setDeleteLoading(false);
    }
  };

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary" /></div>;

  return (
    <div>
      <Toast message={toast.message} type={toast.type} onClose={closeToast} />

      {/* ===== EDIT MODAL ===== */}
      {editStudent && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1050, backgroundColor: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card p-4" style={{ width: '480px', maxWidth: '95vw', borderRadius: '20px' }}>
            <div className="d-flex justify-content-between align-items-center mb-4">
              <h5 className="fw-bold mb-0"><FiEdit2 className="me-2 text-primary"/>Edit Student</h5>
              <button className="btn btn-sm btn-light rounded-circle" onClick={() => setEditStudent(null)}>
                <FiX />
              </button>
            </div>
            <div className="row g-3">
              <div className="col-12">
                <label className="form-label text-muted small fw-bold">Full Name</label>
                <input className="form-control bg-light border-0" value={editForm.name}
                  onChange={e => setEditForm({...editForm, name: e.target.value})} />
              </div>
              <div className="col-12">
                <label className="form-label text-muted small fw-bold">Course</label>
                <input className="form-control bg-light border-0" value={editForm.course} list="course-options"
                  onChange={e => setEditForm({...editForm, course: e.target.value})} />
                <datalist id="course-options">
                  {[...new Set(coursesList.map(c => c.course_code))].map(code => (
                    <option key={code} value={code} />
                  ))}
                </datalist>
              </div>
              <div className="col-md-6">
                <label className="form-label text-muted small fw-bold">Class / Section</label>
                <input className="form-control bg-light border-0" value={editForm.class} list="section-options"
                  onChange={e => setEditForm({...editForm, class: e.target.value})} />
                <datalist id="section-options">
                  {coursesList.filter(c => c.course_code === editForm.course).map(c => (
                    <option key={c.section} value={c.section} />
                  ))}
                </datalist>
              </div>
              <div className="col-md-6">
                <label className="form-label text-muted small fw-bold">Contact</label>
                <input className="form-control bg-light border-0" value={editForm.contact}
                  onChange={e => setEditForm({...editForm, contact: e.target.value})} />
              </div>
            </div>
            <div className="d-flex gap-2 mt-4">
              <button className="btn btn-outline-secondary flex-fill" onClick={() => setEditStudent(null)}>Cancel</button>
              <button className="btn btn-primary flex-fill fw-bold" onClick={handleEditSave} disabled={editLoading}>
                {editLoading ? 'Saving...' : <><FiCheck className="me-1"/>Save Changes</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===== DELETE CONFIRM MODAL ===== */}
      {deleteTarget && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1050, backgroundColor: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card p-4 text-center" style={{ width: '400px', maxWidth: '95vw', borderRadius: '20px' }}>
            <div className="mb-3" style={{ fontSize: '3rem' }}>⚠️</div>
            <h5 className="fw-bold mb-2">Delete Student?</h5>
            <p className="text-muted mb-1">You are about to permanently remove:</p>
            <p className="fw-bold text-danger mb-1">{deleteTarget.name}</p>
            <p className="text-muted small mb-4">Roll: {deleteTarget.roll} | Course: {deleteTarget.course || 'N/A'}</p>
            <p className="small text-danger mb-4">This will also delete all their attendance records. This action cannot be undone.</p>
            <div className="d-flex gap-2">
              <button className="btn btn-outline-secondary flex-fill" onClick={() => setDeleteTarget(null)}>Cancel</button>
              <button className="btn btn-danger flex-fill fw-bold" onClick={handleDelete} disabled={deleteLoading}>
                {deleteLoading ? 'Deleting...' : <><FiTrash2 className="me-1"/>Yes, Delete</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="fw-bold mb-1">Student Roster 📋</h2>
          <p className="text-muted mb-0">Manage and monitor all registered students.</p>
        </div>
        <button className="btn btn-primary px-4 py-2 rounded-3 shadow-sm fw-bold" onClick={() => setShowFaceModal(true)}>
          <FiCamera className="me-2"/> Register New Student
        </button>
      </div>

      <FaceRegistrationModal
        show={showFaceModal}
        onClose={() => setShowFaceModal(false)}
        onSuccess={(data) => {
          setShowFaceModal(false);
          showToast(`✅ ${data.message}`, 'success');
          fetchStudents();
        }}
      />

      {/* Summary Cards */}
      <div className="row mb-4">
        <div className="col-md-4 mb-3">
          <div className="card p-4 border-0">
            <h6 className="text-muted mb-1">Total Students</h6>
            <h2 className="fw-bold text-primary mb-0">{students.length}</h2>
          </div>
        </div>
        <div className="col-md-4 mb-3">
          <div className="card p-4 border-0">
            <h6 className="text-muted mb-1">Avg. Attendance</h6>
            <h2 className="fw-bold text-success mb-0">{avg}%</h2>
          </div>
        </div>
        <div className="col-md-4 mb-3">
          <div className="card p-4 border-0">
            <h6 className="text-muted mb-1">At Risk (&lt;75%)</h6>
            <h2 className={`fw-bold mb-0 ${atRisk > 0 ? 'text-danger' : 'text-success'}`}>{atRisk}</h2>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card p-3 mb-4 border-0">
        <div className="d-flex flex-wrap gap-2 align-items-center">
          <div className="input-group" style={{maxWidth: '220px'}}>
            <span className="input-group-text bg-light border-0"><FiSearch className="text-muted"/></span>
            <input type="text" className="form-control bg-light border-0" placeholder="Search name or roll..."
              value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="form-select border-0 bg-light" style={{maxWidth: '160px'}}
            value={filterCourse} onChange={e => setFilterCourse(e.target.value)}>
            <option value="">All Courses</option>
            {courses.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className="form-select border-0 bg-light" style={{maxWidth: '140px'}}
            value={filterClass} onChange={e => setFilterClass(e.target.value)}>
            <option value="">All Classes</option>
            {classes.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select className="form-select border-0 bg-light" style={{maxWidth: '190px'}}
            value={sortBy} onChange={e => setSortBy(e.target.value)}>
            <option value="name">Sort by Name</option>
            <option value="attendance_asc">⬆ Lowest Attendance</option>
            <option value="attendance_desc">⬇ Highest Attendance</option>
          </select>
          {hasFilters && (
            <button className="btn btn-sm btn-outline-secondary" onClick={resetFilters}>
              <FiFilter className="me-1"/> Reset
            </button>
          )}
          <span className="ms-auto text-muted small">
            Showing <strong>{filtered.length}</strong> of <strong>{students.length}</strong>
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="card p-4 border-0">
        <div className="table-responsive">
          <table className="modern-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Roll</th>
                <th>Course</th>
                <th>Class</th>
                <th>Days Present</th>
                <th>Attendance</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length > 0 ? filtered.map((s, i) => (
                <tr key={i}>
                  <td className="text-muted small">{i + 1}</td>
                  <td className="fw-bold">{s.name}</td>
                  <td><span className="badge bg-light text-dark border">{s.roll}</span></td>
                  <td>{s.course || '—'}</td>
                  <td>{s.class || '—'}</td>
                  <td>{s.present_days}</td>
                  <td style={{minWidth: '140px'}}>
                    <div className="d-flex align-items-center gap-2">
                      <div className="progress flex-grow-1" style={{height: '6px'}}>
                        <div className={`progress-bar ${s.percentage >= 75 ? 'bg-success' : 'bg-danger'}`}
                          style={{width: `${Math.min(s.percentage, 100)}%`}} />
                      </div>
                      <span className="small fw-bold" style={{minWidth: '38px'}}>{s.percentage}%</span>
                    </div>
                  </td>
                  <td>
                    {s.percentage >= 75
                      ? <span className="badge bg-success bg-opacity-15 text-success px-3 py-2 rounded-pill d-flex align-items-center gap-1" style={{width: 'fit-content'}}><FiTrendingUp size={12}/> Good</span>
                      : <span className="badge bg-danger bg-opacity-15 text-danger px-3 py-2 rounded-pill d-flex align-items-center gap-1" style={{width: 'fit-content'}}><FiTrendingDown size={12}/> At Risk</span>
                    }
                  </td>
                  <td>
                    <div className="d-flex gap-2">
                      <button
                        className="btn btn-sm btn-light border rounded-2"
                        title="Edit Student"
                        onClick={() => openEdit(s)}
                      >
                        <FiEdit2 size={14} className="text-primary"/>
                      </button>
                      <button
                        className="btn btn-sm btn-light border rounded-2"
                        title="Delete Student"
                        onClick={() => setDeleteTarget(s)}
                      >
                        <FiTrash2 size={14} className="text-danger"/>
                      </button>
                    </div>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="9" className="text-center text-muted py-5">
                    <FiUsers size={40} className="opacity-25 mb-3 d-block mx-auto"/>
                    No students found matching your filters.
                    <br/>
                    <button className="btn btn-sm btn-primary mt-3" onClick={resetFilters}>Clear Filters</button>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
