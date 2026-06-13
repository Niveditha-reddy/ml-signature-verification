"""
Inference script for Signature Verification
Used after training to make predictions on new signature pairs
"""
import os
import torch
from PIL import Image
from torchvision import transforms
import config
from model import SiameseNetwork


class SignatureVerifier:
    """
    Class for verifying signatures using trained Siamese Network
    """
    
    def __init__(self, model_path=None, device=None):
        """
        Initialize the verifier with a trained model
        
        Args:
            model_path: Path to the trained model checkpoint
            device: Device to run inference on ('cuda' or 'cpu')
        """
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        # Create model
        self.model = SiameseNetwork(
            embedding_dim=config.EMBEDDING_DIM,
            backbone=config.BACKBONE,
            pretrained=False  # Don't need pretrained weights, we load our own
        )
        
        # Load trained weights
        if model_path is None:
            model_path = config.BEST_MODEL_PATH
        
        if os.path.exists(model_path):
            checkpoint = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            print(f"Loaded model from {model_path}")
            print(f"Model trained for {checkpoint['epoch'] + 1} epochs")
            print(f"Validation accuracy: {checkpoint['val_acc']:.2f}%")
        else:
            print(f"Warning: No model found at {model_path}")
            print("Using untrained model weights")
        
        self.model.to(self.device)
        self.model.eval()
        
        # Create transform
        self.transform = self._get_transform()
    
    def _get_transform(self):
        """Get image transform for inference"""
        if config.GRAYSCALE:
            normalize = transforms.Normalize(mean=[0.5], std=[0.5])
        else:
            normalize = transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        
        return transforms.Compose([
            transforms.Resize(config.IMAGE_SIZE),
            transforms.ToTensor(),
            normalize
        ])
    
    def load_image(self, image_path_or_pil):
        """
        Load and preprocess an image
        
        Args:
            image_path_or_pil: Path to image file or PIL Image object
        
        Returns:
            Preprocessed image tensor
        """
        if isinstance(image_path_or_pil, str):
            img = Image.open(image_path_or_pil)
        else:
            img = image_path_or_pil
        
        # Convert to grayscale or RGB based on config
        if config.GRAYSCALE:
            img = img.convert('L')
        else:
            img = img.convert('RGB')
        
        # Apply transforms
        img_tensor = self.transform(img)
        
        # Add batch dimension
        img_tensor = img_tensor.unsqueeze(0)
        
        return img_tensor
    
    def verify(self, original_signature, test_signature, return_score=True):
        """
        Verify if two signatures are from the same person
        
        Args:
            original_signature: Path to original signature image or PIL Image
            test_signature: Path to test signature image or PIL Image
            return_score: If True, return similarity score; else return match/no match
        
        Returns:
            If return_score: tuple (is_match: bool, similarity_score: float)
            Else: bool indicating if signatures match
        """
        # Load images
        img1 = self.load_image(original_signature).to(self.device)
        img2 = self.load_image(test_signature).to(self.device)
        
        # Get prediction
        with torch.no_grad():
            similarity_score = self.model(img1, img2).item()
        
        # Determine match (threshold = 0.5)
        is_match = similarity_score > 0.5
        
        if return_score:
            return is_match, similarity_score
        else:
            return is_match
    
    def verify_from_url(self, original_url, test_url):
        """
        Verify signatures from URLs (for web API)
        
        Args:
            original_url: URL to original signature image
            test_url: URL to test signature image
        
        Returns:
            dict with match result, score, and confidence
        """
        import requests
        from io import BytesIO
        
        # Download images
        response1 = requests.get(original_url)
        response2 = requests.get(test_url)
        
        img1 = Image.open(BytesIO(response1.content))
        img2 = Image.open(BytesIO(response2.content))
        
        # Verify
        is_match, score = self.verify(img1, img2)
        
        # Determine confidence level
        if score > 0.8 or score < 0.2:
            confidence = "High"
        elif score > 0.6 or score < 0.4:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        return {
            "match": is_match,
            "score": round(score, 4),
            "confidence": confidence,
            "message": "Signatures match!" if is_match else "Signatures do NOT match!"
        }


def test_verification(original_path, test_path):
    """Test verification with two images"""
    verifier = SignatureVerifier()
    
    is_match, score = verifier.verify(original_path, test_path)
    
    print(f"\nSignature Verification Result:")
    print(f"  Original: {original_path}")
    print(f"  Test: {test_path}")
    print(f"  Similarity Score: {score:.4f}")
    print(f"  Match: {'✅ YES' if is_match else '❌ NO'}")
    
    return is_match, score


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) == 3:
        # Test with provided images
        test_verification(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python inference.py <original_signature_path> <test_signature_path>")
        print("\nExample:")
        print("  python inference.py path/to/original.png path/to/test.png")
