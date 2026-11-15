from django.contrib import admin

from .models import Asistencia, MuestraRostro, Persona


@admin.register(Persona)
class PersonaAdmin(admin.ModelAdmin):
    list_display = ("nombres", "codigo", "activo", "creado")
    search_fields = ("nombres", "codigo")
    list_filter = ("activo",)


@admin.register(MuestraRostro)
class MuestraRostroAdmin(admin.ModelAdmin):
    list_display = ("id", "persona", "creado")


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("persona", "fecha", "hora_registro", "confianza")
    list_filter = ("fecha",)
