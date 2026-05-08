import { useState, useEffect } from 'react';
import { FiCheckCircle, FiXCircle, FiAlertCircle, FiX } from 'react-icons/fi';

/**
 * Toast notification component.
 * Usage: <Toast message="..." type="success|error|warning" onClose={() => {}} />
 */
export const Toast = ({ message, type = 'success', onClose, duration = 4000 }) => {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onClose]);

  if (!message) return null;

  const config = {
    success: { bg: '#d1fae5', border: '#10b981', text: '#065f46', icon: <FiCheckCircle size={20}/> },
    error:   { bg: '#fee2e2', border: '#ef4444', text: '#7f1d1d', icon: <FiXCircle size={20}/> },
    warning: { bg: '#fef3c7', border: '#f59e0b', text: '#78350f', icon: <FiAlertCircle size={20}/> },
  };

  const { bg, border, text, icon } = config[type] || config.success;

  return (
    <div
      style={{
        position: 'fixed', top: '24px', right: '24px', zIndex: 9999,
        backgroundColor: bg, border: `1.5px solid ${border}`, color: text,
        borderRadius: '12px', padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: '12px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
        animation: 'slideIn 0.3s ease',
        maxWidth: '380px', fontSize: '0.9rem', fontWeight: 500
      }}
    >
      {icon}
      <span className="flex-grow-1">{message}</span>
      <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: text, padding: 0 }}>
        <FiX size={18}/>
      </button>
      <style>{`@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`}</style>
    </div>
  );
};

export const useToast = () => {
  const [toast, setToast] = useState({ message: '', type: 'success' });
  const showToast = (message, type = 'success') => setToast({ message, type });
  const closeToast = () => setToast({ message: '', type: 'success' });
  return { toast, showToast, closeToast };
};
