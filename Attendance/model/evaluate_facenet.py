# -*- coding: utf-8 -*-
"""
evaluate_facenet.py
===================
Evaluates the FaceNet face recognition model on the LFW public dataset.

Split strategy (per person, only people with >= MIN_IMAGES_PER_PERSON):
  70% of each person's images  → train  (build recognition gallery / FAISS index)
  10% of each person's images  → val    (tune similarity threshold)
  20% of each person's images  → test   (final evaluation)

Metrics reported:
  Accuracy, Precision, Recall, F1, Specificity
  AUC-ROC, Average Precision (PR-AUC), R2 Score
  EER (Equal Error Rate), FAR, FRR
  Confusion Matrix, Score Distribution, ROC & PR curves

Usage:
  python evaluate_facenet.py
  python evaluate_facenet.py --min-images 5    # default
  python evaluate_facenet.py --no-download     # skip download if LFW already exists
"""

import sys, os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import argparse
import tarfile
import urllib.request
import pickle
import random
import math
from pathlib import Path
from collections import defaultdict

import numpy as np
import cv2
import torch
from facenet_pytorch import InceptionResnetV1, MTCNN
import faiss
import matplotlib
matplotlib.use("Agg")           # non-interactive backend (no display needed)
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_curve, auc, precision_recall_curve, average_precision_score,
    confusion_matrix, r2_score
)

# ─── Config ───────────────────────────────────────────────────────────────────
ROOT             = Path(__file__).parent
LFW_DATASET_ROOT = ROOT / "lfw_dataset"
# Support both plain lfw/ and lfw-deepfunneled/lfw-deepfunneled/ (Kaggle version)
_candidates = [
    LFW_DATASET_ROOT / "lfw",
    LFW_DATASET_ROOT / "lfw-deepfunneled" / "lfw-deepfunneled",
    LFW_DATASET_ROOT / "lfw-deepfunneled",
]
LFW_DIR = next((p for p in _candidates if p.exists()), LFW_DATASET_ROOT / "lfw")
LFW_TGZ          = LFW_DATASET_ROOT / "lfw.tgz"
LFW_URL          = "http://vis-www.cs.umass.edu/lfw/lfw.tgz"
CACHE_FILE       = LFW_DATASET_ROOT / "embeddings_cache.pkl"
RESULTS_DIR      = ROOT / "eval_results"
MIN_IMAGES       = 5          # only use persons with at least this many images
RANDOM_SEED      = 42
TRAIN_RATIO      = 0.70
VAL_RATIO        = 0.10
TEST_RATIO       = 0.20
IMG_SIZE         = 160        # FaceNet input


