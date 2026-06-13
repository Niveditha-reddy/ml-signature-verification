"""
Siamese Network Model for Signature Verification
Uses MobileNetV2 as backbone with shared weights
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models
import config


class SiameseNetwork(nn.Module):
    """
    Siamese Network for signature verification
    Uses a shared CNN backbone to extract features from both images
    """
    
    def __init__(self, embedding_dim=512, backbone='mobilenet_v2', pretrained=True):
        super(SiameseNetwork, self).__init__()
        
        self.backbone_name = backbone
        
        # Load backbone
        if backbone == 'mobilenet_v2':
            self.backbone = models.mobilenet_v2(
                weights=models.MobileNet_V2_Weights.IMAGENET1K_V1 if pretrained else None
            )
            # Modify first conv layer if using grayscale
            if config.GRAYSCALE:
                self.backbone.features[0][0] = nn.Conv2d(
                    1, 32, kernel_size=3, stride=2, padding=1, bias=False
                )
            backbone_out_features = 1280
            self.backbone.classifier = nn.Identity()
            
        elif backbone == 'resnet18':
            self.backbone = models.resnet18(
                weights=models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
            )
            if config.GRAYSCALE:
                self.backbone.conv1 = nn.Conv2d(
                    1, 64, kernel_size=7, stride=2, padding=3, bias=False
                )
            backbone_out_features = 512
            self.backbone.fc = nn.Identity()
            
        elif backbone == 'resnet50':
            self.backbone = models.resnet50(
                weights=models.ResNet50_Weights.IMAGENET1K_V1 if pretrained else None
            )
            if config.GRAYSCALE:
                self.backbone.conv1 = nn.Conv2d(
                    1, 64, kernel_size=7, stride=2, padding=3, bias=False
                )
            backbone_out_features = 2048
            self.backbone.fc = nn.Identity()
        else:
            raise ValueError(f"Unknown backbone: {backbone}")
        
        # Embedding layers
        self.embedding = nn.Sequential(
            nn.Linear(backbone_out_features, 1024),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(1024, embedding_dim),
            nn.ReLU(inplace=True)
        )
        
        # Final classifier for similarity
        self.classifier = nn.Sequential(
            nn.Linear(embedding_dim, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
            nn.Sigmoid()
        )
    
    def forward_one(self, x):
        """Extract features from one image"""
        features = self.backbone(x)
        if len(features.shape) > 2:
            features = F.adaptive_avg_pool2d(features, 1)
            features = features.view(features.size(0), -1)
        embedding = self.embedding(features)
        return embedding
    
    def forward(self, img1, img2):
        """
        Forward pass for two images
        Returns similarity score (0-1)
        """
        # Get embeddings for both images (shared weights)
        emb1 = self.forward_one(img1)
        emb2 = self.forward_one(img2)
        
        # L1 distance between embeddings
        diff = torch.abs(emb1 - emb2)
        
        # Classify similarity
        similarity = self.classifier(diff)
        
        return similarity.squeeze()
    
    def get_embedding(self, img):
        """Get embedding for a single image (for inference)"""
        return self.forward_one(img)


class ContrastiveLoss(nn.Module):
    """
    Contrastive loss function
    Pulls similar pairs together, pushes dissimilar pairs apart
    """
    
    def __init__(self, margin=1.0):
        super(ContrastiveLoss, self).__init__()
        self.margin = margin
    
    def forward(self, output1, output2, label):
        """
        Args:
            output1: Embedding of first image
            output2: Embedding of second image
            label: 1 if same person, 0 if different
        """
        euclidean_distance = F.pairwise_distance(output1, output2)
        
        # Contrastive loss
        loss = torch.mean(
            label * torch.pow(euclidean_distance, 2) +
            (1 - label) * torch.pow(
                torch.clamp(self.margin - euclidean_distance, min=0.0), 2
            )
        )
        
        return loss


class BinaryCrossEntropyLoss(nn.Module):
    """
    Binary Cross Entropy loss for direct similarity prediction
    """
    
    def __init__(self):
        super(BinaryCrossEntropyLoss, self).__init__()
        self.bce = nn.BCELoss()
    
    def forward(self, prediction, label):
        return self.bce(prediction, label)


def create_model(device=None):
    """Create and return the Siamese Network model"""
    if device is None:
        device = torch.device(config.DEVICE if torch.cuda.is_available() else 'cpu')
    
    model = SiameseNetwork(
        embedding_dim=config.EMBEDDING_DIM,
        backbone=config.BACKBONE,
        pretrained=config.PRETRAINED
    )
    
    model = model.to(device)
    
    # Print model summary
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model: {config.BACKBONE}")
    print(f"Total parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    print(f"Device: {device}")
    
    return model, device


if __name__ == '__main__':
    # Test model creation
    model, device = create_model()
    
    # Test forward pass
    batch_size = 4
    if config.GRAYSCALE:
        img1 = torch.randn(batch_size, 1, *config.IMAGE_SIZE).to(device)
        img2 = torch.randn(batch_size, 1, *config.IMAGE_SIZE).to(device)
    else:
        img1 = torch.randn(batch_size, 3, *config.IMAGE_SIZE).to(device)
        img2 = torch.randn(batch_size, 3, *config.IMAGE_SIZE).to(device)
    
    with torch.no_grad():
        output = model(img1, img2)
    
    print(f"Input shape: {img1.shape}")
    print(f"Output shape: {output.shape}")
    print(f"Output values: {output}")
