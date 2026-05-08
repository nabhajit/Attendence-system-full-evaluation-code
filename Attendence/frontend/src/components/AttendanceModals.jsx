import { useState, useRef, useEffect } from 'react';
import api from '../services/api';
import { FiUpload, FiCamera, FiX, FiCheckCircle, FiLoader, FiVideo } from 'react-icons/fi';

export const VideoUploadModal = ({ show, onClose, onSuccess }) => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');

  if (!show) return null;

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setMessage('Uploading video... please wait.');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/admin/video/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setMessage('✅ ' + res.data.message);
      setTimeout(() => {
        onSuccess(res.data);
        setFile(null);
        setMessage('');
        setUploading(false);
      }, 2000);
    } catch (err) {
      setMessage('❌ ' + (err.response?.data?.detail || 'Upload failed.'));
      setUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content p-4" onClick={e => e.stopPropagation()}>
        <div className="d-flex justify-content-between mb-4">
          <h4 className="fw-bold mb-0">Upload Classroom Recording</h4>
          <button className="btn-close" onClick={onClose}></button>
        </div>
        
        <form onSubmit={handleUpload}>
          <div className="upload-dropzone mb-4 text-center p-5 border-dashed rounded-4 bg-light">
            <FiVideo size={48} className="text-primary mb-3" />
            <p className="mb-0 text-muted">Select an .mp4 or .avi file</p>
            <input 
              type="file" 
              className="mt-3 form-control" 
              accept=".mp4,.avi,.mov"
              onChange={e => setFile(e.target.files[0])}
              required
            />
          </div>

          {message && (
            <div className={`alert ${message.includes('✅') ? 'alert-success' : 'alert-info'} mb-4 py-2`}>
              {message}
            </div>
          )}

          <div className="d-flex gap-2">
            <button type="button" className="btn btn-light flex-grow-1" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary flex-grow-1" disabled={uploading || !file}>
              {uploading ? <><FiLoader className="spinner-spin me-2" /> Processing...</> : 'Start Processing'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export const LiveScannerModal = ({ show, onClose }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [isScanning, setIsScanning] = useState(false);
  const [recognized, setRecognized] = useState([]);
  const [status, setStatus] = useState('Initializing...');
  const [cameraError, setCameraError] = useState(null);

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
    setIsScanning(false);
    setCameraError(null);
  };

  const startCamera = async () => {
    setCameraError(null);
    setStatus('Opening camera...');
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 1280, height: 720 } });
      streamRef.current = s;
      if (videoRef.current) {
        videoRef.current.srcObject = s;
        await videoRef.current.play();
      }
      setIsScanning(true);
      setStatus('🔍 Searching for faces...');
    } catch (err) {
      console.error("Camera access error", err);
      setCameraError('Camera access denied. Please check permissions.');
      setStatus('❌ Camera Error');
    }
  };

  useEffect(() => {
    if (show) startCamera();
    else stopCamera();
    return () => stopCamera();
  }, [show]);

  const captureFrame = async () => {
    if (!videoRef.current || !canvasRef.current || !isScanning) return;
    const canvas = canvasRef.current;
    const video = videoRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

    canvas.toBlob(async (blob) => {
      if (!blob) return;
      const formData = new FormData();
      formData.append('file', blob, 'frame.jpg');
      try {
        const res = await api.post('/admin/face/recognize', formData);
        if (res.data.match) {
          const newMatch = {
            name: res.data.name,
            roll: res.data.roll,
            time: new Date().toLocaleTimeString(),
            logged: res.data.attendance_logged
          };
          setRecognized(prev => {
            if (prev.find(p => p.roll === newMatch.roll)) return prev;
            return [newMatch, ...prev].slice(0, 5);
          });
          setStatus(`✅ Recognized: ${newMatch.name}`);
        } else {
          setStatus(res.data.message || '🔍 Searching...');
        }
      } catch (err) {
        setStatus('⚠️ Recognition Server Busy');
      }
    }, 'image/jpeg', 0.7);
  };

  useEffect(() => {
    let interval = null;
    if (isScanning) interval = setInterval(captureFrame, 2800);
    return () => clearInterval(interval);
  }, [isScanning]);

  if (!show) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content p-4" style={{ maxWidth: '800px' }} onClick={e => e.stopPropagation()}>
        <div className="d-flex justify-content-between mb-4">
          <h4 className="fw-bold mb-0">Live Attendance Scan</h4>
          <button className="btn-close" onClick={onClose}></button>
        </div>

        <div className="row">
          <div className="col-md-7">
            <div className="webcam-container bg-dark rounded-4 overflow-hidden position-relative mb-3" style={{ aspectRatio: '4/3' }}>
              <video ref={videoRef} autoPlay playsInline muted className="w-100 h-100 object-fit-cover" />
              <canvas ref={canvasRef} className="d-none" />
              <div className="position-absolute bottom-0 start-0 end-0 p-3 bg-dark bg-opacity-50 text-white text-center">
                <small className="fw-bold">{status}</small>
              </div>
            </div>
          </div>
          <div className="col-md-5">
            <h6 className="fw-bold text-muted small mb-3">RECOGNIZED STUDENTS</h6>
            <div className="recognition-list" style={{ minHeight: '250px' }}>
              {recognized.length > 0 ? recognized.map((p, i) => (
                <div key={i} className="card p-3 border-0 bg-light mb-2 animate-fade-in">
                  <div className="d-flex align-items-center gap-2">
                    <FiCheckCircle className="text-success" />
                    <div>
                      <p className="mb-0 fw-bold small">{p.name}</p>
                      <p className="mb-0 text-muted" style={{ fontSize: '10px' }}>{p.roll} • {p.time}</p>
                    </div>
                  </div>
                </div>
              )) : (
                <div className="text-center py-5 text-muted">
                  <FiLoader className="spinner-spin d-block mx-auto mb-2" size={24} />
                  <small>Point camera at student face</small>
                </div>
              )}
            </div>
            <button className="btn btn-primary w-100 mt-3 rounded-pill" onClick={onClose}>Stop & Finish</button>
          </div>
        </div>
      </div>
    </div>
  );
};