# ─── Download & Extract ───────────────────────────────────────────────────────
def download_lfw():
    LFW_DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    # If images already exist (e.g. Kaggle download), skip entirely
    if LFW_DIR.exists() and any(LFW_DIR.iterdir()):
        print(f"LFW dataset found at: {LFW_DIR}")
        return
    if not LFW_TGZ.exists():
        print("Downloading LFW dataset (~180 MB) ...")
        def hook(c, bs, tot):
            if tot > 0:
                pct = min(100, c * bs * 100 // tot)
                bar = "#" * (pct // 5) + "." * (20 - pct // 5)
                print(f"\r  [{bar}] {pct}%", end="", flush=True)
        urllib.request.urlretrieve(LFW_URL, LFW_TGZ, reporthook=hook)
        print()
    else:
        print("LFW archive already downloaded.")
    if not LFW_DIR.exists():
        print("Extracting ...")
        with tarfile.open(LFW_TGZ, "r:gz") as tf:
            tf.extractall(LFW_DATASET_ROOT)
        print("Extracted to", LFW_DIR)
    else:
        print("LFW already extracted.")


# ─── Build person -> image list ───────────────────────────────────────────────
def collect_persons(min_images: int):
    persons = defaultdict(list)
    for person_dir in sorted(LFW_DIR.iterdir()):
        if not person_dir.is_dir():
            continue
        imgs = sorted(person_dir.glob("*.jpg"))
        if len(imgs) >= min_images:
            persons[person_dir.name] = [str(p) for p in imgs]
    print(f"Found {len(persons)} persons with >= {min_images} images "
          f"({sum(len(v) for v in persons.values())} images total)")
    return persons


# ─── Split ───────────────────────────────────────────────────────────────────
def split_dataset(persons: dict):
    random.seed(RANDOM_SEED)
    train, val, test = {}, {}, {}
    for name, imgs in persons.items():
        random.shuffle(imgs)
        n   = len(imgs)
        n_tr = max(1, math.floor(n * TRAIN_RATIO))
        n_va = max(1, math.floor(n * VAL_RATIO))
        train[name] = imgs[:n_tr]
        val[name]   = imgs[n_tr:n_tr + n_va]
        test[name]  = imgs[n_tr + n_va:]
    # Report
    n_tr = sum(len(v) for v in train.values())
    n_va = sum(len(v) for v in val.values())
    n_te = sum(len(v) for v in test.values())
    total = n_tr + n_va + n_te
    print(f"\nDataset split (persons={len(persons)}):")
    print(f"  Train : {n_tr} images ({100*n_tr//total}%)")
    print(f"  Val   : {n_va} images ({100*n_va//total}%)")
    print(f"  Test  : {n_te} images ({100*n_te//total}%)")
    return train, val, test


# ─── Embedding extraction ─────────────────────────────────────────────────────
def load_models():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\nDevice: {device}")
    facenet = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    mtcnn   = MTCNN(image_size=IMG_SIZE, margin=0, keep_all=False, device=device)
    return facenet, mtcnn, device


def get_embedding(img_path: str, facenet, mtcnn, device):
    """Extract normalised 512-D embedding for one image. Returns None on failure."""
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        return None
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    try:
        aligned = mtcnn(img_rgb)
        if aligned is None:
            # Fallback: resize directly without alignment
            r = cv2.resize(img_rgb, (IMG_SIZE, IMG_SIZE))
            tensor = torch.from_numpy(r).permute(2,0,1).float()
            tensor = (tensor - 127.5) / 128.0
        else:
            tensor = aligned
        tensor = tensor.unsqueeze(0).to(device)
        with torch.no_grad():
            emb = facenet(tensor).cpu().numpy().flatten()
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        return emb.astype("float32")
    except Exception:
        return None


def extract_all(split_dict: dict, facenet, mtcnn, device, desc=""):
    """Returns dict {person_name: [embedding, ...]}"""
    result = {}
    total  = sum(len(v) for v in split_dict.values())
    done   = 0
    for name, imgs in split_dict.items():
        embs = []
        for img_path in imgs:
            emb = get_embedding(img_path, facenet, mtcnn, device)
            if emb is not None:
                embs.append(emb)
            done += 1
            if done % 200 == 0:
                print(f"  {desc}: {done}/{total} images embedded ...")
        if embs:
            result[name] = embs
    return result


def build_cache(train, val, test, facenet, mtcnn, device):
    if CACHE_FILE.exists():
        print("Loading embeddings from cache ...")
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    print("\nExtracting embeddings (this takes a while on CPU) ...")
    data = {
        "train": extract_all(train, facenet, mtcnn, device, "train"),
        "val":   extract_all(val,   facenet, mtcnn, device, "val"),
        "test":  extract_all(test,  facenet, mtcnn, device, "test"),
    }
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(data, f)
    print("Embeddings cached.")
    return data


# ─── Build FAISS gallery from train embeddings ────────────────────────────────
def build_gallery(train_embs: dict):
    names, vecs = [], []
    for name, emb_list in train_embs.items():
        mean_emb = np.mean(emb_list, axis=0).astype("float32")
        mean_emb /= (np.linalg.norm(mean_emb) + 1e-8)
        names.append(name)
        vecs.append(mean_emb)
    matrix = np.vstack(vecs)
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    return index, names


# ─── Recognition evaluation ───────────────────────────────────────────────────
def evaluate_split(embs_dict: dict, gallery_index, gallery_names: list, threshold: float):
    """
    For each image in embs_dict, query gallery.
    Returns (y_true, y_pred, scores) where:
      y_true = 1 if top match is correct person, else 0  [ground truth]
      y_pred = 1 if similarity >= threshold,     else 0  [prediction]
      scores = raw cosine similarity to top match
    """
    y_true, y_pred, scores = [], [], []
    for true_name, emb_list in embs_dict.items():
        for emb in emb_list:
            q = np.array([emb], dtype="float32")
            faiss.normalize_L2(q)
            D, I = gallery_index.search(q, k=1)
            sim   = float(D[0][0])
            pred_name = gallery_names[int(I[0][0])]
            correct   = int(pred_name == true_name)
            y_true.append(correct)
            y_pred.append(int(sim >= threshold))
            scores.append(sim)
    return np.array(y_true), np.array(y_pred), np.array(scores)


def find_optimal_threshold(val_embs: dict, gallery_index, gallery_names: list):
    """Sweep thresholds on val set and return the one maximising F1."""
    _, _, scores = evaluate_split(val_embs, gallery_index, gallery_names, threshold=0.0)
    truths = []
    for true_name, emb_list in val_embs.items():
        for emb in emb_list:
            q = np.array([emb], dtype="float32")
            faiss.normalize_L2(q)
            D, I = gallery_index.search(q, k=1)
            pred_name = gallery_names[int(I[0][0])]
            truths.append(int(pred_name == true_name))

    truths = np.array(truths)
    scores_arr = np.array(scores)
    best_f1, best_thr = 0.0, 0.5
    for thr in np.arange(0.1, 0.95, 0.01):
        preds = (scores_arr >= thr).astype(int)
        if preds.sum() == 0:
            continue
        f1 = f1_score(truths, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_thr = f1, thr
    print(f"  Optimal threshold (val F1={best_f1:.4f}): {best_thr:.3f}")
    return best_thr


# ─── EER ──────────────────────────────────────────────────────────────────────
def compute_eer(y_true, scores):
    fpr, tpr, thresholds = roc_curve(y_true, scores)
    fnr = 1 - tpr
    # Find point where FAR == FRR
    abs_diff = np.abs(fpr - fnr)
    idx  = np.argmin(abs_diff)
    eer  = (fpr[idx] + fnr[idx]) / 2.0
    thr  = thresholds[idx]
    return eer, thr, fpr, tpr, fnr, thresholds


# ─── Plotting ─────────────────────────────────────────────────────────────────
def plot_dashboard(y_true, y_pred, scores, threshold, split_name="Test"):
    RESULTS_DIR.mkdir(exist_ok=True)

    acc  = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec  = recall_score(y_true, y_pred, zero_division=0)
    f1   = f1_score(y_true, y_pred, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0,1]).ravel()
    spec = tn / (tn + fp + 1e-8)

    fpr_roc, tpr_roc, _ = roc_curve(y_true, scores)
    roc_auc = auc(fpr_roc, tpr_roc)
    prec_pr, rec_pr, _ = precision_recall_curve(y_true, scores)
    ap  = average_precision_score(y_true, scores)
    eer, eer_thr, fpr_eer, tpr_eer, fnr_eer, thr_eer = compute_eer(y_true, scores)

    # R2 between scores and y_true
    r2 = r2_score(y_true, scores)

    fig = plt.figure(figsize=(18, 12))
    fig.suptitle(f"FaceNet Performance Dashboard - LFW ({split_name} Set)", fontsize=15, fontweight="bold")
    gs  = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35)

    # 1. Bar chart of metrics
    ax1 = fig.add_subplot(gs[0, 0])
    metrics_labels = ["Accuracy", "Precision", "Recall", "F1", "Specificity"]
    metrics_values = [acc, prec, rec, f1, spec]
    colors = ["#4CAF50","#2196F3","#FF9800","#9C27B0","#F44336"]
    bars = ax1.bar(metrics_labels, [v*100 for v in metrics_values], color=colors, width=0.6)
    for bar, val in zip(bars, metrics_values):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f"{val*100:.1f}%", ha="center", va="bottom", fontsize=8, fontweight="bold")
    ax1.set_ylim(0, 115)
    ax1.set_title("Classification Metrics")
    ax1.set_ylabel("Score (%)")
    ax1.tick_params(axis="x", labelsize=8)

    # 2. ROC Curve
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(fpr_roc, tpr_roc, color="#FF8C00", lw=2, label=f"AUC={roc_auc:.4f}")
    ax2.plot([0,1],[0,1],"--", color="grey", lw=1)
    ax2.fill_between(fpr_roc, tpr_roc, alpha=0.15, color="#FF8C00")
    ax2.set_xlabel("FPR"); ax2.set_ylabel("TPR")
    ax2.set_title(f"ROC (AUC={roc_auc:.4f})")
    ax2.legend(fontsize=8)

    # 3. Confusion Matrix
    ax3 = fig.add_subplot(gs[0, 2])
    cm = np.array([[tn, fp],[fn, tp]])
    im = ax3.imshow(cm, cmap="Blues")
    ax3.set_xticks([0,1]); ax3.set_yticks([0,1])
    ax3.set_xticklabels(["Diff","Same"]); ax3.set_yticklabels(["Diff","Same"])
    ax3.set_xlabel("Predicted"); ax3.set_ylabel("Actual")
    ax3.set_title("Confusion Matrix")
    for r in range(2):
        for c in range(2):
            ax3.text(c, r, str(cm[r,c]), ha="center", va="center",
                     fontsize=12, color="white" if cm[r,c] > cm.max()/2 else "black")
    plt.colorbar(im, ax=ax3, shrink=0.8)

    # 4. Score distribution
    ax4 = fig.add_subplot(gs[1, 0:2])
    same_scores = scores[y_true == 1]
    diff_scores = scores[y_true == 0]
    ax4.hist(diff_scores, bins=50, color="#E57373", alpha=0.7, density=True, label="Different")
    ax4.hist(same_scores, bins=50, color="#81C784", alpha=0.7, density=True, label="Same Person")
    ax4.axvline(threshold, color="navy", linestyle="--", lw=1.5, label=f"theta={threshold:.3f}")
    ax4.set_xlabel("Cosine Similarity"); ax4.set_ylabel("Density")
    ax4.set_title("Score Distribution")
    ax4.legend(fontsize=8)

    # 5. EER curve
    ax5 = fig.add_subplot(gs[1, 2])
    thr_arr = thr_eer
    ax5.plot(thr_arr, fpr_eer * 100, color="red", label="FAR")
    ax5.plot(thr_arr, fnr_eer * 100, color="blue", label="FRR")
    ax5.axvline(eer_thr, color="magenta", linestyle="--", lw=1.5)
    ax5.scatter([eer_thr],[eer*100], color="black", zorder=5)
    ax5.set_xlabel("Threshold"); ax5.set_ylabel("Error Rate (%)")
    ax5.set_title(f"EER={eer*100:.2f}%")
    ax5.legend(fontsize=8)

    # 6. PR Curve
    ax6 = fig.add_subplot(gs[2, 0])
    ax6.step(rec_pr, prec_pr, color="#43A047", where="post", lw=2)
    ax6.fill_between(rec_pr, prec_pr, alpha=0.15, color="#43A047")
    ax6.set_xlabel("Recall"); ax6.set_ylabel("Precision")
    ax6.set_title(f"PR Curve (AP={ap:.4f})")

    # 7. Summary text box
    ax7 = fig.add_subplot(gs[2, 1:3])
    ax7.axis("off")
    summary = (
        f"  FaceNet (VGGFace2) on LFW Benchmark\n"
        f"  {'─'*38}\n"
        f"  Accuracy      : {acc*100:.2f}%\n"
        f"  Precision     : {prec*100:.2f}%\n"
        f"  Recall        : {rec*100:.2f}%\n"
        f"  F1-Score      : {f1*100:.2f}%\n"
        f"  Specificity   : {spec*100:.2f}%\n"
        f"  AUC-ROC       : {roc_auc:.4f}\n"
        f"  Avg Precision : {ap:.4f}\n"
        f"  R2 Score      : {r2:.4f}\n"
        f"  EER           : {eer*100:.2f}%\n"
        f"  FAR @ opt thr : {fpr_eer[np.argmin(np.abs(thr_eer - threshold))]*100:.2f}%\n"
        f"  FRR @ opt thr : {fnr_eer[np.argmin(np.abs(thr_eer - threshold))]*100:.2f}%\n"
        f"  Threshold     : {threshold:.3f}\n"
        f"  Test Pairs    : {len(y_true)}\n"
    )
    ax7.text(0.05, 0.95, summary, transform=ax7.transAxes,
             fontsize=10, verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="#FFFDE7", alpha=0.8, edgecolor="#FBC02D"))

    out_path = RESULTS_DIR / "facenet_lfw_dashboard.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nDashboard saved: {out_path}")
    return out_path


