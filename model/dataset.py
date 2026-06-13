"""
Dataset loading and pair generation for Siamese Network
Handles CEDAR and BHSig260 datasets with different naming conventions
"""
import os
import random
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from itertools import combinations
import config


class SignatureDataset(Dataset):
    """
    Dataset for Siamese Network training
    Generates balanced genuine and forgery pairs
    """
    
    def __init__(self, pairs, labels, transform=None):
        """
        Args:
            pairs: List of tuples (img1_path, img2_path)
            labels: List of labels (1 for genuine pair, 0 for forgery pair)
            transform: Optional transform to apply to images
        """
        self.pairs = pairs
        self.labels = labels
        self.transform = transform
    
    def __len__(self):
        return len(self.pairs)
    
    def __getitem__(self, idx):
        img1_path, img2_path = self.pairs[idx]
        label = self.labels[idx]
        
        # Load images
        img1 = Image.open(img1_path)
        img2 = Image.open(img2_path)
        
        # Convert to grayscale if configured
        if config.GRAYSCALE:
            img1 = img1.convert('L')
            img2 = img2.convert('L')
        else:
            img1 = img1.convert('RGB')
            img2 = img2.convert('RGB')
        
        # Apply transforms
        if self.transform:
            img1 = self.transform(img1)
            img2 = self.transform(img2)
        
        return img1, img2, torch.tensor(label, dtype=torch.float32)


def get_file_type(filename, dataset_type):
    """
    Determine if a file is genuine or forged based on dataset naming convention
    
    Args:
        filename: Name of the image file
        dataset_type: 'cedar', 'bhsig_hindi', or 'bhsig_bengali'
    
    Returns:
        'genuine', 'forged', or None
    """
    pattern_info = config.DATASET_PATTERNS[dataset_type]
    genuine_pattern = pattern_info['genuine_pattern']
    forged_pattern = pattern_info['forged_pattern']
    pattern_type = pattern_info['type']
    
    filename_lower = filename.lower()
    
    if pattern_type == 'contains':
        if genuine_pattern.lower() in filename_lower:
            return 'genuine'
        elif forged_pattern.lower() in filename_lower:
            return 'forged'
    elif pattern_type == 'startswith':
        # For BHSig, check the actual filename (not path)
        base_name = os.path.basename(filename)
        if base_name.upper().startswith(genuine_pattern):
            return 'genuine'
        elif base_name.upper().startswith(forged_pattern):
            return 'forged'
    
    return None


def load_dataset_images(dataset_path, dataset_type):
    """
    Load all images from a dataset, organized by person
    
    Returns:
        dict: {person_id: {'genuine': [paths], 'forged': [paths]}}
    """
    data = {}
    
    # Walk through the dataset directory
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')):
                file_path = os.path.join(root, file)
                file_type = get_file_type(file, dataset_type)
                
                if file_type is None:
                    continue
                
                # Extract person ID from path
                # For CEDAR: parent folder name or extract from filename
                # For BHSig: parent folder name
                rel_path = os.path.relpath(root, dataset_path)
                
                # Use the first folder level as person ID
                if rel_path == '.':
                    # Files directly in dataset folder - extract ID from filename
                    # CEDAR format: original_1_1.png -> person 1
                    parts = file.replace('.', '_').split('_')
                    person_id = None
                    for part in parts:
                        if part.isdigit():
                            person_id = f"{dataset_type}_{part}"
                            break
                    if person_id is None:
                        continue
                else:
                    # Files in subfolders - use folder name as person ID
                    person_id = f"{dataset_type}_{rel_path.split(os.sep)[0]}"
                
                # Initialize person entry if needed
                if person_id not in data:
                    data[person_id] = {'genuine': [], 'forged': []}
                
                data[person_id][file_type].append(file_path)
    
    return data


