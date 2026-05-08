import { useState, useEffect, useContext } from 'react';
import api from '../services/api';
import { AuthContext } from '../contexts/AuthContext';
import { FiCheckCircle, FiXCircle, FiCalendar, FiMessageSquare, FiUser, FiCamera, FiBarChart2, FiClock } from 'react-icons/fi';
import Calendar from 'react-calendar';
import 'react-calendar/dist/Calendar.css';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const StudentDashboard = () => {
  const { user } = useContext(AuthContext);
  const [data, setData] = useState({ logs: [], total_days_present: 0, percentage: 0, course: '', student_class: '' });
  const [remarks, setRemarks] = useState([]);
  const [courses, setCourses] = useState([]);
  const [timetables, setTimetables] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [attRes, remRes, subRes, timeRes] = await Promise.all([
          api.get('/student/attendance'),
          api.get('/student/remarks'),
          api.get('/student/courses'),
          api.get('/student/timetables')
        ]);
        setData(attRes.data);
        setRemarks(remRes.data);
        setCourses(subRes.data);
        setTimetables(timeRes.data);
      } catch (err) {
        console.error("Error fetching student data", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary" /></div>;

  const trendData = data.logs.slice(-10).map((log, index) => ({
    name: log.date.split('-').slice(1).join('/'),
    status: log.status.toLowerCase() === 'present' ? 1 : 0
  }));

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

  return (
    <div>
      <h2 className="fw-bold mb-4">Welcome back, {user?.name || user?.email}! 👋</h2>

      <div className="row mb-4">
        {/* Enrolled Courses */}
        <div className="col-md-3 mb-3">
          <div className="card p-4 h-100 border-0 shadow-sm">
            <h6 className="text-muted mb-3">Enrolled Courses</h6>
            {courses.length > 0 ? (
              <ul className="list-unstyled mb-0">
                {courses.map((c, idx) => (
                  <li key={`${c.course_code}-${c.section}-${idx}`} className="mb-2 pb-2 border-bottom">
                    <div className="fw-bold text-primary">{c.course_code}</div>
                    <small className="text-muted">Section: {c.section}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted small mb-0">No courses enrolled</p>
            )}
          </div>
        </div>

        {/* Days Present */}
        <div className="col-md-3 mb-3">
          <div className="card p-4 h-100 border-0 shadow-sm">
            <div className="d-flex align-items-center mb-2">
              <div className="p-3 bg-primary bg-opacity-10 text-primary rounded-circle me-3"><FiCheckCircle size={24}/></div>
              <h6 className="text-muted mb-0">Days Present</h6>
            </div>
            <h2 className="fw-bold ms-5 ps-2 mb-0">{data.total_days_present}</h2>
          </div>
        </div>

        {/* Attendance % */}
        <div className="col-md-6 mb-3">
          <div className="card p-4 h-100 border-0 shadow-sm">
            <h6 className="text-muted mb-2">Global Attendance Percentage</h6>
            <div className="d-flex align-items-center gap-3">
              <div className="progress flex-grow-1" style={{height: '10px', borderRadius: '5px'}}>
                <div
                  className={`progress-bar ${data.percentage >= 75 ? 'bg-success' : 'bg-danger'}`}
                  style={{width: `${Math.min(data.percentage, 100)}%`, transition: 'width 0.5s'}}
                />
              </div>
              <span className={`fw-bold fs-5 ${data.percentage >= 75 ? 'text-success' : 'text-danger'}`}>
                {data.percentage}%
              </span>
            </div>
            {data.percentage < 75 && (
              <small className="text-danger mt-1">⚠️ Below 75% threshold — risk of being a defaulter!</small>
            )}
          </div>
        </div>
      </div>

      <div className="row mb-4">
        {/* Timetable Section */}
        <div className="col-md-12 mb-3">
          <div className="card p-4 border-0 shadow-sm">
            <h5 className="fw-bold mb-3 d-flex align-items-center"><FiClock className="me-2 text-info"/> My Weekly Timetable</h5>
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
                                <div key={i} className="mb-2 p-2 bg-white shadow-sm rounded border-start border-info border-3 text-start position-relative">
                                  <div className="fw-bold text-info" style={{ fontSize: '0.85rem' }}>{c.course_code}</div>
                                  <div className="text-muted" style={{ fontSize: '0.75rem' }}>Sec: {c.section} | {c.classroom}</div>
                                  <div className="text-muted mt-1" style={{ fontSize: '0.7rem' }}>Prof. {c.faculty_id}</div>
                                  {c.notes && <div className="text-muted fst-italic mt-1" style={{ fontSize: '0.7rem' }}>{c.notes}</div>}
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
                        No classes scheduled yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div className="row mb-4">
        {/* Attendance Trend Chart */}
        <div className="col-md-8 mb-3">
          <div className="card p-4 h-100 border-0 shadow-sm">
            <h5 className="fw-bold mb-3 d-flex align-items-center"><FiBarChart2 className="me-2 text-primary"/> Attendance Trend (Last 10 Days)</h5>
            {trendData.length > 0 ? (
              <div style={{ width: '100%', height: 250 }}>
                <ResponsiveContainer>
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                    <XAxis dataKey="name" stroke="#6b7280" fontSize={12} tickLine={false} />
                    <YAxis domain={[0, 1]} ticks={[0, 1]} tickFormatter={(val) => val === 1 ? 'P' : 'A'} stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip formatter={(value) => [value === 1 ? 'Present' : 'Absent', 'Status']} />
                    <Line type="monotone" dataKey="status" stroke="#4f46e5" strokeWidth={3} dot={{ r: 4, fill: '#4f46e5' }} activeDot={{ r: 6 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="text-center text-muted mt-4">Not enough data for trend chart.</div>
            )}
          </div>
        </div>

        {/* Profile & Registration Stub */}
        <div className="col-md-4 mb-3">
          <div className="card p-4 h-100 border-0 shadow-sm">
            <h5 className="fw-bold mb-3 d-flex align-items-center"><FiUser className="me-2 text-success"/> Profile Actions</h5>
            <div className="d-flex flex-column gap-3 mt-2">
              <button className="btn btn-outline-primary d-flex align-items-center justify-content-center py-2">
                <FiCamera className="me-2"/> Update Face Registration
              </button>
              <button className="btn btn-outline-secondary d-flex align-items-center justify-content-center py-2">
                <FiUser className="me-2"/> Edit Profile Details
              </button>
              <button className="btn btn-outline-info d-flex align-items-center justify-content-center py-2">
                Download Attendance PDF
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="row">
        {/* Attendance Calendar */}
        <div className="col-md-8">
          <div className="card p-4 border-0 shadow-sm">
            <h5 className="fw-bold mb-3 d-flex align-items-center"><FiCalendar className="me-2 text-primary"/> Interactive Attendance</h5>
            <div className="w-100 d-flex justify-content-center">
              <Calendar 
                className="border-0 w-100"
                tileContent={({ date, view }) => {
                  if (view === 'month') {
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const dateString = `${year}-${month}-${day}`;
                    
                    const log = data.logs.find(l => l.date === dateString);
                    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                    const today = new Date();
                    today.setHours(0,0,0,0);
                    const isPast = date < today;

                    if (log && log.status.toLowerCase() === 'present') {
                      return <div className="d-flex justify-content-center mt-2 text-success"><FiCheckCircle size={22}/></div>;
                    } else if (!log && isPast && !isWeekend) {
                      return <div className="d-flex justify-content-center mt-2 text-danger"><FiXCircle size={22}/></div>;
                    }
                  }
                }}
                tileClassName="py-3"
              />
            </div>
            <div className="d-flex justify-content-center mt-4 gap-4 small fw-bold">
               <span className="text-success"><FiCheckCircle className="me-1"/> Present</span>
               <span className="text-danger"><FiXCircle className="me-1"/> Absent</span>
            </div>
          </div>
        </div>

        {/* Remarks Column */}
        <div className="col-md-4">
          <div className="card p-4 h-100 border-0 shadow-sm">
            <h5 className="fw-bold mb-3 d-flex align-items-center"><FiMessageSquare className="me-2 text-warning"/> Admin Remarks</h5>
            {remarks.length > 0 ? (
              remarks.map((r, i) => (
                <div key={i} className="mb-3 p-3 rounded" style={{backgroundColor: '#fff3cd', border: '1px solid #ffe69c'}}>
                  <div className="d-flex justify-content-between align-items-center mb-1">
                    <span className="small fw-bold text-dark">{r.admin_email}</span>
                    <span className="badge text-dark bg-white shadow-sm" style={{fontSize: '0.7rem'}}>{r.date.split('T')[0]}</span>
                  </div>
                  <p className="mb-0 text-dark small">{r.remark}</p>
                </div>
              ))
            ) : (
              <div className="text-center text-muted mt-5 py-5">
                <FiCheckCircle size={40} className="text-success opacity-50 mb-3"/>
                <p>No negative remarks! Keep up the good work.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
