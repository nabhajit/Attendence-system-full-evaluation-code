import { useState, useEffect } from 'react';
import api from '../services/api';
import { FiUserPlus, FiUsers, FiTrash2 } from 'react-icons/fi';

export const SuperadminDashboard = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newAdmin, setNewAdmin] = useState({ name: '', email: '', password: '' });

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const res = await api.get('/superadmin/users');
      setUsers(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAdmin = async (e) => {
    e.preventDefault();
    try {
      await api.post('/superadmin/admins', newAdmin);
      setNewAdmin({ name: '', email: '', password: '' });
      fetchUsers(); // Refresh list
    } catch (e) {
      alert("Error creating admin: " + (e.response?.data?.detail || e.message));
    }
  };

  const handleDelete = async (userId) => {
    if(!window.confirm("Are you sure you want to permanently delete this user?")) return;
    try {
      await api.delete(`/superadmin/users/${userId}`);
      fetchUsers();
    } catch(e) {
      alert("Error deleting user");
    }
  };

  const handleSuspend = async (userId, currentState) => {
    try {
      await api.patch(`/superadmin/users/${userId}/suspend?is_suspended=${!currentState}`);
      fetchUsers();
    } catch(e) {
      alert("Error updating suspension status");
    }
  };

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary" /></div>;

  return (
    <div>
      <h2 className="fw-bold mb-4">Superadmin Global Control 🌍</h2>

      <div className="row">
        {/* Create Admin Form */}
        <div className="col-md-4 mb-4">
          <div className="card p-4 h-100">
            <h5 className="fw-bold mb-3 d-flex align-items-center">
              <FiUserPlus className="me-2 text-primary"/> Register New Admin
            </h5>
            <form onSubmit={handleCreateAdmin}>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Full Name</label>
                <input type="text" className="form-control" required value={newAdmin.name} onChange={e => setNewAdmin({...newAdmin, name: e.target.value})} />
              </div>
              <div className="mb-3">
                <label className="form-label text-muted small fw-bold">Work Email</label>
                <input type="email" className="form-control" required value={newAdmin.email} onChange={e => setNewAdmin({...newAdmin, email: e.target.value})}/>
              </div>
              <div className="mb-4">
                <label className="form-label text-muted small fw-bold">Temporary Password</label>
                <input type="text" className="form-control" required value={newAdmin.password} onChange={e => setNewAdmin({...newAdmin, password: e.target.value})}/>
              </div>
              <button className="btn btn-primary w-100">Create Admin Account</button>
            </form>
          </div>
        </div>

        {/* Global Users Table */}
        <div className="col-md-8 mb-4">
          <div className="card p-4 h-100">
             <h5 className="fw-bold mb-3 d-flex align-items-center">
              <FiUsers className="me-2 text-primary"/> Global User Roster
            </h5>
            
            <div className="table-responsive">
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, i) => (
                    <tr key={i}>
                      <td className="fw-bold text-dark">{u.email} <br/><span className="text-muted fw-normal small">{u.roll_number || 'N/A'}</span></td>
                      <td>
                        <span className={`badge rounded-pill px-3 py-2 ${
                            u.role === 'superadmin' ? 'bg-primary' : 
                            u.role === 'admin' ? 'bg-warning text-dark' : 'bg-light text-dark border'
                        }`}>
                          {u.role.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <button 
                          className={`btn btn-sm ${u.is_suspended ? 'btn-outline-danger' : 'btn-outline-success'}`}
                          onClick={() => handleSuspend(u._id, u.is_suspended)}
                          disabled={u.role === 'superadmin'}
                        >
                          {u.is_suspended ? 'Suspended' : 'Active'}
                        </button>
                      </td>
                      <td>
                         <button className="btn btn-sm btn-light text-danger" onClick={() => handleDelete(u._id)} disabled={u.role === 'superadmin'}>
                           <FiTrash2 />
                         </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
          </div>
        </div>
      </div>
    </div>
  );
};
