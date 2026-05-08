import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// Request interceptor: Attach JWT token globally
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Global error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      // Eject user on Auth expiration/violation
      console.warn("Auth exception triggered - enforcing logout.");
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      localStorage.removeItem('name');
      // Simple reload bypasses complex router navigation contexts
      window.location.href = '/login'; 
    }
    return Promise.reject(error);
  }
);

export default api;
