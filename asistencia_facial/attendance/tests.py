
import base64
import json
import shutil
import tempfile

import cv2
import numpy as np
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import vision
from .models import Asistencia, MuestraRostro, Persona

TMP_MEDIA = tempfile.mkdtemp(prefix="faceattend_test_")


def to_data_url(frame: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def sample_face_frame():
    """Fotograma BGR con un rostro real, o None si no hay imagen de prueba."""
    try:
        from skimage import data
    except ImportError:  # pragma: no cover
        return None
    rgb = data.astronaut()
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


@override_settings(
    MEDIA_ROOT=TMP_MEDIA,
    FACE_MODEL_PATH=f"{TMP_MEDIA}/modelo_lbph.yml",
)
class VisionTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        vision.delete_model()

    def test_decode_data_url_roundtrip(self):
        frame = np.full((48, 64, 3), 127, dtype=np.uint8)
        decoded = vision.decode_data_url(to_data_url(frame))
        self.assertEqual(decoded.shape, (48, 64, 3))

    def test_decode_invalid_raises(self):
        with self.assertRaises(ValueError):
            vision.decode_data_url("no-es-una-imagen")

    def test_blank_frame_has_no_faces(self):
        frame = np.full((480, 640, 3), 90, dtype=np.uint8)
        self.assertEqual(vision.analyze_frame(frame), [])

    def test_detects_real_face(self):
        frame = sample_face_frame()
        if frame is None:
            self.skipTest("scikit-image no disponible")
        results = vision.analyze_frame(frame)
        self.assertGreaterEqual(len(results), 1)

    def test_train_and_recognize(self):
        frame = sample_face_frame()
        if frame is None:
            self.skipTest("scikit-image no disponible")
        gray = vision.to_gray(frame)
        box = vision.detect_faces(gray)[0]
        face = vision.preprocess_face(gray, box)
        # Variaciones leves de brillo para simular distintas muestras
        samples = [(7, np.clip(face.astype(int) + d, 0, 255).astype(np.uint8)) for d in (-10, -5, 0, 5, 10)]
        # Una segunda "persona" con ruido para que existan dos clases
        rng = np.random.default_rng(1)
        samples += [(9, rng.integers(0, 255, face.shape, dtype=np.uint8)) for _ in range(5)]
        self.assertEqual(vision.train_model(samples), 2)
        self.assertTrue(vision.model_ready())
        label, distance = vision.predict(face)
        self.assertEqual(label, 7)
        self.assertLess(distance, 70)


@override_settings(
    MEDIA_ROOT=TMP_MEDIA,
    FACE_MODEL_PATH=f"{TMP_MEDIA}/modelo_lbph.yml",
)
class ViewsTests(TestCase):
    def setUp(self):
        vision.delete_model()
        self.persona = Persona.objects.create(codigo="0912345678", nombres="Ana Prueba")

    def post_frame(self, url, frame):
        return self.client.post(
            url, data=json.dumps({"image": to_data_url(frame)}), content_type="application/json"
        )

    def test_pages_render(self):
        for name in ("dashboard", "en_vivo", "personas", "registro", "historial"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("capturar", args=[self.persona.pk])).status_code, 200)

    def test_home_is_live_camera_page(self):
        res = self.client.get("/")
        self.assertContains(res, 'id="video"')
        self.assertContains(res, "en_vivo.js")

    def test_register_person_redirects_to_capture(self):
        res = self.client.post(reverse("registro"), {"codigo": "111", "nombres": "luis   perez"})
        persona = Persona.objects.get(codigo="111")
        self.assertEqual(persona.nombres, "Luis Perez")
        self.assertRedirects(res, reverse("capturar", args=[persona.pk]))

    def test_duplicate_code_rejected(self):
        res = self.client.post(reverse("registro"), {"codigo": "0912345678", "nombres": "Otro"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Persona.objects.count(), 1)

    def test_api_frame_invalid_image(self):
        res = self.client.post(reverse("api_frame"), data="{}", content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_api_frame_blank(self):
        frame = np.full((480, 640, 3), 90, dtype=np.uint8)
        data = self.post_frame(reverse("api_frame"), frame).json()
        self.assertEqual(data["count"], 0)
        self.assertFalse(data["model_ready"])

    def test_api_frame_requires_post(self):
        self.assertEqual(self.client.get(reverse("api_frame")).status_code, 405)

    def test_sample_without_face_is_not_saved(self):
        frame = np.full((480, 640, 3), 90, dtype=np.uint8)
        data = self.post_frame(reverse("api_muestra", args=[self.persona.pk]), frame).json()
        self.assertFalse(data["ok"])
        self.assertEqual(MuestraRostro.objects.count(), 0)

    def test_full_flow_enroll_train_recognize(self):
        frame = sample_face_frame()
        if frame is None:
            self.skipTest("scikit-image no disponible")
        url = reverse("api_muestra", args=[self.persona.pk])
        for _ in range(5):
            self.assertTrue(self.post_frame(url, frame).json()["ok"])
        self.assertEqual(self.persona.muestras.count(), 5)

        res = self.client.post(reverse("entrenar"), HTTP_X_REQUESTED_WITH="fetch")
        self.assertTrue(res.json()["ok"])

        data = self.post_frame(reverse("api_frame"), frame).json()
        self.assertTrue(data["model_ready"])
        self.assertEqual(data["faces"][0]["name"], "Ana Prueba")
        self.assertEqual(data["faces"][0]["status"], "registrado")
        self.assertEqual(Asistencia.objects.filter(persona=self.persona).count(), 1)

        # Segundo fotograma el mismo día: no duplica la asistencia
        data = self.post_frame(reverse("api_frame"), frame).json()
        self.assertEqual(data["faces"][0]["status"], "ya_registrado")
        self.assertEqual(Asistencia.objects.filter(persona=self.persona).count(), 1)

    def test_train_without_samples(self):
        res = self.client.post(reverse("entrenar"), HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(res.status_code, 400)

    def test_history_and_csv(self):
        Asistencia.objects.create(persona=self.persona, fecha=timezone.localdate(), confianza=12.3)
        page = self.client.get(reverse("historial"))
        self.assertContains(page, "Ana Prueba")
        csv_res = self.client.get(reverse("exportar_csv"))
        self.assertEqual(csv_res["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("0912345678", csv_res.content.decode("utf-8"))

    def test_delete_person(self):
        res = self.client.post(reverse("eliminar_persona", args=[self.persona.pk]))
        self.assertRedirects(res, reverse("personas"))
        self.assertEqual(Persona.objects.count(), 0)
