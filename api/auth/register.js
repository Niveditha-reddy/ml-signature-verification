import connectDB from '../lib/mongodb.js';
import User from '../models/User.js';
import { hashPassword, generateToken } from '../lib/auth.js';
import { uploadImage } from '../lib/cloudinary.js';

export default async function handler(req, res) {
    // Only allow POST method
    if (req.method !== 'POST') {
        return res.status(405).json({ message: 'Method not allowed' });
    }

    try {
        await connectDB();

        const { name, email, password, signature, threshold } = req.body;

        // Validation
        if (!name || !email || !password) {
            return res.status(400).json({ message: 'Please provide all required fields' });
        }

        if (!signature) {
            return res.status(400).json({ message: 'Please upload your signature' });
        }

        if (threshold === undefined || threshold === null) {
            return res.status(400).json({ message: 'Threshold calculation required' });
        }

        if (password.length < 6) {
            return res.status(400).json({ message: 'Password must be at least 6 characters' });
        }

        // Check if user already exists
        const existingUser = await User.findOne({ email: email.toLowerCase() });
        if (existingUser) {
            return res.status(400).json({ message: 'User with this email already exists' });
        }

        // Debug: Log Cloudinary env vars (partial)
        console.log('Cloudinary config check:', {
            hasCloudName: !!process.env.CLOUDINARY_CLOUD_NAME,
            hasApiKey: !!process.env.CLOUDINARY_API_KEY,
            hasApiSecret: !!process.env.CLOUDINARY_API_SECRET,
            signatureLength: signature ? signature.length : 0
        });

        // Upload signature to Cloudinary
        let signatureUrl, signaturePublicId;
        try {
            const uploadResult = await uploadImage(signature);
            signatureUrl = uploadResult.url;
            signaturePublicId = uploadResult.publicId;
            console.log('Cloudinary upload success:', signatureUrl);
        } catch (uploadError) {
            console.error('Cloudinary upload failed:', uploadError);
            return res.status(500).json({
                message: 'Failed to upload signature. Please try again.',
                error: uploadError.message
            });
        }

        if (!signatureUrl) {
            return res.status(500).json({ message: 'Signature upload failed - no URL returned' });
        }

        // Hash password and create user
        const hashedPassword = await hashPassword(password);
        const user = await User.create({
            name,
            email: email.toLowerCase(),
            password: hashedPassword,
            signatureUrl,
            signaturePublicId,
            threshold
        });

        // Generate JWT token
        const token = generateToken(user._id);

        res.status(201).json({
            message: 'User registered successfully',
            token,
            user: {
                id: user._id,
                name: user.name,
                email: user.email,
                signatureUrl: user.signatureUrl,
                threshold: user.threshold
            }
        });
    } catch (error) {
        console.error('Registration error:', error);
        res.status(500).json({ message: 'Server error. Please try again.' });
    }
}
