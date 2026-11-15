from django.urls import path

from . import views

urlpatterns = [
    path("", views.en_vivo, name="en_vivo"),
    path("inicio/", views.dashboard, name="dashboard"),
    path("personas/", views.personas, name="personas"),
    path("personas/<int:pk>/eliminar/", views.eliminar_persona, name="eliminar_persona"),
    path("registro/", views.registro, name="registro"),
    path("registro/<int:pk>/capturar/", views.capturar, name="capturar"),
    path("entrenar/", views.entrenar, name="entrenar"),
    path("historial/", views.historial, name="historial"),
    path("historial/exportar/", views.exportar_csv, name="exportar_csv"),
    path("api/frame/", views.api_frame, name="api_frame"),
    path("api/personas/<int:pk>/muestra/", views.api_muestra, name="api_muestra"),
]
