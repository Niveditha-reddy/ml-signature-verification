"""
Configuration file for Siamese Network Signature Verification
"""
import os

# Dataset Paths
DATASET_PATHS = {
    'cedar': r'C:\Users\abhir\Downloads\signature dataset\signatures',
    'bhsig_hindi': r'C:\Users\abhir\Downloads\signature dataset\BHSig260-Hindi',
    'bhsig_bengali': r'C:\Users\abhir\Downloads\signature dataset\BHSig260-Bengali'
}

# Dataset naming patterns
# CEDAR: files contain 'original' or 'forgeries' in name
# BHSig260: files contain '-G-' for genuine or '-F-' for forged in name
DATASET_PATTERNS = {
    'cedar': {
        'genuine_pattern': 'original',    # Contains 'original' in filename
        'forged_pattern': 'forgeries',    # Contains 'forgeries' in filename
        'type': 'contains'                # Pattern matching type
    },
    'bhsig_hindi': {
        'genuine_pattern': '-G-',         # Contains '-G-' in filename
        'forged_pattern': '-F-',          # Contains '-F-' in filename
        'type': 'contains'                # Pattern matching type
    },
    'bhsig_bengali': {
        'genuine_pattern': '-G-',         # Contains '-G-' in filename
        'forged_pattern': '-F-',          # Contains '-F-' in filename
        'type': 'contains'                # Pattern matching type
    }
}

# Image preprocessing
IMAGE_SIZE = (155, 220)  # Height x Width (standard for signature)
GRAYSCALE = True

# Model configuration
EMBEDDING_DIM = 512
BACKBONE = 'mobilenet_v2'  # Options: 'mobilenet_v2', 'resnet18', 'resnet50'
PRETRAINED = True

# Training configuration
BATCH_SIZE = 32
LEARNING_RATE = 0.0001
NUM_EPOCHS = 100  # Increased for better training
TRAIN_SPLIT = 0.8
MARGIN = 1.0  # Margin for contrastive loss

# Checkpoint configuration
CHECKPOINT_INTERVAL = 25  # Save checkpoint every N epochs
EARLY_STOPPING_PATIENCE = 15  # Stop if no improvement for N epochs

# Augmentation
AUGMENT_TRAIN = True

# Paths for saving
MODEL_SAVE_PATH = os.path.join(os.path.dirname(__file__), 'checkpoints')
BEST_MODEL_PATH = os.path.join(MODEL_SAVE_PATH, 'best_model.pth')

# Device
DEVICE = 'cuda'  # Will be set to 'cpu' if CUDA not available

# Seed for reproducibility
RANDOM_SEED = 42
