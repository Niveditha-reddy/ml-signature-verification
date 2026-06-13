import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Client } from '@gradio/client';
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

        try {
            // Fetch the original signature image from Cloudinary
            const originalResponse = await fetch(user.signatureUrl);
            const originalBlob = await originalResponse.blob();

            // Connect to Hugging Face Space using Gradio client
            const client = await Client.connect("sunny4203/signature-verification");

            // Call the predict function with both images
            const result = await client.predict("/compute_similarity", {
                image1: originalBlob,
                image2: comparisonImage
            });

            // Parse the result
            const verificationText = result.data[0];
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
