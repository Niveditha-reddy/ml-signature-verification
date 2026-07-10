import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';
import './Dashboard.css';

function Dashboard() {
    const navigate = useNavigate();
    const [user, setUser] = useState(null);
    const [comparisonImage, setComparisonImage] = useState(null);
    const [comparisonPreview, setComparisonPreview] = useState(null);
    const [verificationResult, setVerificationResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        const token = localStorage.getItem('signatureguard-token');
        const userData = localStorage.getItem('signatureguard-user');

        if (!token || !userData) {
            navigate('/');
            return;
        }

        setUser(JSON.parse(userData));
    }, [navigate]);

    const handleLogout = () => {
        localStorage.removeItem('signatureguard-token');
        localStorage.removeItem('signatureguard-user');
        navigate('/');
    };

    const handleImageChange = (e) => {
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
            setComparisonImage(file);
            setError('');
            setVerificationResult(null);

            const reader = new FileReader();
            reader.onloadend = () => {
                setComparisonPreview(reader.result);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleVerify = async () => {
        if (!comparisonImage) {
            setError('Please upload a signature to verify');
            return;
        }

        if (!user.signatureUrl) {
            setError('No original signature found. Please register again with a signature.');
            return;
        }

        setLoading(true);
        setError('');
        setVerificationResult(null);

        // Helper: wrap a promise with a timeout
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

        // Upload a single file to the Space and return its server-side path
        const uploadFile = async (blob, filename) => {
            const formData = new FormData();
            formData.append("files", blob, filename);

            const res = await fetch(`${SPACE_URL}/gradio_api/upload`, {
                method: "POST",
                body: formData,
                credentials: "omit"
            });

            if (!res.ok) {
                throw new Error(`Upload failed with status ${res.status}`);
            }

            const paths = await res.json();
            return paths[0];
        };

        // Submit the job and return the event_id
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

        // Stream the SSE result for the given event_id
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
            // Fetch the original signature image from Cloudinary
            const originalResponse = await fetch(user.signatureUrl);
            const originalBlob = await originalResponse.blob();

            // Upload both images (60s timeout each)
            const [path1, path2] = await withTimeout(
                Promise.all([
                    uploadFile(originalBlob, "original.png"),
                    uploadFile(comparisonImage, comparisonImage.name || "comparison.png")
                ]),
                60000
            );

            // Submit the job
            const eventId = await withTimeout(submitJob(path1, path2), 60000);

            // Stream the result
            const verificationText = await withTimeout(getResult(eventId), 60000);

            processResult(verificationText);

        } catch (err) {
            console.error('Verification error:', err);
            setError('Verification failed. Please try again. ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    const processResult = (verificationText) => {
        // Parse the new output format: "🔍 Similarity Score: 0.xxxx"
        const scoreMatch = verificationText.match(/Similarity Score:\s*([\d.]+)/);

        if (!scoreMatch) {
            setError('Could not parse verification result');
            return;
        }

        const score = parseFloat(scoreMatch[1]);

        // Use personalized threshold from user data (fallback to 0.5 for legacy users)
        const userThreshold = user.threshold !== undefined ? user.threshold : 0.5;
        const isMatch = score > userThreshold;

        // Determine confidence based on how far the score is from threshold
        let confidence = 'Low';
        const diff = Math.abs(score - userThreshold);
        if (diff > 0.2) {
            confidence = 'High';
        } else if (diff > 0.1) {
            confidence = 'Medium';
        }

        setVerificationResult({
            match: isMatch,
            score: score,
            threshold: userThreshold,
            confidence: confidence,
            message: isMatch ? 'Signatures are from the same person!' : 'Signatures are from different persons!'
        });
    };

    // Helper function to convert blob to base64
    const blobToBase64 = (blob) => {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    };

    const clearComparison = () => {
        setComparisonImage(null);
        setComparisonPreview(null);
        setVerificationResult(null);
        setError('');
    };

    if (!user) {
        return null;
    }

    return (
        <div className="dashboard-page">
            <ThemeToggle />

            <header className="dashboard-header">
                <div className="logo">
                    <span className="logo-icon">🛡️</span>
                    <h1>SignatureGuard</h1>
                </div>

                <div className="user-info">
                    <span className="user-name">Welcome, {user.name}</span>
                    <button onClick={handleLogout} className="logout-btn">
                        Logout
                    </button>
                </div>
            </header>

            <main className="dashboard-main">
                <div className="dashboard-content">
                    <h2 className="page-title">Signature Verification</h2>
                    <p className="page-subtitle">Compare a signature against your registered original</p>

                    <div className="verification-container">
                        {/* Original Signature */}
                        <div className="signature-card original">
                            <h3>📝 Your Registered Signature</h3>
                            <div className="signature-display">
                                {user.signatureUrl ? (
                                    <img
                                        src={user.signatureUrl}
                                        alt="Your registered signature"
                                    />
                                ) : (
                                    <p className="no-signature">No signature on file</p>
                                )}
                            </div>
                            <span className="card-label">Original</span>
                        </div>

                        {/* VS Separator */}
                        <div className="vs-separator">
                            <span>VS</span>
                        </div>

                        {/* Comparison Signature */}
                        <div className="signature-card comparison">
                            <h3>🔍 Upload to Verify</h3>
                            <div className="signature-display">
                                {comparisonPreview ? (
                                    <>
                                        <img
                                            src={comparisonPreview}
                                            alt="Signature to verify"
                                        />
                                        <button
                                            className="clear-btn"
                                            onClick={clearComparison}
                                            aria-label="Clear uploaded image"
                                        >
                                            ✕
                                        </button>
                                    </>
                                ) : (
                                    <div className="upload-area">
                                        <input
                                            type="file"
                                            id="comparison-upload"
                                            accept="image/*"
                                            onChange={handleImageChange}
                                            className="file-input"
                                        />
                                        <label htmlFor="comparison-upload" className="upload-label">
                                            <span className="upload-icon">📤</span>
                                            <span>Click to upload</span>
                                            <span className="upload-hint">PNG, JPG up to 5MB</span>
                                        </label>
                                    </div>
                                )}
                            </div>
                            <span className="card-label">To Verify</span>
                        </div>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="error-message">
                            <span>⚠️</span> {error}
                        </div>
                    )}

                    {/* Verify Button */}
                    <button
                        className="verify-btn"
                        onClick={handleVerify}
                        disabled={!comparisonImage || loading}
                    >
                        {loading ? (
                            <>
                                <span className="spinner"></span>
                                Analyzing...
                            </>
                        ) : (
                            <>
                                🔐 Verify Signature
                            </>
                        )}
                    </button>

                    {/* Verification Result */}
                    {verificationResult && (
                        <div className={`result-card ${verificationResult.match ? 'match' : 'no-match'}`}>
                            <div className="result-icon">
                                {verificationResult.match ? '✅' : '❌'}
                            </div>
                            <div className="result-content">
                                <h4>{verificationResult.match ? 'Signatures Match!' : 'Signatures Do Not Match'}</h4>
                                <p className="score">Similarity Score: {verificationResult.score.toFixed(4)}</p>
                                <p className="threshold">Your Threshold: {verificationResult.threshold?.toFixed(4) || '0.5000'}</p>
                                <p className="confidence">Confidence: {verificationResult.confidence || 'Medium'}</p>
                                <p className="result-message">{verificationResult.message}</p>
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}

export default Dashboard;