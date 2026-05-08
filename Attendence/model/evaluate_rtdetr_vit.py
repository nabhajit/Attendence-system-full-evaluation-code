#!/usr/bin/env python
# coding: utf-8

# # 1. Face Dataset Splitter (Train: 70%, Val: 20%, Test: 10%)
# This cell preserves class balance, copies images into their respective split folders, and prints the summary using `sklearn` and `shutil`.

# In[ ]:


import os
import shutil
from pathlib import Path
from sklearn.model_selection import train_test_split

def split_dataset(source_dir, dest_dir):
    source = Path(source_dir)
    dest = Path(dest_dir)
    
    train_dir = dest / 'train'
    val_dir = dest / 'val'
    test_dir = dest / 'test'
    
    for d in [train_dir, val_dir, test_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    total_train = total_val = total_test = 0
    
    for person_dir in source.iterdir():
        if not person_dir.is_dir():
            continue
            
        person_name = person_dir.name
        images = list(person_dir.glob('*.*'))
        if not images:
            continue
            
        # 70% train, 30% temp (for val and test)
        if len(images) < 3:
            print(f'Skipping {person_name} - not enough images to split properly')
            continue
            
        train_imgs, temp_imgs = train_test_split(images, test_size=0.3, random_state=42)
        
        if len(temp_imgs) < 2:
            val_imgs, test_imgs = temp_imgs, []
        else:
            # Of the 30% temp array, we want 20% for val and 10% for test
            # 2/3 for val, 1/3 for test
            val_imgs, test_imgs = train_test_split(temp_imgs, test_size=1/3, random_state=42)
            
        def copy_imgs(imgs, split_dir):
            target_dir = split_dir / person_name
            target_dir.mkdir(parents=True, exist_ok=True)
            for img in imgs:
                shutil.copy2(img, target_dir / img.name)
            return len(imgs)
            
        total_train += copy_imgs(train_imgs, train_dir)
        total_val += copy_imgs(val_imgs, val_dir)
        total_test += copy_imgs(test_imgs, test_dir)
        
    print('========================')
    print(f'Dataset Split Completed!')
    print(f'Train images: {total_train}')
    print(f'Val images:   {total_val}')
    print(f'Test images:  {total_test}')
    print('========================')

# Uncomment and set your paths to run the split
# split_dataset(source_dir='dataset', dest_dir='split_dataset')


# # 2. RT-DETR + ViT Evaluation Pipeline
# Detect faces with RT-DETR, align them, extract embeddings using ViT, and perform FAISS cosine similarity matching. Finally, output evaluation metrics just like the YOLO + FaceNet pipeline.

# In[ ]:


import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import time
import numpy as np
import cv2
import torch
import faiss
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm.notebook import tqdm
from sklearn.metrics import (accuracy_score, precision_score, recall_score, 
                             f1_score, roc_curve, auc, confusion_matrix)

# For RT-DETR
from ultralytics import RTDETR
# For Alignment 
from facenet_pytorch import MTCNN
# For ViT
import torchvision.models as models
import torchvision.transforms as transforms
import torch.nn as nn

# --- CONFIGURATION ---
TEST_DIR = Path('split_dataset/test')
TRAIN_DIR = Path('split_dataset/train') # Using train set embeddings to build the Gallery

YOLO_CONF = 0.5
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# --- LOAD MODELS ---
print("Loading RT-DETR Model...")
# Use an appropriate RT-DETR weights file if you have a face-specific one, or the base one
det_model = RTDETR('rtdetr-l.pt') 

print("Loading ViT Model for Embeddings...")
# Using Torchvision to avoid HuggingFace DNS/download issues
vit_weights = models.ViT_B_16_Weights.DEFAULT
vit_model = models.vit_b_16(weights=vit_weights).to(device)
vit_model.heads = nn.Identity() # output raw embedding vector
vit_model.eval()

# Standard ImageNet normalization for PyTorch models
vit_transforms = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# MTCNN used just for robust facial landmark alignment if wanted (optional fallback)
mtcnn_aligner = MTCNN(keep_all=False, select_largest=True, device=device)

def get_vit_embedding(face_img):
    # Preprocess img for ViT
    input_tensor = vit_transforms(face_img).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = vit_model(input_tensor)
    
    emb = emb.cpu().numpy().flatten()
    # Normalize for cosine similarity
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = (emb / norm).astype('float32')
    return emb

def get_embedding_via_pipeline(img_path):
    start_time = time.time()
    img_bgr = cv2.imread(str(img_path))
    if img_bgr is None:
        return None, 0
    
    # 1. Detect using RT-DETR
    results = det_model(img_bgr, verbose=False, conf=YOLO_CONF)
    boxes = results[0].boxes
    
    face_crop = None
    if len(boxes) > 0:
        confs = boxes.conf.cpu().numpy()
        best_idx = np.argmax(confs)
        x1, y1, x2, y2 = boxes.xyxy[best_idx].cpu().numpy().astype(int)
        
        # Crop with margin
        h, w = img_bgr.shape[:2]
        margin = max(4, int((x2 - x1) * 0.1))
        x1, y1 = max(0, x1 - margin), max(0, y1 - margin)
        x2, y2 = min(w, x2 + margin), min(h, y2 + margin)
        face_crop = img_bgr[y1:y2, x1:x2]
        
    if face_crop is None or face_crop.size == 0:
        return None, time.time() - start_time
        
    face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
    
    # 2. Align (using MTCNN to get precise tight crop aligned on face if you want, 
    # but bounding box is often enough since ViT is quite robust)
    # To mimic exact pipeline alignment behaviors:
    try:
        aligned = mtcnn_aligner(face_rgb)
        if aligned is not None:
            # Reformat to RGB numpy array for ViT feature extractor
            aligned_img = aligned.permute(1, 2, 0).cpu().numpy()
            aligned_img = ((aligned_img * 128.0) + 127.5).astype(np.uint8)
            face_rgb = aligned_img
    except Exception:
        pass # Fallback to unaligned YOLO crop
        
    # 3. Embed
    emb = get_vit_embedding(face_rgb)
    
    inference_time = time.time() - start_time
    return emb, inference_time


# In[ ]:


# --- BUILD GALLERY ---
gallery_embs = []
gallery_names = []

print("Extracting gallery embeddings from Train split...")
if TRAIN_DIR.exists():
    for person_dir in tqdm(list(TRAIN_DIR.iterdir()), desc="Gallery Persons"):
        if not person_dir.is_dir(): continue
        name = person_dir.name
        
        # You can average embeddings per person or store all. Storing averaged is cleaner.
        person_embs = []
        for img_path in person_dir.glob('*.*'):
            emb, _ = get_embedding_via_pipeline(img_path)
            if emb is not None:
                person_embs.append(emb)
                
        if person_embs:
            # Average vector representing person
            mean_emb = np.mean(person_embs, axis=0).astype('float32')
            mean_emb /= np.linalg.norm(mean_emb)
            gallery_embs.append(mean_emb)
            gallery_names.append(name)
            
    if gallery_embs:
        gallery_matrix = np.vstack(gallery_embs)
        dimension = gallery_matrix.shape[1]
        index = faiss.IndexFlatIP(dimension) # Cosine similarity
        index.add(gallery_matrix)
        print(f"Gallery built! Persons: {len(gallery_names)}, Vector Size: {dimension}")
else:
    print("Train directory not found. Please run the split_dataset cell first.")


# In[ ]:


# --- EVALUATION ON TEST SET ---
y_true = []
y_scores = []
y_pred = []
inference_times = []

# This threshold should ideally be tuned using the Val set to find EER.
# Setting a default value here for demonstration.
EVAL_THRESHOLD = 0.5 

print("Evaluating test set...")
if TEST_DIR.exists() and gallery_embs:
    # Need images from test set too! The inner loop processes test images now.
    for person_dir in tqdm(list(TEST_DIR.iterdir()), desc="Test Persons"):
        if not person_dir.is_dir(): continue
        true_name = person_dir.name
        
        for img_path in person_dir.glob('*.*'):
            emb, t_inf = get_embedding_via_pipeline(img_path)
            inference_times.append(t_inf)
            
            if emb is not None:
                q = np.array([emb], dtype='float32')
                D, I = index.search(q, k=1)
                
                sim = D[0][0]
                pred_name = gallery_names[I[0][0]]
                
                y_true.append(1 if true_name == pred_name else 0)
                y_scores.append(sim)
                y_pred.append(1 if sim >= EVAL_THRESHOLD else 0)

# --- CALCULATE METRICS ---
if y_true:
    y_true_arr = np.array(y_true)
    y_scores_arr = np.array(y_scores)
    y_pred_arr = np.array(y_pred)
    
    acc = accuracy_score(y_true_arr, y_pred_arr)
    prec = precision_score(y_true_arr, y_pred_arr, zero_division=0)
    rec = recall_score(y_true_arr, y_pred_arr, zero_division=0)
    f1 = f1_score(y_true_arr, y_pred_arr, zero_division=0)
    
    fpr, tpr, thresholds = roc_curve(y_true_arr, y_scores_arr)
    roc_auc = auc(fpr, tpr)
    
    # EER calculation
    fnr = 1 - tpr
    eer_idx = np.argmin(np.abs(fpr - fnr))
    eer = (fpr[eer_idx] + fnr[eer_idx]) / 2.0
    eer_thr = thresholds[eer_idx]
    
    # FAR & FRR at current evaluation threshold
    idx = np.argmin(np.abs(thresholds - EVAL_THRESHOLD))
    far = fpr[idx]
    frr = fnr[idx]
    
    avg_inf_time = np.mean(inference_times)
    
    print('\n' + '='*40)
    print(f'RT-DETR + ViT Evaluation Metrics')
    print('='*40)
    print(f'Accuracy:             {acc*100:.2f}%')
    print(f'Precision:            {prec*100:.2f}%')
    print(f'Recall:               {rec*100:.2f}%')
    print(f'F1 Score:             {f1*100:.2f}%')
    print(f'ROC Curve AUC:        {roc_auc:.4f}')
    print(f'EER (Equal Error Rate): {eer*100:.2f}% (at thr={eer_thr:.3f})')
    print(f'FAR (False Accept):   {far*100:.2f}% (at thr={EVAL_THRESHOLD})')
    print(f'FRR (False Reject):   {frr*100:.2f}% (at thr={EVAL_THRESHOLD})')
    print(f'Avg Inference Time:   {avg_inf_time*1000:.2f} ms / image')
    print('='*40)
    
    # Optional: Plotting ROC
    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.4f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve (RT-DETR + ViT)')
    plt.legend(loc="lower right")
    plt.grid(True)
    plt.show()
else:
    print("No valid embeddings were extracted from the Test set.")

