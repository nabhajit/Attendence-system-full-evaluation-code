import { useState, useRef, useCallback, useEffect } from 'react';
import api from '../services/api';
import { FiCamera, FiUser, FiCheckCircle, FiTrash2, FiUpload, FiBook } from 'react-icons/fi';

const TARGET_IMAGES = 20;

export const FaceRegistrationModal = ({ show, onClose, onSuccess }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const [step, setStep] = useState('form');
  const [studentInfo, setStudentInfo] = useState({ name: '', roll_number: '', student_class: '', contact: '', course: '' });
  const [capturedImages, setCapturedImages] = useState([]);
  const [isCapturing, setIsCapturing] = useState(false);
  const [error, setError] = useState('');
  const [uploadProgress, setUploadProgress] = useState('');
  const [result, setResult] = useState(null);

  const startCamera = async () => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' } });
      streamRef.current = stream;
      setStep('camera');
    } catch (err) {
      setError('Could not access camera. Please allow browser camera permissions.');
    }
  };

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
  }, []);

  // KEY FIX: Attach stream to video element AFTER React renders the <video> tag
  useEffect(() => {
    if (step === 'camera' && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current.play().catch(e => console.warn("Video play error:", e));
    }
  }, [step]);

  useEffect(() => {
    if (!show) {
      stopCamera();
      setStep('form');
      setCapturedImages([]);
      setError('');
      setResult(null);
    }
    return () => stopCamera();
  }, [show, stopCamera]);

  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) setCapturedImages(prev => [...prev, blob]);
    }, 'image/jpeg', 0.85);
  }, []);

  useEffect(() => {
    if (isCapturing && capturedImages.length < TARGET_IMAGES) {
      const timer = setTimeout(captureFrame, 1500);
      return () => clearTimeout(timer);
    }
    if (isCapturing && capturedImages.length >= TARGET_IMAGES) setIsCapturing(false);
  }, [isCapturing, capturedImages.length, captureFrame]);

  const handleStartCapture = () => { setCapturedImages([]); setIsCapturing(true); };

  const handleSubmit = async () => {
    if (capturedImages.length < 5) { setError('Please capture at least 5 images first.'); return; }
    setStep('uploading');
    setUploadProgress('Uploading & computing FaceNet embeddings...');
    stopCamera();

    try {
      const formData = new FormData();
      formData.append('name', studentInfo.name);
      formData.append('roll_number', studentInfo.roll_number);
      formData.append('student_class', studentInfo.student_class || 'Unknown');
      formData.append('contact', studentInfo.contact || 'N/A');
      formData.append('course', studentInfo.course || '');
      capturedImages.forEach((blob, i) => formData.append('images', blob, `face_${i + 1}.jpg`));

      const res = await api.post('/admin/face/register', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
      setStep('done');
      onSuccess?.(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
      setStep('camera');
      startCamera();
    }
  };

  if (!show) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1050,
      backgroundColor: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div className="card shadow-lg" style={{ width: '680px', maxWidth: '96vw', borderRadius: '20px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="card-header d-flex justify-content-between align-items-center border-0">
          <h5 className="fw-bold mb-0 d-flex align-items-center"><FiCamera className="me-2 text-primary" /> Register Student Face</h5>
          <button className="btn btn-sm btn-light rounded-circle" onClick={onClose}>✕</button>
        </div>

        <div className="card-body px-4 pb-4">
          {error && <div className="alert alert-danger small border-0">{error}</div>}

          {/* STEP 1 - FORM */}
          {step === 'form' && (
            <div>
              <p className="text-muted mb-4">Fill in the student details then we'll open your camera to capture face samples.</p>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label text-muted small fw-bold">Full Name *</label>
                  <input className="form-control bg-light border-0" required value={studentInfo.name} onChange={e => setStudentInfo({...studentInfo, name: e.target.value})} />
                </div>
                <div className="col-md-6">
                  <label className="form-label text-muted small fw-bold d-flex justify-content-between">
                    <span>Roll Number *</span>
                    <span className="text-primary" style={{fontSize:'0.7rem'}}>* CRITICAL - Must match web account *</span>
                  </label>
                  <input className="form-control bg-light border-0 border-start border-3 border-primary" required value={studentInfo.roll_number} onChange={e => setStudentInfo({...studentInfo, roll_number: e.target.value})} />
                </div>
                <div className="col-md-6">
                  <label className="form-label text-muted small fw-bold d-flex align-items-center">
                    <FiBook className="me-1"/> Course Enrolled In *
                  </label>
                  <input className="form-control bg-light border-0" placeholder="e.g. B.Tech CSE / BCA / MCA" required value={studentInfo.course} onChange={e => setStudentInfo({...studentInfo, course: e.target.value})} />
                </div>
                <div className="col-md-6">
                  <label className="form-label text-muted small fw-bold">Class / Section</label>
                  <input className="form-control bg-light border-0" placeholder="e.g. 12-A" value={studentInfo.student_class} onChange={e => setStudentInfo({...studentInfo, student_class: e.target.value})} />
                </div>
                <div className="col-md-12">
                  <label className="form-label text-muted small fw-bold">Contact Number</label>
                  <input className="form-control bg-light border-0" placeholder="e.g. +91 9876543210" value={studentInfo.contact} onChange={e => setStudentInfo({...studentInfo, contact: e.target.value})} />
                </div>
              </div>
              <button
                className="btn btn-primary w-100 py-3 mt-4 fw-bold rounded-3"
                onClick={() => {
                  if (!studentInfo.name.trim() || !studentInfo.roll_number.trim() || !studentInfo.course.trim()) {
                    setError('Name, Roll Number, and Course are required!');
                    return;
                  }
                  setError('');
                  startCamera();
                }}
              >
                <FiCamera className="me-2"/> Open Camera & Start Registration
              </button>
            </div>
          )}

          {/* STEP 2 - CAMERA */}
          {step === 'camera' && (
            <div>
              <div className="position-relative mb-3" style={{ borderRadius: '12px', overflow: 'hidden', backgroundColor: '#000' }}>
                <video ref={videoRef} autoPlay playsInline muted
                  style={{ width: '100%', transform: 'scaleX(-1)', display: 'block', maxHeight: '360px', objectFit: 'cover' }} />
                <div className="position-absolute top-0 start-0 m-3 bg-dark bg-opacity-75 rounded-3 px-3 py-2 text-white small fw-bold">
                  📸 {capturedImages.length} / {TARGET_IMAGES} captured
                </div>
                {isCapturing && (
                  <div className="position-absolute bottom-0 start-0 end-0 m-3">
                    <div className="progress" style={{height: '8px', borderRadius: '4px'}}>
                      <div className="progress-bar bg-success" style={{width: `${(capturedImages.length/TARGET_IMAGES)*100}%`, transition: 'width 0.3s'}} />
                    </div>
                  </div>
                )}
              </div>
              <canvas ref={canvasRef} style={{ display: 'none' }} />
              <div className="alert py-2 mb-3 border-0" style={{backgroundColor: '#e8f4fd', fontSize: '0.85rem'}}>
                <FiUser className="me-2 text-primary"/> <strong>{studentInfo.name}</strong> &nbsp;|&nbsp;
                Roll: <strong>{studentInfo.roll_number}</strong> &nbsp;|&nbsp;
                Course: <strong>{studentInfo.course}</strong>
              </div>
              {capturedImages.length < TARGET_IMAGES ? (
                <button className={`btn w-100 py-3 fw-bold rounded-3 ${isCapturing ? 'btn-warning' : 'btn-primary'}`}
                  onClick={isCapturing ? () => setIsCapturing(false) : handleStartCapture}>
                  {isCapturing ? '⏸ Pause Auto-Capture' : '▶ Start Auto-Capture'}
                </button>
              ) : (
                <div className="d-flex gap-2">
                  <button className="btn btn-outline-secondary flex-fill py-3" onClick={handleStartCapture}><FiTrash2 className="me-2"/> Retake</button>
                  <button className="btn btn-success flex-fill py-3 fw-bold" onClick={handleSubmit}><FiUpload className="me-2"/> Submit & Register (FaceNet AI)</button>
                </div>
              )}
              {capturedImages.length > 5 && capturedImages.length < TARGET_IMAGES && !isCapturing && (
                <div className="mt-2 text-center">
                  <button className="btn btn-success fw-bold px-5 py-2" onClick={handleSubmit}>✓ Use {capturedImages.length} Images & Submit</button>
                </div>
              )}
            </div>
          )}

          {/* STEP 3 - UPLOADING */}
          {step === 'uploading' && (
            <div className="text-center py-5">
              <div className="spinner-border text-primary mb-4" style={{width: '3rem', height: '3rem'}}/>
              <h5 className="fw-bold">Processing & Uploading...</h5>
              <p className="text-muted">{uploadProgress}</p>
              <p className="text-muted small">This may take up to 30 seconds while the AI computes facial embeddings.</p>
            </div>
          )}

          {/* STEP 4 - DONE */}
          {step === 'done' && result && (
            <div className="text-center py-4">
              <FiCheckCircle size={60} className="text-success mb-3"/>
              <h4 className="fw-bold">Registration Complete! 🎉</h4>
              <p className="text-muted">The student is now part of the Face Attendance System.</p>
              <div className="card bg-light border-0 p-3 text-start mb-4">
                <div><strong>Name:</strong> {studentInfo.name}</div>
                <div><strong>Roll Number:</strong> {studentInfo.roll_number}</div>
                <div><strong>Course:</strong> {studentInfo.course}</div>
                <div><strong>Images Processed:</strong> {result.images_processed}</div>
              </div>
              <button className="btn btn-primary px-5 py-2 rounded-3" onClick={onClose}>Close</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
