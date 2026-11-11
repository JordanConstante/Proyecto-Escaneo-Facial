import os
import time
import cv2
from django.conf import settings
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from .camera import get_camera

def index(request):
    return render(request, "captura/index.html")

def gen(cam):
    while True:
        frame = cam.get_frame()
        if frame is None:
            break
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")

def video_feed(request):
    return StreamingHttpResponse(
        gen(get_camera), content_type="multipart/x-mixed-replace; boundary=frame"
    )

@require_POST
def capture(request):
    rostro = get_camera.capture_face()
    if rostro is None:
        return JsonResponse({"ok": False, "error": "No se detectó rostro"}, status=400)
    carpeta = os.path.join(settings.MEDIA_ROOT, "rostros")
    os.makedirs(carpeta, exist_ok=True)
    nombre = f"rostro_{int(time.time())}.jpg"
    cv2.imwrite(os.path.join(carpeta, nombre), rostro)
    return JsonResponse({"ok": True, "archivo": f"rostros/{nombre}"})