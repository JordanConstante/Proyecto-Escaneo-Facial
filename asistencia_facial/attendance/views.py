import csv
import json
from datetime import date

import cv2
from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import vision
from .forms import PersonaForm
from .models import Asistencia, MuestraRostro, Persona



# Páginas

def dashboard(request):
    hoy = timezone.localdate()
    asistencias_hoy = Asistencia.objects.filter(fecha=hoy).select_related("persona")
    context = {
        "total_personas": Persona.objects.filter(activo=True).count(),
        "presentes_hoy": asistencias_hoy.count(),
        "total_muestras": MuestraRostro.objects.count(),
        "modelo_listo": vision.model_ready(),
        "asistencias_hoy": asistencias_hoy[:10],
        "hoy": hoy,
    }
    return render(request, "attendance/dashboard.html", context)


def en_vivo(request):
    return render(request, "attendance/en_vivo.html", {"modelo_listo": vision.model_ready()})


def personas(request):
    lista = Persona.objects.annotate(n_muestras=Count("muestras")).order_by("nombres")
    return render(
        request,
        "attendance/personas.html",
        {
            "personas": lista,
            "modelo_listo": vision.model_ready(),
            "muestras_objetivo": settings.FACE_SAMPLES_PER_PERSON,
        },
    )


def registro(request):
    if request.method == "POST":
        form = PersonaForm(request.POST)
        if form.is_valid():
            persona = form.save()
            request.session["registro_pendiente_persona"] = persona.pk
            messages.success(request, f"{persona.nombres} fue registrado. Ahora captura su rostro.")
            return redirect("capturar", pk=persona.pk)
    else:
        form = PersonaForm()
    return render(request, "attendance/registro.html", {"form": form})


def capturar(request, pk):
    persona = get_object_or_404(Persona, pk=pk)
    return render(
        request,
        "attendance/capturar.html",
        {
            "persona": persona,
            "objetivo": settings.FACE_SAMPLES_PER_PERSON,
            "existentes": persona.muestras.count(),
        },
    )


def historial(request):
    fecha_txt = request.GET.get("fecha")
    try:
        fecha = date.fromisoformat(fecha_txt) if fecha_txt else timezone.localdate()
    except ValueError:
        fecha = timezone.localdate()
    registros = Asistencia.objects.filter(fecha=fecha).select_related("persona")
    ausentes = Persona.objects.filter(activo=True).exclude(asistencias__fecha=fecha)
    return render(
        request,
        "attendance/historial.html",
        {"fecha": fecha, "registros": registros, "ausentes": ausentes},
    )


def exportar_csv(request):
    fecha_txt = request.GET.get("fecha")
    try:
        fecha = date.fromisoformat(fecha_txt) if fecha_txt else timezone.localdate()
    except ValueError:
        fecha = timezone.localdate()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="asistencia_{fecha}.csv"'
    response.write("﻿")  # BOM para que Excel respete las tildes
    writer = csv.writer(response)
    writer.writerow(["Código", "Nombres", "Fecha", "Hora", "Distancia LBPH"])
    for a in Asistencia.objects.filter(fecha=fecha).select_related("persona"):
        hora = timezone.localtime(a.hora_registro).strftime("%H:%M:%S")
        writer.writerow([a.persona.codigo, a.persona.nombres, a.fecha, hora, round(a.confianza, 2)])
    return response



# Acciones

@require_POST
def eliminar_persona(request, pk):
    persona = get_object_or_404(Persona, pk=pk)
    nombre = persona.nombres
    persona.delete()
    messages.success(request, f"{nombre} fue eliminado. Reentrena el modelo para aplicar el cambio.")
    return redirect("personas")


@require_POST
def entrenar(request):
    """Entrena el modelo LBPH con todas las muestras guardadas."""
    muestras = MuestraRostro.objects.filter(persona__activo=True).select_related("persona")
    samples = []
    for m in muestras:
        img = cv2.imread(m.imagen.path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            samples.append((m.persona_id, img))
    if not samples:
        vision.delete_model()
        msg = "Aún no hay muestras de rostros para entrenar."
        if request.headers.get("x-requested-with") == "fetch":
            return JsonResponse({"ok": False, "mensaje": msg}, status=400)
        messages.error(request, msg)
        return redirect("personas")
    n = vision.train_model(samples)
    persona_pendiente = request.session.get("registro_pendiente_persona")
    if persona_pendiente and Persona.objects.filter(pk=persona_pendiente, muestras__isnull=False).exists():
        request.session.pop("registro_pendiente_persona", None)
    msg = f"Modelo entrenado con {len(samples)} muestras de {n} persona(s)."
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": True, "mensaje": msg})
    messages.success(request, msg)
    return redirect("personas")




def _read_frame(request):
    try:
        payload = json.loads(request.body)
        return vision.decode_data_url(payload["image"])
    except (ValueError, KeyError, TypeError):
        return None


@require_POST
def api_frame(request):
    frame = _read_frame(request)
    if frame is None:
        return JsonResponse({"error": "Imagen inválida"}, status=400)

    hoy = timezone.localdate()
    height, width = frame.shape[:2]
    faces = []
    for r in vision.analyze_frame(frame):
        item = {
            "box": list(r.box),
            "name": "Desconocido",
            "status": "desconocido",
            "distance": None,
        }
        if r.confidence is not None:
            item["distance"] = round(r.confidence, 1)
        if r.label is not None:
            persona = Persona.objects.filter(pk=r.label, activo=True).first()
            if persona:
                _, creada = Asistencia.objects.get_or_create(
                    persona=persona, fecha=hoy, defaults={"confianza": r.confidence}
                )
                item["name"] = persona.nombres
                item["status"] = "registrado" if creada else "ya_registrado"
        faces.append(item)

    return JsonResponse(
        {
            "width": width,
            "height": height,
            "count": len(faces),
            "faces": faces,
            "model_ready": vision.model_ready(),
        }
    )


@require_POST
def api_muestra(request, pk):
    persona = get_object_or_404(Persona, pk=pk)
    frame = _read_frame(request)
    if frame is None:
        return JsonResponse({"error": "Imagen inválida"}, status=400)

    crop = vision.largest_face_crop(frame)
    if crop is None:
        return JsonResponse({"ok": False, "motivo": "sin_rostro", "total": persona.muestras.count()})

    label, distance = vision.predict(crop)
    if label is not None and label != persona.pk:
        existente = Persona.objects.filter(pk=label, activo=True).first()
        if existente:
            pendiente_id = request.session.get("registro_pendiente_persona")
            if pendiente_id == persona.pk:
                # La persona creada por el formulario es provisional hasta
                # terminar la captura. Si es duplicada, se descarta completa.
                for muestra_existente in persona.muestras.all():
                    muestra_existente.imagen.delete(save=False)
                persona.delete()
                request.session.pop("registro_pendiente_persona", None)
            return JsonResponse({
                "ok": False,
                "motivo": "rostro_duplicado",
                "nombres": existente.nombres,
                "distancia": round(distance, 1),
            })

    muestra = MuestraRostro(persona=persona)
    muestra.imagen.save(f"p{persona.pk}_{timezone.now():%Y%m%d%H%M%S%f}.png",
                        ContentFile(vision.encode_png(crop)), save=True)
    return JsonResponse({"ok": True, "total": persona.muestras.count()})
