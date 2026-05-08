import { useState, useEffect } from 'react';
import api from '../services/api';
import { FiBarChart2, FiPieChart, FiActivity } from 'react-icons/fi';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const COLORS = ['#22c55e', '#ef4444', '#f97316', '#4f46e5'];

export const AnalyticsPage = () => {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const stuRes = await api.get('/admin/students');
        setStudents(stuRes.data);
      } catch (err) {
        console.error('Error fetching admin data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary" /></div>;

  // Process data for charts
  const presentCount = students.filter(s => s.percentage >= 75).length;
  const defaulterCount = students.length - presentCount;
  const pieData = [
    { name: 'Good Standing (>=75%)', value: presentCount },
    { name: 'Defaulters (<75%)', value: defaulterCount }
  ];

  // Distribute students by attendance buckets
  const buckets = { '0-25%': 0, '26-50%': 0, '51-75%': 0, '76-100%': 0 };
  students.forEach(s => {
    if (s.percentage <= 25) buckets['0-25%']++;
    else if (s.percentage <= 50) buckets['26-50%']++;
    else if (s.percentage <= 75) buckets['51-75%']++;
    else buckets['76-100%']++;
  });
  
  const barData = Object.keys(buckets).map(k => ({ name: k, count: buckets[k] }));

  return (
    <div>
      <h2 className="fw-bold mb-4 text-primary d-flex align-items-center">
        <FiActivity className="me-2" /> AI Attendance Analytics
      </h2>

      <div className="row mb-4">
        {/* Pie Chart */}
        <div className="col-md-6 mb-3">
          <div className="card p-4 border-0 h-100 shadow-sm">
            <h5 className="fw-bold mb-4 d-flex align-items-center text-dark">
              <FiPieChart className="me-2 text-warning"/> Class Distribution
            </h5>
            <div style={{ width: '100%', height: 300 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={pieData}
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Bar Chart */}
        <div className="col-md-6 mb-3">
          <div className="card p-4 border-0 h-100 shadow-sm">
            <h5 className="fw-bold mb-4 d-flex align-items-center text-dark">
              <FiBarChart2 className="me-2 text-primary"/> Attendance Buckets
            </h5>
            <div style={{ width: '100%', height: 300 }}>
              <ResponsiveContainer>
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb"/>
                  <XAxis dataKey="name" stroke="#6b7280" fontSize={12} tickLine={false} />
                  <YAxis stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{fill: 'transparent'}} />
                  <Bar dataKey="count" fill="#4f46e5" radius={[4, 4, 0, 0]} barSize={40} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