def generate_balanced_pairs(data, max_pairs_per_person=None):
    """
    Generate balanced genuine and forgery pairs
    
    Args:
        data: dict from load_dataset_images
        max_pairs_per_person: Optional limit on pairs per person
    
    Returns:
        pairs: List of (img1_path, img2_path)
        labels: List of labels (1 for genuine, 0 for forgery)
    """
    genuine_pairs = []
    forgery_pairs = []
    
    for person_id, images in data.items():
        genuine_images = images['genuine']
        forged_images = images['forged']
        
        if len(genuine_images) < 2:
            continue
        
        # Generate genuine pairs (combinations of genuine signatures)
        person_genuine_pairs = list(combinations(genuine_images, 2))
        
        # Generate forgery pairs (genuine vs forged)
        person_forgery_pairs = []
        for genuine in genuine_images:
            for forged in forged_images:
                person_forgery_pairs.append((genuine, forged))
        
        # Limit pairs per person if specified
        if max_pairs_per_person:
            random.shuffle(person_genuine_pairs)
            random.shuffle(person_forgery_pairs)
            person_genuine_pairs = person_genuine_pairs[:max_pairs_per_person]
            person_forgery_pairs = person_forgery_pairs[:max_pairs_per_person]
        
        genuine_pairs.extend(person_genuine_pairs)
        forgery_pairs.extend(person_forgery_pairs)
    
    # Balance the dataset
    min_pairs = min(len(genuine_pairs), len(forgery_pairs))
    print(f"Total genuine pairs: {len(genuine_pairs)}")
    print(f"Total forgery pairs: {len(forgery_pairs)}")
    print(f"Balanced to: {min_pairs} pairs each")
    
    random.shuffle(genuine_pairs)
    random.shuffle(forgery_pairs)
    
    genuine_pairs = genuine_pairs[:min_pairs]
    forgery_pairs = forgery_pairs[:min_pairs]
    
    # Combine and create labels
    pairs = genuine_pairs + forgery_pairs
    labels = [1] * len(genuine_pairs) + [0] * len(forgery_pairs)
    
    # Shuffle together
    combined = list(zip(pairs, labels))
    random.shuffle(combined)
    pairs, labels = zip(*combined)
    
    return list(pairs), list(labels)


def get_transforms(train=True):
    """Get image transforms for training or validation"""
    if config.GRAYSCALE:
        normalize = transforms.Normalize(mean=[0.5], std=[0.5])
        channels = 1
    else:
        normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                                         std=[0.229, 0.224, 0.225])
        channels = 3
    
    if train and config.AUGMENT_TRAIN:
        transform = transforms.Compose([
            transforms.Resize(config.IMAGE_SIZE),
            transforms.RandomRotation(5),
            transforms.RandomAffine(degrees=0, translate=(0.05, 0.05)),
            transforms.ToTensor(),
            normalize
        ])
    else:
        transform = transforms.Compose([
            transforms.Resize(config.IMAGE_SIZE),
            transforms.ToTensor(),
            normalize
        ])
    
    return transform


def create_dataloaders():
    """Create train and validation dataloaders"""
    random.seed(config.RANDOM_SEED)
    
    # Load all datasets
    all_data = {}
    for dataset_name, dataset_path in config.DATASET_PATHS.items():
        if os.path.exists(dataset_path):
            print(f"Loading {dataset_name} from {dataset_path}")
            data = load_dataset_images(dataset_path, dataset_name)
            all_data.update(data)
            print(f"  Found {len(data)} persons")
        else:
            print(f"Warning: {dataset_path} not found, skipping...")
    
    print(f"\nTotal persons across all datasets: {len(all_data)}")
    
    # Generate balanced pairs
    pairs, labels = generate_balanced_pairs(all_data)
    print(f"Total balanced pairs: {len(pairs)}")
    
    # Split into train and validation
    split_idx = int(len(pairs) * config.TRAIN_SPLIT)
    
    train_pairs = pairs[:split_idx]
    train_labels = labels[:split_idx]
    val_pairs = pairs[split_idx:]
    val_labels = labels[split_idx:]
    
    print(f"Training pairs: {len(train_pairs)}")
    print(f"Validation pairs: {len(val_pairs)}")
    
    # Create datasets
    train_dataset = SignatureDataset(
        train_pairs, train_labels, 
        transform=get_transforms(train=True)
    )
    val_dataset = SignatureDataset(
        val_pairs, val_labels,
        transform=get_transforms(train=False)
    )
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset, 
        batch_size=config.BATCH_SIZE,
        shuffle=True,
        num_workers=0,  # Set to 0 for Windows compatibility
        pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=True
    )
    
    return train_loader, val_loader


if __name__ == '__main__':
    # Test dataset loading
    train_loader, val_loader = create_dataloaders()
    
    # Check a sample batch
    for img1, img2, labels in train_loader:
        print(f"Batch shape: img1={img1.shape}, img2={img2.shape}, labels={labels.shape}")
        print(f"Label distribution: {labels.sum().item()}/{len(labels)} genuine pairs")
        break