# ─── Main ─────────────────────────────────────────────────────────────────────
def main(min_images=MIN_IMAGES, skip_download=False):
    print("=" * 60)
    print("  FaceNet Evaluation on LFW Public Dataset")
    print(f"  Split: {int(TRAIN_RATIO*100)}% train / "
          f"{int(VAL_RATIO*100)}% val / {int(TEST_RATIO*100)}% test")
    print("=" * 60)

    if not skip_download:
        download_lfw()

    persons = collect_persons(min_images)
    train, val, test = split_dataset(persons)

    facenet, mtcnn, device = load_models()
    cache = build_cache(train, val, test, facenet, mtcnn, device)

    print("\nBuilding FAISS gallery from train embeddings ...")
    gallery_index, gallery_names = build_gallery(cache["train"])

    print("\nFinding optimal threshold on validation set ...")
    threshold = find_optimal_threshold(cache["val"], gallery_index, gallery_names)

    print(f"\nEvaluating on test set (threshold={threshold:.3f}) ...")
    y_true, y_pred, scores = evaluate_split(cache["test"], gallery_index, gallery_names, threshold)

    print("\n" + "=" * 50)
    print("  RESULTS")
    print("=" * 50)
    from sklearn.metrics import classification_report
    print(classification_report(y_true, y_pred, target_names=["Mismatch","Match"]))

    out = plot_dashboard(y_true, y_pred, scores, threshold, split_name="Test")
    print(f"\nAll done! Open {out} to view the dashboard.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-images",    type=int, default=MIN_IMAGES)
    parser.add_argument("--no-download",   action="store_true")
    args = parser.parse_args()
    main(min_images=args.min_images, skip_download=args.no_download)
