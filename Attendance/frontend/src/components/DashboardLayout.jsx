import { useContext } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { AuthContext } from '../contexts/AuthContext';
import { 
  FiGrid, FiLogOut, FiUser, FiUsers, FiShield, FiCalendar, FiFileText, FiActivity, FiBookOpen, FiClock
} from 'react-icons/fi';

export const DashboardLayout = () => {
  const { user, logout } = useContext(AuthContext);
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate('/login'); };

  // Role-based nav items
  const navItems = {
    student: [
      { to: '/student',        icon: <FiGrid />,     label: 'Dashboard' },
      { to: '/student/leaves', icon: <FiCalendar />, label: 'Leave Requests' },
    ],
    admin: [
      { to: '/admin',          icon: <FiGrid />,     label: 'Dashboard' },
      { to: '/admin/subjects', icon: <FiBookOpen />, label: 'Subjects' },
      { to: '/admin/timetables',icon: <FiClock />,   label: 'Timetables' },
      { to: '/admin/roster',   icon: <FiUsers />,    label: 'Student Roster' },
      { to: '/admin/leaves',   icon: <FiCalendar />, label: 'Leave Requests' },
      { to: '/admin/analytics', icon: <FiActivity />, label: 'Analytics' },
    ],
    superadmin: [
      { to: '/superadmin',     icon: <FiShield />,   label: 'Control Panel' },
      { to: '/admin',          icon: <FiGrid />,     label: 'Admin Dashboard' },
      { to: '/admin/subjects', icon: <FiBookOpen />, label: 'Subjects' },
      { to: '/admin/timetables',icon: <FiClock />,   label: 'Timetables' },
      { to: '/admin/roster',   icon: <FiUsers />,    label: 'Student Roster' },
      { to: '/admin/leaves',   icon: <FiCalendar />, label: 'Leave Requests' },
      { to: '/admin/analytics', icon: <FiActivity />, label: 'Analytics' },
    ],
  };

  const items = navItems[user?.role] || [];

  return (
    <div className="d-flex" style={{ backgroundColor: 'var(--secondary-bg)', minHeight: '100vh' }}>
      {/* Sidebar */}
      <div className="sidebar d-flex flex-column" style={{ width: '250px', minHeight: '100vh' }}>
        {/* Logo */}
        <div className="px-3 mb-4">
          <h4 className="fw-bolder text-primary mb-0">Smart Attendance</h4>
          <small className="text-muted" style={{fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
            {user?.role} portal
          </small>
        </div>

        {/* Navigation */}
        <div className="nav flex-column mb-auto gap-1">
          <span className="nav-link text-muted px-3 pb-1" style={{fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em'}}>
            Navigation
          </span>
          {items.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `nav-link d-flex align-items-center gap-2 px-3 py-2 rounded-2 mx-2 ${isActive ? 'active' : ''}`
              }
            >
              {item.icon} {item.label}
            </NavLink>
          ))}

          {/* Profile section */}
          <span className="nav-link text-muted px-3 pb-1 mt-3" style={{fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em'}}>
            Account
          </span>
          <div className="nav-link d-flex align-items-center gap-2 px-3 py-2 mx-2">
            <div className="rounded-circle bg-primary bg-opacity-10 d-flex align-items-center justify-content-center text-primary fw-bold"
              style={{width: '32px', height: '32px', fontSize: '0.85rem', flexShrink: 0}}>
              {(user?.name || user?.email || '?')[0].toUpperCase()}
            </div>
            <div style={{overflow: 'hidden'}}>
              <div className="fw-bold text-dark" style={{fontSize: '0.85rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>
                {user?.name || user?.email}
              </div>
              <div className="text-muted" style={{fontSize: '0.72rem'}}>{user?.role}</div>
            </div>
          </div>
        </div>

        {/* Logout */}
        <div className="mt-auto p-3">
          <button className="btn btn-light w-100 text-start text-danger border-0" onClick={handleLogout}>
            <FiLogOut className="me-2" /> Logout
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-grow-1 p-5" style={{overflowY: 'auto'}}>
        <Outlet />
      </div>
    </div>
  );
};
