---
title: SignatureGuard - Signature Verification
emoji: 🛡️
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

# SignatureGuard - Signature Verification API

A Siamese Network-based signature verification system.

## Features
- Upload two signature images
- Get similarity score and match result
- High/Medium/Low confidence levels

## Model
- Architecture: Siamese Network with MobileNetV2 backbone
- Training: CEDAR + BHSig260 datasets
- Accuracy: Testing (Epoch 1 model)

## API Usage

```python
import gradio_client

client = gradio_client.Client("YOUR_SPACE_URL")
result = client.predict(
    original_image="path/to/original.png",
    test_image="path/to/test.png",
    api_name="/predict"
)
print(result)
```
