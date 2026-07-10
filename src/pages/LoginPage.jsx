import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';
import './LoginPage.css';

function LoginPage() {
    const navigate = useNavigate();
    const [isLogin, setIsLogin] = useState(true);
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        password: ''
    });
    const [signatureFile, setSignatureFile] = useState(null);
    const [signaturePreview, setSignaturePreview] = useState(null);
    const [signatureFile2, setSignatureFile2] = useState(null);
    const [signaturePreview2, setSignaturePreview2] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
        setError('');
    };

    const handleSignatureChange = (e, isSecond = false) => {
        const file = e.target.files[0];
        if (file) {
            if (!file.type.startsWith('image/')) {
                setError('Please upload an image file');
                return;
            }
            if (file.size > 5 * 1024 * 1024) {
                setError('Image must be less than 5MB');
                return;
            }

            if (isSecond) {
                setSignatureFile2(file);
            } else {
                setSignatureFile(file);
            }
            setError('');

            const reader = new FileReader();
            reader.onloadend = () => {
                if (isSecond) {
                    setSignaturePreview2(reader.result);
                } else {
                    setSignaturePreview(reader.result);
                }
            };
            reader.readAsDataURL(file);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            if (isLogin) {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: formData.email,
                        password: formData.password
                    })
                });

                const data = await response.json();
                if (!response.ok) throw new Error(data.message || 'Login failed');

                localStorage.setItem('signatureguard-token', data.token);
                localStorage.setItem('signatureguard-user', JSON.stringify(data.user));
                navigate('/dashboard');
            } else {
                if (!signatureFile || !signatureFile2) {
                    throw new Error('Please upload both signature samples');
                }

                setError('');

                const withTimeout = (promise, ms) => {
                    let timer;
                    return Promise.race([
                        promise,
                        new Promise((_, reject) => {
                            timer = setTimeout(() => reject(new Error(
                                'The signature verification service is currently unavailable (timed out). Please try again in a few minutes.'
                            )), ms);
                        })
                    ]).finally(() => clearTimeout(timer));
                };

                const SPACE_URL = "https://sunny4203-signature-verification.hf.space";

                const uploadFile = async (blob, filename) => {
                    const formDataUpload = new FormData();
                    formDataUpload.append("files", blob, filename);

                    const res = await fetch(`${SPACE_URL}/gradio_api/upload`, {
                        method: "POST",
                        body: formDataUpload,
                        credentials: "omit"
                    });

                    if (!res.ok) {
                        throw new Error(`Upload failed with status ${res.status}`);
                    }

                    const paths = await res.json();
                    return paths[0];
                };

                const submitJob = async (path1, path2) => {
                    const res = await fetch(`${SPACE_URL}/gradio_api/call/compute_similarity`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        credentials: "omit",
                        body: JSON.stringify({
                            data: [
                                { path: path1, meta: { _type: "gradio.FileData" } },
                                { path: path2, meta: { _type: "gradio.FileData" } }
                            ]
                        })
                    });

                    if (!res.ok) {
                        throw new Error(`Job submission failed with status ${res.status}`);
                    }

                    const { event_id } = await res.json();
                    return event_id;
                };

                const getResult = (eventId) => {
                    return new Promise((resolve, reject) => {
                        const es = new EventSource(
                            `${SPACE_URL}/gradio_api/call/compute_similarity/${eventId}`
                        );

                        es.addEventListener("complete", (event) => {
                            es.close();
                            try {
                                const parsed = JSON.parse(event.data);
                                resolve(parsed[0]);
                            } catch (e) {
                                reject(new Error("Could not parse verification result"));
                            }
                        });

                        es.addEventListener("error", () => {
                            es.close();
                            reject(new Error("The verification service returned an error"));
                        });

                        es.onerror = () => {
                            es.close();
                            reject(new Error("Connection to the verification service was lost"));
                        };
                    });
                };

                try {
                    const [path1, path2] = await withTimeout(
                        Promise.all([
                            uploadFile(signatureFile, signatureFile.name || "signature1.png"),
                            uploadFile(signatureFile2, signatureFile2.name || "signature2.png")
                        ]),
                        60000
                    );

                    const eventId = await withTimeout(submitJob(path1, path2), 60000);

                    const resultText = await withTimeout(getResult(eventId), 60000);

                    const scoreMatch = resultText.match(/Similarity Score:\s*([\d.]+)/);
                    if (!scoreMatch) {
                        throw new Error('Could not calculate threshold. Please try again.');
                    }

                    const similarityScore = parseFloat(scoreMatch[1]);
                    const threshold = similarityScore - 0.03;

                    const base64 = await new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onloadend = () => resolve(reader.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(signatureFile);
                    });

                    const response = await fetch('/api/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ...formData,
                            signature: base64,
                            threshold: threshold
                        })
                    });

                    const data = await response.json();
                    if (!response.ok) throw new Error(data.message || 'Registration failed');

                    localStorage.setItem('signatureguard-token', data.token);
                    localStorage.setItem('signatureguard-user', JSON.stringify(data.user));
                    navigate('/dashboard');
                } catch (err) {
                    setError(err.message);
                } finally {
                    setLoading(false);
                }
                return;
            }
        } catch (err) {
            setError(err.message);
            setLoading(false);
        } finally {
            if (isLogin) setLoading(false);
        }
    };

    const toggleMode = () => {
        setIsLogin(!isLogin);
        setError('');
        setFormData({ name: '', email: '', password: '' });
        setSignatureFile(null);
        setSignaturePreview(null);
        setSignatureFile2(null);
        setSignaturePreview2(null);
    };

    const removeSignature = (isSecond = false) => {
        if (isSecond) {
            setSignatureFile2(null);
            setSignaturePreview2(null);
        } else {
            setSignatureFile(null);
            setSignaturePreview(null);
        }
    };

    return (
        <div className="login-page">
            <ThemeToggle />

            <div className="login-container">
                <div className="login-card">
                    <div className="login-header">
                        <div className="logo">
                            <span className="logo-icon">🛡️</span>
                            <h1>SignatureGuard</h1>
                        </div>
                        <p className="tagline">Secure Signature Verification System</p>
                    </div>

                    <form onSubmit={handleSubmit} className="login-form">
                        <h2>{isLogin ? 'Welcome Back' : 'Create Account'}</h2>

                        {error && (
                            <div className="error-message">
                                <span>⚠️</span> {error}
                            </div>
                        )}

                        {!isLogin && (
                            <div className="input-group">
                                <label htmlFor="name">Full Name</label>
                                <input
                                    type="text"
                                    id="name"
                                    name="name"
                                    value={formData.name}
                                    onChange={handleChange}
                                    placeholder="John Doe"
                                    required={!isLogin}
                                />
                            </div>
                        )}

                        <div className="input-group">
                            <label htmlFor="email">Email Address</label>
                            <input
                                type="email"
                                id="email"
                                name="email"
                                value={formData.email}
                                onChange={handleChange}
                                placeholder="you@example.com"
                                autoComplete="email"
                                required
                            />
                        </div>

                        <div className="input-group">
                            <label htmlFor="password">Password</label>
                            <div className="password-wrapper">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    id="password"
                                    name="password"
                                    value={formData.password}
                                    onChange={handleChange}
                                    placeholder="••••••••"
                                    autoComplete={isLogin ? 'current-password' : 'new-password'}
                                    required
                                    minLength={6}
                                />
                                <button
                                    type="button"
                                    className="password-toggle"
                                    onClick={() => setShowPassword(!showPassword)}
                                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                                >
                                    {showPassword ? '👁️' : '👁️‍🗨️'}
                                </button>
                            </div>
                        </div>

                        {!isLogin && (
                            <>
                                <div className="input-group">
                                    <label>Signature Sample 1</label>
                                    <p className="input-hint">This will be your reference signature</p>

                                    {signaturePreview ? (
                                        <div className="signature-preview">
                                            <img src={signaturePreview} alt="Signature 1 preview" />
                                            <button
                                                type="button"
                                                className="remove-signature"
                                                onClick={() => removeSignature(false)}
                                                aria-label="Remove signature 1"
                                            >
                                                ✕
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="signature-upload">
                                            <input
                                                type="file"
                                                id="signature1"
                                                accept="image/*"
                                                onChange={(e) => handleSignatureChange(e, false)}
                                                className="file-input"
                                            />
                                            <label htmlFor="signature1" className="file-label">
                                                <span className="upload-icon">📝</span>
                                                <span>Upload Signature 1</span>
                                                <span className="file-hint">PNG, JPG up to 5MB</span>
                                            </label>
                                        </div>
                                    )}
                                </div>

                                <div className="input-group">
                                    <label>Signature Sample 2</label>
                                    <p className="input-hint">Used to calibrate your personal threshold</p>

                                    {signaturePreview2 ? (
                                        <div className="signature-preview">
                                            <img src={signaturePreview2} alt="Signature 2 preview" />
                                            <button
                                                type="button"
                                                className="remove-signature"
                                                onClick={() => removeSignature(true)}
                                                aria-label="Remove signature 2"
                                            >
                                                ✕
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="signature-upload">
                                            <input
                                                type="file"
                                                id="signature2"
                                                accept="image/*"
                                                onChange={(e) => handleSignatureChange(e, true)}
                                                className="file-input"
                                            />
                                            <label htmlFor="signature2" className="file-label">
                                                <span className="upload-icon">📝</span>
                                                <span>Upload Signature 2</span>
                                                <span className="file-hint">PNG, JPG up to 5MB</span>
                                            </label>
                                        </div>
                                    )}
                                </div>
                            </>
                        )}

                        <button
                            type="submit"
                            className="submit-btn"
                            disabled={loading}
                        >
                            {loading ? (
                                <span className="spinner"></span>
                            ) : (
                                isLogin ? 'Sign In' : 'Create Account'
                            )}
                        </button>
                    </form>

                    <div className="toggle-auth">
                        <p>
                            {isLogin ? "Don't have an account?" : "Already have an account?"}
                            <button type="button" onClick={toggleMode}>
                                {isLogin ? 'Sign Up' : 'Sign In'}
                            </button>
                        </p>
                    </div>
                </div>

                <div className="decorative-circle circle-1"></div>
                <div className="decorative-circle circle-2"></div>
                <div className="decorative-circle circle-3"></div>
            </div>
        </div>
    );
}

export default LoginPage;