import { useState, useEffect } from 'react';
import api from '../services/api';
import { FiCalendar, FiClock, FiPlus, FiTrash2, FiEdit2, FiX } from 'react-icons/fi';
import { useToast, Toast } from '../components/Toast';

export const TimetableScheduler = () => {
  const [timetables, setTimetables] = useState([]);
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const { toast, showToast, closeToast } = useToast();

  const [form, setForm] = useState({
    course_code: '', course_name: '', section: '', classroom: '', day: 'Monday', start_time: '09:00', end_time: '10:00', notes: ''
  });
  const [editingTT, setEditingTT] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ttRes, coursesRes] = await Promise.all([
        api.get('/faculty/timetables'),
        api.get('/faculty/courses/search')
      ]);
      setTimetables(ttRes.data);
      setCourses(coursesRes.data);
    } catch (err) {
      console.error(err);
      showToast('Failed to load timetables', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      if (editingTT) {
        await api.put(`/faculty/timetables/${editingTT.course_code}/${editingTT.section}/${editingTT.day}/${editingTT.start_time}`, form);
        showToast('Timetable updated successfully!', 'success');
        setEditingTT(null);
      } else {
        await api.post('/faculty/timetables', form);
        showToast('Timetable scheduled successfully!', 'success');
      }
      fetchData();
      // Reset form but keep some defaults
      setForm({...form, course_code: '', course_name: '', section: '', notes: ''});
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to save', 'error');
    }
  };

  const handleDelete = async (tt) => {
    try {
      await api.delete(`/faculty/timetables/${tt.course_code}/${tt.section}/${tt.day}/${tt.start_time}`);
      showToast('Timetable deleted successfully!', 'success');
      fetchData();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to delete', 'error');
    }
  };

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary"/></div>;

  const daysOfWeek = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const dayColors = {
    Monday: '#e7d5b8',
    Tuesday: '#cbe4eb',
    Wednesday: '#d8d8eb',
    Thursday: '#e3dfd3',
    Friday: '#c5dfc7',
    Saturday: '#aebfd6'
  };
  
  // Extract unique, sorted time slots
  const timeSlots = [...new Set(timetables.map(t => `${t.start_time} - ${t.end_time}`))].sort();

  // Unique lists for autocomplete
  const uniqueCourseCodes = [...new Set(courses.map(c => c.course_code).filter(Boolean))];
  const uniqueSections = [...new Set(courses.filter(c => c.course_code === form.course_code).map(c => c.section).filter(Boolean))];

  return (
    <div>
      <Toast message={toast.message} type={toast.type} onClose={closeToast} />
      
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold mb-0 d-flex align-items-center"><FiCalendar className="me-2 text-primary"/> Timetable Scheduler</h2>
      </div>

      <div className="row">
        <div className="col-md-4 mb-4">
          <div className="card p-4 border-0 shadow-sm h-100">
            <h5 className="fw-bold mb-3">
              {editingTT ? 'Edit Class' : 'Schedule Class'}
            </h5>
            <form onSubmit={handleCreate}>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Course Code</label>
                <input type="text" className="form-control bg-light border-0" required placeholder="e.g. CS101"
                  value={form.course_code} onChange={e => {
                    const val = e.target.value;
                    // Auto-fill course name if we know it
                    const existing = courses.find(c => c.course_code === val);
                    setForm({...form, course_code: val, course_name: existing?.course_name || form.course_name});
                  }} list="courseList" />
                <datalist id="courseList">
                  {uniqueCourseCodes.map(c => <option key={c} value={c} />)}
                </datalist>
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Course Name (Optional)</label>
                <input type="text" className="form-control bg-light border-0" placeholder="e.g. Data Structures"
                  value={form.course_name} onChange={e => setForm({...form, course_name: e.target.value})} />
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Section</label>
                <input type="text" className="form-control bg-light border-0" required placeholder="e.g. A"
                  value={form.section} onChange={e => setForm({...form, section: e.target.value})} list="sectionList" />
                <datalist id="sectionList">
                  {uniqueSections.map(s => <option key={s} value={s} />)}
                </datalist>
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Classroom</label>
                <input type="text" className="form-control bg-light border-0" required placeholder="e.g. Room 101"
                  value={form.classroom} onChange={e => setForm({...form, classroom: e.target.value})} />
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Faculty Notes (Optional)</label>
                <input type="text" className="form-control bg-light border-0" placeholder="e.g. Bring laptops"
                  value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} />
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Day</label>
                <select className="form-select bg-light border-0" required
                  value={form.day} onChange={e => setForm({...form, day: e.target.value})}>
                  {daysOfWeek.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div className="row">
                <div className="col-6 mb-3">
                  <label className="form-label text-muted small fw-bold">Start Time</label>
                  <input type="time" className="form-control bg-light border-0" required
                    value={form.start_time} onChange={e => setForm({...form, start_time: e.target.value})} />
                </div>
                <div className="col-6 mb-3">
                  <label className="form-label text-muted small fw-bold">End Time</label>
                  <input type="time" className="form-control bg-light border-0" required
                    value={form.end_time} onChange={e => setForm({...form, end_time: e.target.value})} />
                </div>
              </div>
              <div className="d-flex gap-2">
                <button type="submit" className="btn btn-primary flex-fill rounded-3">
                  {editingTT ? <><FiEdit2 className="me-2"/>Update</> : <><FiPlus className="me-2"/>Schedule</>}
                </button>
                {editingTT && (
                  <button type="button" className="btn btn-outline-secondary rounded-3" onClick={() => {
                    setEditingTT(null);
                    setForm({...form, course_code: '', course_name: '', section: '', notes: ''});
                  }}>
                    <FiX />
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>

        <div className="col-md-8 mb-4">
          <div className="card p-4 border-0 shadow-sm h-100">
            <h5 className="fw-bold mb-3">Weekly Schedule</h5>
            <div className="table-responsive rounded-3 shadow-sm" style={{ border: '1px solid #dee2e6', overflow: 'hidden' }}>
              <table className="table table-bordered text-center align-middle mb-0" style={{ backgroundColor: '#f8f9fa' }}>
                <thead>
                  <tr>
                    <th style={{ backgroundColor: '#fef3c7', width: '10%', minWidth: '80px', borderBottom: '2px solid #dee2e6' }}>Time</th>
                    {daysOfWeek.map(day => (
                      <th key={day} style={{ backgroundColor: dayColors[day], width: '15%', minWidth: '120px', borderBottom: '2px solid #dee2e6' }}>
                        {day}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {timeSlots.length > 0 ? timeSlots.map((slot, index) => {
                    const [start, end] = slot.split(' - ');
                    return (
                      <tr key={slot}>
                        <td className="fw-bold" style={{ backgroundColor: '#f3f4f6', verticalAlign: 'middle' }}>
                          <div className="fs-6">{start}</div>
                          <div className="text-muted small">{end}</div>
                        </td>
                        {daysOfWeek.map(day => {
                          const cellClasses = timetables.filter(t => t.day === day && t.start_time === start && t.end_time === end);
                          return (
                            <td key={day} className="p-2 align-top" style={{ backgroundColor: cellClasses.length > 0 ? `${dayColors[day]}33` : '#ffffff' }}>
                              {cellClasses.map((c, i) => (
                                <div key={i} className="mb-2 p-2 bg-white shadow-sm rounded border-start border-primary border-3 text-start position-relative" style={{ transition: 'all 0.2s', cursor: 'default' }}>
                                  <div className="fw-bold text-primary" style={{ fontSize: '0.85rem' }}>{c.course_code}</div>
                                  <div className="text-muted" style={{ fontSize: '0.75rem' }}>Sec: {c.section} | {c.classroom}</div>
                                  {c.notes && <div className="text-muted fst-italic mt-1" style={{ fontSize: '0.7rem' }}>{c.notes}</div>}
                                  
                                  {/* Actions */}
                                  <div className="position-absolute top-0 end-0 p-1 d-flex gap-1" style={{ opacity: 0.7 }}>
                                    <button 
                                      className="btn btn-sm text-primary p-0 m-0" 
                                      onClick={() => {
                                        setEditingTT(c);
                                        setForm(c);
                                      }} 
                                      title="Edit Class"
                                    >
                                      <FiEdit2 size={14} />
                                    </button>
                                    <button 
                                      className="btn btn-sm text-danger p-0 m-0 ms-1" 
                                      onClick={() => handleDelete(c)} 
                                      title="Delete Class"
                                    >
                                      <FiTrash2 size={14} />
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  }) : (
                    <tr>
                      <td colSpan={7} className="text-center py-5 text-muted bg-white">
                        <div className="opacity-50 mb-2"><FiCalendar size={32} /></div>
                        No classes scheduled. Create a new schedule on the left.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

