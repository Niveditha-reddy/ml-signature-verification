import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
from PIL import Image
import gradio as gr
import numpy as np

# --------------------------------------------------
# Configuration
# --------------------------------------------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_PATH = "final_signature_verification_model.pth"  # put this in repo root

IMAGE_SIZE = (224, 224)

# --------------------------------------------------
# Model definition (SAME as training)
# --------------------------------------------------
class SiameseNetwork(nn.Module):
    def __init__(self, embedding_dim=128):
        super().__init__()

        backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

        self.feature_extractor = nn.Sequential(
            *list(backbone.children())[:-1]
        )

        self.embedding = nn.Linear(512, embedding_dim)

    def forward_once(self, x):
        feat = self.feature_extractor(x)
        feat = feat.view(feat.size(0), -1)
        emb = self.embedding(feat)
        emb = F.normalize(emb, p=2, dim=1)
        return emb

    def forward(self, x1, x2):
        return self.forward_once(x1), self.forward_once(x2)


# --------------------------------------------------
# Load trained model
# --------------------------------------------------
print("🔄 Loading model...")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")

checkpoint = torch.load(
    MODEL_PATH,
    map_location=DEVICE,
    weights_only=False
)

model = SiameseNetwork(embedding_dim=checkpoint["embedding_dim"])
model.load_state_dict(checkpoint["model_state_dict"])
model.to(DEVICE)
model.eval()

print("✅ Model loaded successfully")

# --------------------------------------------------
# Image preprocessing (MUST match training)
# --------------------------------------------------
transform = transforms.Compose([
    transforms.Resize(IMAGE_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# --------------------------------------------------
# Inference function (returns similarity score only)
# --------------------------------------------------
def compute_similarity(image1, image2):
    if image1 is None or image2 is None:
        return "❌ Please upload both images."

    try:
        img1 = transform(image1.convert("RGB")).unsqueeze(0).to(DEVICE)
        img2 = transform(image2.convert("RGB")).unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            emb1, emb2 = model(img1, img2)
            distance = torch.nn.functional.pairwise_distance(emb1, emb2).item()
            similarity = float(np.exp(-distance))

        return f"🔍 Similarity Score: {similarity:.4f}"

    except Exception as e:
        return f"❌ Error: {str(e)}"


# --------------------------------------------------
# Gradio UI
# --------------------------------------------------
demo = gr.Interface(
    fn=compute_similarity,
    inputs=[
        gr.Image(type="pil", label="Signature Image 1"),
        gr.Image(type="pil", label="Signature Image 2")
    ],
    outputs=gr.Textbox(label="Result"),
    title="✍️ Signature Similarity Checker",
    description="Upload two signature images to get a similarity score (0–1)."
)

if __name__ == "__main__":
    demo.launch()
