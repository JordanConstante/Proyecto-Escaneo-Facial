from django.db import models


class Persona(models.Model):


    codigo = models.CharField("Código / cédula", max_length=20, unique=True)
    nombres = models.CharField("Nombres completos", max_length=120)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombres"]
        verbose_name = "persona"
        verbose_name_plural = "personas"

    def __str__(self):
        return f"{self.nombres} ({self.codigo})"


class MuestraRostro(models.Model):


    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="muestras")
    imagen = models.FileField(upload_to="rostros/")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Muestra {self.pk} de {self.persona.nombres}"


class Asistencia(models.Model):


    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="asistencias")
    fecha = models.DateField(db_index=True)
    hora_registro = models.DateTimeField(auto_now_add=True)
    confianza = models.FloatField(help_text="Distancia LBPH (menor = más similar).")

    class Meta:
        ordering = ["-fecha", "-hora_registro"]
        constraints = [
            models.UniqueConstraint(fields=["persona", "fecha"], name="una_asistencia_por_dia"),
        ]

    def __str__(self):
        return f"{self.persona.nombres} - {self.fecha}"
