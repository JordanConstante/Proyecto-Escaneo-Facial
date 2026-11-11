import cv2
import threading

class FaceCamera:
    def __init__(self, index=0):
        self.video = cv2.VideoCapture(index)
        self.cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.lock = threading.Lock()
        self.last_frame = None  # frame sin rectángulos

    def __del__(self):
        if self.video.isOpened():
            self.video.release()

    def get_frame(self):
        ok, frame = self.video.read()
        if not ok:
            return None
        with self.lock:
            self.last_frame = frame.copy()

        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostros = self.cascade.detectMultiScale(
            gris, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80)
        )
        for (x, y, w, h) in rostros:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        _, jpeg = cv2.imencode(".jpg", frame)
        return jpeg.tobytes()

    def capture_face(self):
        with self.lock:
            if self.last_frame is None:
                return None
            frame = self.last_frame.copy()
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        rostros = self.cascade.detectMultiScale(gris, 1.2, 5, minSize=(80, 80))
        if len(rostros) == 0:
            return None
        x, y, w, h = rostros[0]
        return frame[y:y + h, x:x + w]

_camera = None

def get_camera():
    global _camera
    if _camera is None:
        _camera = FaceCamera()
    return _camera