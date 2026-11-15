/* Utilidades compartidas de cámara: captura de fotogramas y llamadas a la API. */
(function () {
  const CAPTURE_WIDTH = 480; // ancho al que se reduce el fotograma antes de enviarlo

  async function startCamera(video) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Tu navegador no soporta acceso a la cámara (usa localhost o HTTPS).");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    return stream;
  }

  function stopCamera(video) {
    const stream = video.srcObject;
    if (stream) stream.getTracks().forEach((t) => t.stop());
    video.srcObject = null;
  }

  const work = document.createElement("canvas");
  function grabFrame(video) {
    const ratio = video.videoHeight / video.videoWidth;
    work.width = CAPTURE_WIDTH;
    work.height = Math.round(CAPTURE_WIDTH * ratio);
    work.getContext("2d").drawImage(video, 0, 0, work.width, work.height);
    return work.toDataURL("image/jpeg", 0.75);
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": window.CSRF_TOKEN },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error("Error del servidor (" + res.status + ")");
    return res.json();
  }

  /* Dibuja en el canvas superpuesto un recuadro por rostro detectado. */
  function drawFaces(canvas, video, data) {
    const rect = video.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!data || !data.faces.length) return;

    // El video usa object-fit: cover, así que hay que replicar el recorte.
    const scale = Math.max(rect.width / data.width, rect.height / data.height);
    const offX = (rect.width - data.width * scale) / 2;
    const offY = (rect.height - data.height * scale) / 2;
    const colors = { registrado: "#34d399", ya_registrado: "#fbbf24", desconocido: "#f87171", detectado: "#38bdf8" };

    data.faces.forEach((f) => {
      const [x, y, w, h] = f.box;
      const px = x * scale + offX, py = y * scale + offY, pw = w * scale, ph = h * scale;
      const color = colors[f.status] || colors.detectado;
      ctx.lineWidth = 3;
      ctx.strokeStyle = color;
      ctx.strokeRect(px, py, pw, ph);

      let label = f.name;
      if (f.distance !== null && f.distance !== undefined) label += " · dist. " + f.distance;
      ctx.font = "600 14px system-ui, sans-serif";
      const tw = ctx.measureText(label).width + 14;
      const ty = Math.max(py - 26, 0);
      ctx.fillStyle = color;
      ctx.fillRect(px, ty, tw, 24);
      ctx.fillStyle = "#04130f";
      ctx.fillText(label, px + 7, ty + 17);
    });
  }

  window.Camara = { startCamera, stopCamera, grabFrame, postJSON, drawFaces };
})();
