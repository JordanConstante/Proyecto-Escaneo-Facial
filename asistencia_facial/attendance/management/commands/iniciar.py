"""Inicia el sistema con un solo comando: migra la BD, levanta el servidor y abre el navegador.

Uso:  python manage.py iniciar [puerto]
"""
import threading
import webbrowser

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Aplica migraciones, inicia el servidor y abre el navegador (la cámara se abre sola)."

    def add_arguments(self, parser):
        parser.add_argument("puerto", nargs="?", default="8000")

    def handle(self, *args, **options):
        puerto = options["puerto"]
        url = f"http://localhost:{puerto}/"
        call_command("migrate", interactive=False, verbosity=0)
        self.stdout.write(self.style.SUCCESS(f"Sistema listo en {url} (Ctrl+C para detener)"))
        threading.Timer(1.5, webbrowser.open, args=[url]).start()
        # --noreload evita que el navegador se abra dos veces.
        call_command("runserver", f"127.0.0.1:{puerto}", use_reloader=False)
