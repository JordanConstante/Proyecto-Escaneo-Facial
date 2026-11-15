# FaceAttend · Control de asistencia por reconocimiento facial

Aplicativo web desarrollado con **Django**, **OpenCV** y **PostgreSQL** que captura video en tiempo real desde la cámara, detecta y reconoce rostros, y registra automáticamente la asistencia.

> Práctica 3 · Construcción de Software (CONSOF) · Universidad Estatal de Milagro (UNEMI)
> Enfoque elegido: **Detección de rostros para control de asistencia**

## Funcionalidades

- **Reconocimiento en vivo**: el navegador captura la cámara, envía fotogramas al servidor y recibe los resultados, que se dibujan directamente sobre el video (recuadro, nombre y porcentaje de similitud).
- **Detección con OpenCV**: clasificador en cascada Haar (`haarcascade_frontalface_default`).
- **Reconocimiento con OpenCV**: LBPH (`cv2.face.LBPHFaceRecognizer`), entrenado con las muestras de cada persona.
- **Registro guiado**: formulario + captura automática de 20 muestras de rostro con barra de progreso y entrenamiento automático al finalizar.
- **Prevención de duplicados**: durante la captura compara el rostro con el modelo entrenado y avisa si ya está asociado a otra persona; descarta el registro provisional duplicado.
- **Asistencia automática**: una asistencia por persona y día (restricción única en base de datos).
- **Conteo de personas en cámara** en tiempo real.
- **Historial** por fecha con presentes/ausentes y **exportación a CSV**.
- Panel de administración de Django para gestionar los datos.

## Arquitectura

```
asistencia_facial/
├── manage.py
├── requirements.txt
├── .env.example
├── config/                 # Configuración del proyecto Django
└── attendance/             # Aplicación principal
    ├── vision.py           # Módulo OpenCV (detección, LBPH, entrenamiento)
    ├── models.py           # Persona, MuestraRostro, Asistencia
    ├── views.py            # Páginas y API JSON
    ├── forms.py / urls.py / admin.py
    ├── tests.py            # Pruebas automatizadas (16)
    ├── templates/attendance/
    └── static/attendance/  # CSS y JS (cámara, captura, en vivo)
```

Flujo: `navegador (getUserMedia) → POST /api/frame/ → vision.analyze_frame → JSON → canvas sobre el video`.

## Requisitos

- Python 3.10 o superior
- PostgreSQL 13 o superior
- Una cámara web y un navegador moderno (Chrome, Edge o Firefox)

## Instalación

```bash
# 1. Clonar el repositorio
git clone <URL_DEL_REPOSITORIO>
cd asistencia_facial

# 2. Crear y activar un entorno virtual (no se sube al repositorio)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env         # Windows  (cp .env.example .env en Linux/macOS)
```

### Base de datos PostgreSQL

Crea la base de datos y ajusta las credenciales en `.env`:

```sql
CREATE DATABASE asistencia_facial;
```

### Ejecutar (la cámara se abre sola)

```bash
python manage.py iniciar
```

Este comando aplica las migraciones, inicia el servidor y **abre el navegador en http://localhost:8000**. La página principal solicita y abre la cámara automáticamente al cargar, sin pulsar «Iniciar cámara». La primera vez, el navegador puede pedir permiso para usarla; hay que aceptar ese permiso para que el video se muestre.

Alternativa manual:

```bash
python manage.py migrate
python manage.py runserver        # luego abre http://localhost:8000
python manage.py createsuperuser  # opcional, para /admin
```

La cámara solo funciona en `localhost` o bajo HTTPS.

> Para una prueba rápida sin PostgreSQL define `USE_SQLITE=1` en `.env`.

## Uso

1. **Registrar** → ingresa código y nombre → «Continuar a la captura».
2. **Capturar** → «Iniciar cámara» → «Capturar 20 muestras». Al terminar, el modelo se entrena solo.
3. **En vivo** (página principal) → la cámara se abre sola al entrar. Al reconocer a una persona se registra su asistencia.
4. **Historial** → consulta por fecha y exporta a CSV.

Consejos: buena iluminación frontal, un solo rostro durante el registro, y mover levemente la cabeza para variar las muestras. Si se registran o eliminan personas desde otra vía, usa «Entrenar modelo» en la sección Personas.

## Demostración y entrega

Para la demostración, graba desde un computador un recorrido de menos de 3 minutos. Muestra el registro de una persona, la captura de muestras, el reconocimiento en vivo con el recuadro sobre el video y el registro de asistencia, y finalmente el historial y su exportación CSV. Sube el video a Google Drive con permiso de visualización y agrega ese enlace junto con el enlace del repositorio al documento PDF solicitado por la guía.

Antes de publicar el repositorio, confirma que incluya `README.md` y `requirements.txt` y que no incluya `venv/`, `.venv/`, `.env`, `db.sqlite3` ni datos personales o imágenes reales de estudiantes. El archivo `.gitignore` excluye esos elementos locales.

## Privacidad y lectura de resultados

Las muestras faciales se guardan localmente en `media/rostros/` y se usan para entrenar el modelo. Solicita autorización antes de registrar a una persona y elimina las muestras cuando ya no sean necesarias. El valor `dist.` mostrado junto al rostro es la distancia de LBPH: una distancia menor indica una comparación más cercana, pero no es un porcentaje de certeza.

## Pruebas

```bash
python manage.py test attendance
```

Las pruebas cubren decodificación de imágenes, detección sobre un rostro real, entrenamiento y reconocimiento LBPH, el flujo completo de registro → asistencia sin duplicados, historial y exportación CSV. Las pruebas que usan un rostro real requieren `scikit-image` (`pip install scikit-image`); si no está instalado se omiten.

## Parámetros configurables (`.env`)

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `FACE_CONFIDENCE_THRESHOLD` | Distancia LBPH máxima para aceptar un reconocimiento (menor = más estricto) | 70 |
| `FACE_SAMPLES_PER_PERSON` | Muestras por persona en el registro | 20 |

## Tecnologías

Python · Django · OpenCV (`cv2`, módulo `face`) · NumPy · PostgreSQL · HTML/CSS/JavaScript
