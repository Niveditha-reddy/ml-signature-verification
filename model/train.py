"""
Training script for Siamese Network Signature Verification
Features: Periodic checkpoints, early stopping, resume training
"""
import os
import time
import torch
import torch.nn as nn
import torch.optim as optim
from tqdm import tqdm
import matplotlib.pyplot as plt

import config
from dataset import create_dataloaders
from model import create_model, BinaryCrossEntropyLoss


def train_epoch(model, train_loader, criterion, optimizer, device):
    """Train for one epoch"""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    # Use tqdm with minimal updates
    pbar = tqdm(train_loader, desc='Training', leave=False, 
                mininterval=5.0, ncols=80)
    for batch_idx, (img1, img2, labels) in enumerate(pbar):
        img1 = img1.to(device)
        img2 = img2.to(device)
        labels = labels.to(device)
        
        # Zero gradients
        optimizer.zero_grad()
        
        # Forward pass
        outputs = model(img1, img2)
        loss = criterion(outputs, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        # Statistics
        running_loss += loss.item()
        predictions = (outputs > 0.5).float()
        correct += (predictions == labels).sum().item()
        total += labels.size(0)
        
        # Update progress bar less frequently
        if batch_idx % 100 == 0:
            pbar.set_postfix({
                'loss': f'{running_loss/(batch_idx+1):.4f}',
                'acc': f'{100*correct/total:.1f}%'
            })
    
    pbar.close()
    epoch_loss = running_loss / len(train_loader)
    epoch_acc = 100 * correct / total
    
    return epoch_loss, epoch_acc


def validate(model, val_loader, criterion, device):
    """Validate the model"""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    all_predictions = []
    all_labels = []
    
    with torch.no_grad():
        pbar = tqdm(val_loader, desc='Validating', leave=False, 
                    mininterval=5.0, ncols=80)
        for img1, img2, labels in pbar:
            img1 = img1.to(device)
            img2 = img2.to(device)
            labels = labels.to(device)
            
            outputs = model(img1, img2)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            predictions = (outputs > 0.5).float()
            correct += (predictions == labels).sum().item()
            total += labels.size(0)
            
            all_predictions.extend(predictions.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
        
        pbar.close()
    
    epoch_loss = running_loss / len(val_loader)
    epoch_acc = 100 * correct / total
    
    # Calculate additional metrics
    all_predictions = [int(p) for p in all_predictions]
    all_labels = [int(l) for l in all_labels]
    
    # True positives, false positives, etc.
    tp = sum(1 for p, l in zip(all_predictions, all_labels) if p == 1 and l == 1)
    fp = sum(1 for p, l in zip(all_predictions, all_labels) if p == 1 and l == 0)
    fn = sum(1 for p, l in zip(all_predictions, all_labels) if p == 0 and l == 1)
    tn = sum(1 for p, l in zip(all_predictions, all_labels) if p == 0 and l == 0)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return epoch_loss, epoch_acc, precision, recall, f1


def save_checkpoint(model, optimizer, scheduler, epoch, val_acc, history, path, is_best=False):
    """Save model checkpoint with all training state"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict() if scheduler else None,
        'val_acc': val_acc,
        'history': history
    }
    torch.save(checkpoint, path)
    marker = "⭐ BEST" if is_best else "📁"
    print(f"  {marker} Checkpoint saved: {os.path.basename(path)}")


def load_checkpoint(model, optimizer, scheduler, path, device):
    """Load checkpoint and return training state"""
    checkpoint = torch.load(path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    if scheduler and checkpoint['scheduler_state_dict']:
        scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
    
    return (
        checkpoint['epoch'],
        checkpoint['val_acc'],
        checkpoint.get('history', None)
    )


def plot_training_history(history, save_path=None):
    """Plot training history"""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    
    # Loss plot
    axes[0].plot(history['train_loss'], label='Train')
    axes[0].plot(history['val_loss'], label='Validation')
    axes[0].set_xlabel('Epoch')
    axes[0].set_ylabel('Loss')
    axes[0].set_title('Training and Validation Loss')
    axes[0].legend()
    
    # Accuracy plot
    axes[1].plot(history['train_acc'], label='Train')
    axes[1].plot(history['val_acc'], label='Validation')
    axes[1].set_xlabel('Epoch')
    axes[1].set_ylabel('Accuracy (%)')
    axes[1].set_title('Training and Validation Accuracy')
    axes[1].legend()
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path)
        print(f"Training history plot saved: {save_path}")
    
    plt.close()


def train(resume_from=None):
    """
    Main training function
    
    Args:
        resume_from: Path to checkpoint to resume from (optional)
    """
    print("=" * 60)
    print("Siamese Network Training for Signature Verification")
    print("=" * 60)
    
    # Set random seed
    torch.manual_seed(config.RANDOM_SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(config.RANDOM_SEED)
    
    # Create dataloaders
    print("\n📦 Loading datasets...")
    train_loader, val_loader = create_dataloaders()
    
    # Create model
    print("\n🏗️ Creating model...")
    model, device = create_model()
    
    # Loss and optimizer
    criterion = BinaryCrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=config.LEARNING_RATE)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='max', factor=0.5, patience=5
    )
    
    # Training history
    history = {
        'train_loss': [], 'train_acc': [],
        'val_loss': [], 'val_acc': [],
        'precision': [], 'recall': [], 'f1': []
    }
    
    start_epoch = 0
    best_val_acc = 0.0
    epochs_without_improvement = 0
    
    # Resume from checkpoint if specified
    if resume_from and os.path.exists(resume_from):
        print(f"\n🔄 Resuming from checkpoint: {resume_from}")
        start_epoch, best_val_acc, loaded_history = load_checkpoint(
            model, optimizer, scheduler, resume_from, device
        )
        start_epoch += 1  # Start from next epoch
        if loaded_history:
            history = loaded_history
        print(f"   Resuming from epoch {start_epoch}, best val acc: {best_val_acc:.2f}%")
    
    start_time = time.time()
    
    print(f"\n🚀 Starting training...")
    print(f"   Epochs: {start_epoch + 1} to {config.NUM_EPOCHS}")
    print(f"   Batch size: {config.BATCH_SIZE}")
    print(f"   Learning rate: {config.LEARNING_RATE}")
    print(f"   Checkpoint interval: every {config.CHECKPOINT_INTERVAL} epochs")
    print(f"   Early stopping patience: {config.EARLY_STOPPING_PATIENCE} epochs")
    print(f"   Device: {device}")
    print("-" * 60)
    
    for epoch in range(start_epoch, config.NUM_EPOCHS):
        print(f"\nEpoch {epoch + 1}/{config.NUM_EPOCHS}")
        
        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device
        )
        
        # Validate
        val_loss, val_acc, precision, recall, f1 = validate(
            model, val_loader, criterion, device
        )
        
        # Update scheduler
        scheduler.step(val_acc)
        
        # Save history
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['precision'].append(precision)
        history['recall'].append(recall)
        history['f1'].append(f1)
        
        # Print epoch summary
        print(f"  Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}%")
        print(f"  Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2f}%")
        print(f"  Precision: {precision:.4f} | Recall: {recall:.4f} | F1: {f1:.4f}")
        
        # Check for improvement
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            epochs_without_improvement = 0
            # Save best model
            save_checkpoint(
                model, optimizer, scheduler, epoch, val_acc, history,
                config.BEST_MODEL_PATH, is_best=True
            )
        else:
            epochs_without_improvement += 1
            print(f"  ⚠️ No improvement for {epochs_without_improvement} epochs")
        
        # Save periodic checkpoint
        if (epoch + 1) % config.CHECKPOINT_INTERVAL == 0:
            checkpoint_path = os.path.join(
                config.MODEL_SAVE_PATH, 
                f'checkpoint_epoch_{epoch + 1}.pth'
            )
            save_checkpoint(
                model, optimizer, scheduler, epoch, val_acc, history,
                checkpoint_path
            )
        
        # Early stopping
        if epochs_without_improvement >= config.EARLY_STOPPING_PATIENCE:
            print(f"\n⛔ Early stopping triggered after {epoch + 1} epochs")
            print(f"   No improvement for {config.EARLY_STOPPING_PATIENCE} epochs")
            break
        
        # Save plot periodically
        if (epoch + 1) % 10 == 0:
            plot_path = os.path.join(config.MODEL_SAVE_PATH, 'training_history.png')
            plot_training_history(history, plot_path)
    
    # Training complete
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("🎉 Training Complete!")
    print(f"   Total time: {total_time / 60:.2f} minutes")
    print(f"   Best validation accuracy: {best_val_acc:.2f}%")
    print(f"   Checkpoints saved in: {config.MODEL_SAVE_PATH}")
    print("=" * 60)
    
    # Save final plot
    plot_path = os.path.join(config.MODEL_SAVE_PATH, 'training_history.png')
    plot_training_history(history, plot_path)
    
    # List saved checkpoints
    print("\n📁 Saved Model Files:")
    for f in os.listdir(config.MODEL_SAVE_PATH):
        if f.endswith('.pth'):
            print(f"   - {f}")
    
    return model, history


if __name__ == '__main__':
    import sys
    
    # Check for resume argument
    resume_path = None
    if len(sys.argv) > 1:
        resume_path = sys.argv[1]
        if not os.path.exists(resume_path):
            print(f"Warning: Checkpoint not found: {resume_path}")
            resume_path = None
    
    train(resume_from=resume_path)
