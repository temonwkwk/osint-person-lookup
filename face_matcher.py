"""Face Matching Module using OpenCV YuNet (Detection) and SFace (Recognition).

Runs 100% on local CPU via ONNX models, without external APIs or cloud dependencies.
Embeddings are cached in .face_cache/ to prevent duplicate processing.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
import numpy as np

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

MODELS_DIR = Path(__file__).resolve().parent / "models"
CACHE_DIR = Path(__file__).resolve().parent / ".face_cache"

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_PATH = MODELS_DIR / "face_recognition_sface_2021dec.onnx"


class FaceMatcher:
    def __init__(self):
        self.enabled = False
        if not OPENCV_AVAILABLE:
            print("[FaceMatcher] OpenCV (cv2) not available. Face matching disabled.")
            return

        self._ensure_models()
        if not (YUNET_PATH.exists() and SFACE_PATH.exists()):
            print("[FaceMatcher] Model files missing. Face matching disabled.")
            return

        try:
            self.detector = cv2.FaceDetectorYN.create(
                model=str(YUNET_PATH),
                config="",
                input_size=(320, 320),
                score_threshold=0.7,
                nms_threshold=0.3,
                top_k=5000,
            )
            self.recognizer = cv2.FaceRecognizerSF.create(
                model=str(SFACE_PATH),
                config="",
            )
            CACHE_DIR.mkdir(exist_ok=True)
            self.enabled = True
        except Exception as e:
            print(f"[FaceMatcher] Init error: {e}")
            self.enabled = False

    def _ensure_models(self):
        MODELS_DIR.mkdir(exist_ok=True)
        if not YUNET_PATH.exists():
            print("[FaceMatcher] Downloading YuNet face detection model...")
            try:
                urllib.request.urlretrieve(YUNET_URL, YUNET_PATH)
            except Exception as e:
                print(f"[FaceMatcher] Failed to download YuNet: {e}")

        if not SFACE_PATH.exists():
            print("[FaceMatcher] Downloading SFace face recognition model (~37MB)...")
            try:
                urllib.request.urlretrieve(SFACE_URL, SFACE_PATH)
            except Exception as e:
                print(f"[FaceMatcher] Failed to download SFace: {e}")

    def _get_cache_key(self, source: str | bytes | Path) -> str:
        if isinstance(source, bytes):
            return hashlib.md5(source).hexdigest()
        return hashlib.md5(str(source).encode("utf-8")).hexdigest()

    def get_face_feature(self, image_source: str | Path | bytes) -> np.ndarray | None:
        """Extract aligned 128-d face embedding from image path, URL, or raw bytes."""
        if not self.enabled:
            return None

        cache_key = self._get_cache_key(image_source)
        cache_file = CACHE_DIR / f"{cache_key}.npy"
        if cache_file.exists():
            try:
                return np.load(cache_file)
            except Exception:
                pass

        # Load image into numpy array
        img = None
        if isinstance(image_source, bytes):
            nparr = np.frombuffer(image_source, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_source, (str, Path)):
            src_str = str(image_source)
            if src_str.startswith(("http://", "https://")):
                try:
                    req = urllib.request.Request(
                        src_str,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    )
                    data = urllib.request.urlopen(req, timeout=10).read()
                    nparr = np.frombuffer(data, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                except Exception:
                    return None
            else:
                p = Path(src_str)
                if p.exists():
                    img = cv2.imread(str(p))

        if img is None:
            return None

        h, w, _ = img.shape
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)

        if faces is None or len(faces) == 0:
            return None

        # Pick the largest face if multiple detected
        face = max(faces, key=lambda f: f[2] * f[3])

        # Align & extract feature embedding
        aligned_face = self.recognizer.alignCrop(img, face)
        feature = self.recognizer.feature(aligned_face)

        # Cache feature to disk
        try:
            np.save(cache_file, feature)
        except Exception:
            pass

        return feature

    def compare_faces(self, feat1: np.ndarray, feat2: np.ndarray) -> tuple[float, bool]:
        """Compute cosine similarity. Returns (percentage, is_match).
        
        SFace threshold for cosine similarity is 0.363.
        Score mapping:
          < 0.15 -> 0-35%
          0.15 - 0.36 -> 35-69% (Unlikely/Weak)
          0.363 - 0.50 -> 70-85% (Match)
          > 0.50 -> 85-99% (Strong Match)
        """
        if not self.enabled or feat1 is None or feat2 is None:
            return (0.0, False)

        cos_score = self.recognizer.match(feat1, feat2, cv2.FaceRecognizerSF_FR_COSINE)
        is_match = cos_score >= 0.363

        # Map to intuitive percentage (0 - 100%)
        if cos_score <= 0.0:
            pct = 10.0
        elif cos_score < 0.363:
            pct = 10.0 + (cos_score / 0.363) * 59.0
        else:
            pct = 70.0 + min(30.0, ((cos_score - 0.363) / 0.45) * 30.0)

        return (round(pct, 1), is_match)
