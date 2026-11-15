/* Captura de muestras de rostro para registrar a una persona. */
(function () {
  const $ = (id) => document.getElementById(id);
  const video = $("video"), msg = $("video-msg");
  const btnStart = $("btn-start"), btnCapture = $("btn-capture"), btnDone = $("btn-done");
  const bar = $("bar"), totalEl = $("total"), statusEl = $("status");

  let total = window.EXISTENTES || 0;
  const goal = window.OBJETIVO;

  function setProgress() {
    totalEl.textContent = total;
    bar.style.width = Math.min(100, Math.round((total / goal) * 100)) + "%";
  }
  setProgress();

  async function start() {
    btnStart.disabled = true;
    msg.hidden = false;
    msg.textContent = "Solicitando acceso a la cámara…";
    try {
      await Camara.startCamera(video);
      msg.hidden = true;
      btnCapture.disabled = false;
    } catch (err) {
      msg.textContent = "No se pudo abrir la cámara: " + err.message;
      btnStart.disabled = false;
    }
  }

  async function capture() {
    btnCapture.disabled = true;
    let saved = 0, misses = 0;
    let duplicateName = null;
    const missing = Math.max(0, goal - total);
    if (missing === 0) {
      statusEl.textContent = "Ya se alcanzó el número de muestras requerido.";
      btnDone.hidden = false;
      return;
    }
    statusEl.textContent = "Capturando… mira a la cámara y gira un poco la cabeza.";
    while (saved < missing && misses < 40) {
      try {
        const res = await Camara.postJSON(window.API_MUESTRA, { image: Camara.grabFrame(video) });
        if (res.ok) {
          saved += 1;
          total = res.total;
          setProgress();
        } else if (res.motivo === "rostro_duplicado") {
          duplicateName = res.nombres;
          break;
        } else {
          misses += 1;
          statusEl.textContent = "No se detecta ningún rostro. Acércate y mejora la iluminación.";
        }
      } catch (err) {
        statusEl.textContent = err.message;
        misses += 1;
      }
      await new Promise((r) => setTimeout(r, 250));
    }

    if (duplicateName) {
      statusEl.className = "alert alert-warning";
      statusEl.textContent = `Este rostro ya está registrado a nombre de ${duplicateName}. No se guardó el nuevo registro.`;
      Camara.stopCamera(video);
      msg.hidden = false;
      msg.textContent = "Registro duplicado detectado";
      btnCapture.disabled = true;
      btnDone.textContent = "Volver a personas";
      btnDone.hidden = false;
      return;
    }

    if (saved < missing) {
      statusEl.textContent = "No se completó la captura. Inténtalo de nuevo con mejor iluminación.";
      btnCapture.disabled = false;
      return;
    }

    statusEl.textContent = "Entrenando el modelo…";
    try {
      const res = await fetch(window.API_ENTRENAR, {
        method: "POST",
        headers: { "X-CSRFToken": window.CSRF_TOKEN, "X-Requested-With": "fetch" },
      });
      const data = await res.json();
      statusEl.textContent = data.mensaje;
    } catch (err) {
      statusEl.textContent = "Muestras guardadas, pero falló el entrenamiento: " + err.message;
    }
    Camara.stopCamera(video);
    msg.hidden = false;
    msg.textContent = "Captura completada";
    btnDone.hidden = false;
  }

  btnStart.addEventListener("click", start);
  btnCapture.addEventListener("click", capture);
  window.addEventListener("beforeunload", () => Camara.stopCamera(video));
})();
