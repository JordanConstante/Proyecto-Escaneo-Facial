"""Módulo de visión artificial (OpenCV).

Responsabilidades:
  * Decodificar los fotogramas enviados por el navegador.
  * Detectar rostros con un clasificador en cascada Haar.
  * Reconocer rostros con LBPH (Local Binary Patterns Histograms).
  * Entrenar, guardar y cargar el modelo de reconocimiento.

Se mantiene separado de las vistas para poder reutilizarlo y probarlo.
"""
from __future__ import annotations

import base64
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings

FACE_SIZE = (200, 200)
MIN_FACE = (60, 60)

_cascade = None
_cascade_lock = threading.Lock()
_model_state = {"recognizer": None, "mtime": None}


@dataclass
class FaceResult:
    """Un rostro detectado en un fotograma."""

    box: tuple[int, int, int, int]  # x, y, w, h
    label: int | None = None  # id de Persona si fue reconocido
    confidence: float | None = None  # distancia LBPH (menor = mejor)


# --------------------------------------------------------------------------- #
# Utilidades de imagen
# --------------------------------------------------------------------------- #
def decode_data_url(data_url: str) -> np.ndarray:
    """Convierte un 'data:image/jpeg;base64,...' en una imagen BGR de OpenCV."""
    if not isinstance(data_url, str) or "," not in data_url:
        raise ValueError("Formato de imagen inválido")
    raw = base64.b64decode(data_url.split(",", 1)[1], validate=False)
    buffer = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("No se pudo decodificar la imagen")
    return frame


def to_gray(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.equalizeHist(gray)


def preprocess_face(gray: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Recorta el rostro y lo normaliza a un tamaño fijo."""
    x, y, w, h = box
    face = gray[y : y + h, x : x + w]
    return cv2.resize(face, FACE_SIZE, interpolation=cv2.INTER_AREA)


# --------------------------------------------------------------------------- #
# Detección
# --------------------------------------------------------------------------- #
def get_cascade() -> cv2.CascadeClassifier:
    global _cascade
    with _cascade_lock:
        if _cascade is None:
            path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            classifier = cv2.CascadeClassifier(str(path))
            if classifier.empty():
                raise RuntimeError(f"No se pudo cargar el clasificador Haar en {path}")
            _cascade = classifier
    return _cascade


def detect_faces(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Devuelve los rostros detectados como (x, y, w, h), de mayor a menor."""
    cascade = get_cascade()
    with _cascade_lock:  # CascadeClassifier no es thread-safe
        found = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=MIN_FACE
        )
    boxes = [tuple(int(v) for v in b) for b in found]
    return sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)


# --------------------------------------------------------------------------- #
# Modelo de reconocimiento (LBPH)
# --------------------------------------------------------------------------- #
def _model_path() -> Path:
    return Path(settings.FACE_MODEL_PATH)


def model_ready() -> bool:
    return _model_path().exists()


def train_model(samples: list[tuple[int, np.ndarray]]) -> int:
    """Entrena LBPH con [(id_persona, imagen_gris_200x200), ...].

    Devuelve la cantidad de personas distintas usadas en el entrenamiento.
    """
    if not samples:
        raise ValueError("No hay muestras para entrenar")
    labels = np.array([s[0] for s in samples], dtype=np.int32)
    images = [s[1] for s in samples]
    recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(images, labels)
    path = _model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    recognizer.write(str(path))
    _model_state["recognizer"] = None  # fuerza recarga
    return len(set(labels.tolist()))


def _load_recognizer():
    path = _model_path()
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    if _model_state["recognizer"] is None or _model_state["mtime"] != mtime:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(str(path))
        _model_state.update(recognizer=recognizer, mtime=mtime)
    return _model_state["recognizer"]


def delete_model() -> None:
    path = _model_path()
    if path.exists():
        path.unlink()
    _model_state.update(recognizer=None, mtime=None)


def predict(face_gray: np.ndarray) -> tuple[int | None, float | None]:
    """Devuelve (id_persona, distancia). id=None si no supera el umbral."""
    recognizer = _load_recognizer()
    if recognizer is None:
        return None, None
    label, distance = recognizer.predict(face_gray)
    if distance <= settings.FACE_CONFIDENCE_THRESHOLD:
        return int(label), float(distance)
    return None, float(distance)


# --------------------------------------------------------------------------- #
# Pipeline completo sobre un fotograma
# --------------------------------------------------------------------------- #
def analyze_frame(frame: np.ndarray) -> list[FaceResult]:
    """Detecta y (si hay modelo) reconoce todos los rostros de un fotograma."""
    gray = to_gray(frame)
    results = []
    for box in detect_faces(gray):
        label, distance = predict(preprocess_face(gray, box))
        results.append(FaceResult(box=box, label=label, confidence=distance))
    return results


def largest_face_crop(frame: np.ndarray) -> np.ndarray | None:
    """Recorte normalizado del rostro más grande (None si no hay ninguno)."""
    gray = to_gray(frame)
    boxes = detect_faces(gray)
    if not boxes:
        return None
    return preprocess_face(gray, boxes[0])


def encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("No se pudo codificar la imagen")
    return buffer.tobytes()
