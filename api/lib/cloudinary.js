import { v2 as cloudinary } from 'cloudinary';

cloudinary.config({
    cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
    api_key: process.env.CLOUDINARY_API_KEY,
    api_secret: process.env.CLOUDINARY_API_SECRET
});

/**
 * Upload an image to Cloudinary
 * @param {string} imageData - Base64 encoded image or image URL
 * @param {string} folder - Folder to store the image in
 * @returns {Promise<{url: string, publicId: string}>}
 */
export async function uploadImage(imageData, folder = 'signatures') {
    try {
        const result = await cloudinary.uploader.upload(imageData, {
            folder: folder,
            resource_type: 'image',
            quality: 100
        });

        return {
            url: result.secure_url,
            publicId: result.public_id
        };
    } catch (error) {
        console.error('Cloudinary upload error:', error);
        throw new Error('Failed to upload image');
    }
}

/**
 * Delete an image from Cloudinary
 * @param {string} publicId - The public ID of the image to delete
 */
export async function deleteImage(publicId) {
    try {
        await cloudinary.uploader.destroy(publicId);
    } catch (error) {
        console.error('Cloudinary delete error:', error);
    }
}

export default cloudinary;
