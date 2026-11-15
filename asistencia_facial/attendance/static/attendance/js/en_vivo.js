/* Reconocimiento en vivo: envía fotogramas al servidor y muestra los resultados. */
(function () {
  const $ = (id) => document.getElementById(id);
  const video = $("video"), overlay = $("overlay"), msg = $("video-msg");
  const btnStart = $("btn-start"), btnStop = $("btn-stop");
  const fpsEl = $("fps"), countEl = $("count");
  const detectionsEl = $("detections"), eventsEl = $("events");

  let running = false;
  let frames = 0, lastTick = performance.now();
  const announced = new Set(); // evita repetir el mismo evento en pantalla

  const STATUS_TEXT = {
    registrado: ["Asistencia registrada", "tag-ok"],
    ya_registrado: ["Ya registrado hoy", "tag-warn"],
    desconocido: ["No reconocido", "tag-unk"],
  };

  function renderDetections(data) {
    countEl.textContent = data.count;
    detectionsEl.innerHTML = "";
    if (!data.faces.length) {
      detectionsEl.innerHTML = '<li class="muted">Sin detecciones</li>';
      return;
    }
    data.faces.forEach((f) => {
      const [text, cls] = STATUS_TEXT[f.status] || ["Detectado", ""];
      const li = document.createElement("li");
      const name = document.createElement("strong");
      name.textContent = f.name;
      const state = document.createElement("span");
      state.className = cls;
      state.textContent = text;
      li.append(name, state);
      detectionsEl.appendChild(li);
    });
  }

  function logEvents(data) {
    data.faces.forEach((f) => {
      if (f.status !== "registrado" || announced.has(f.name)) return;
      announced.add(f.name);
      if (eventsEl.querySelector(".muted")) eventsEl.innerHTML = "";
      const li = document.createElement("li");
      const who = document.createElement("span");
      who.textContent = f.name;
      const when = document.createElement("span");
      when.className = "muted";
      when.textContent = new Date().toLocaleTimeString("es-EC");
      li.append(who, when);
      eventsEl.prepend(li);
    });
  }

  function tickFps() {
    frames += 1;
    const now = performance.now();
    if (now - lastTick >= 1000) {
      fpsEl.textContent = Math.round((frames * 1000) / (now - lastTick)) + " FPS";
      frames = 0;
      lastTick = now;
    }
  }

  async function loop() {
    // Un solo envío a la vez: si el servidor tarda, no se acumulan fotogramas.
    while (running) {
      const started = performance.now();
      try {
        const data = await Camara.postJSON(window.API_FRAME, { image: Camara.grabFrame(video) });
        if (!running) break;
        Camara.drawFaces(overlay, video, data);
        renderDetections(data);
        logEvents(data);
        tickFps();
      } catch (err) {
        msg.hidden = false;
        msg.textContent = err.message;
        await new Promise((r) => setTimeout(r, 1500));
      }
      const wait = Math.max(0, 120 - (performance.now() - started));
      await new Promise((r) => setTimeout(r, wait));
    }
  }

  async function start() {
    btnStart.disabled = true;
    btnStart.hidden = true;
    msg.hidden = false;
    msg.textContent = "Abriendo la cámara automáticamente…";
    try {
      await Camara.startCamera(video);
    } catch (err) {
      msg.textContent = "No se pudo abrir la cámara: " + err.message;
      btnStart.disabled = false;
      btnStart.hidden = false;
      return;
    }
    msg.hidden = true;
    btnStop.disabled = false;
    running = true;
    loop();
  }

  function stop() {
    running = false;
    Camara.stopCamera(video);
    overlay.getContext("2d").clearRect(0, 0, overlay.width, overlay.height);
    msg.hidden = false;
    msg.textContent = "Cámara detenida";
    btnStart.hidden = false;
    btnStart.disabled = false;
    btnStop.disabled = true;
    fpsEl.textContent = "0 FPS";
    countEl.textContent = "0";
  }

  btnStart.addEventListener("click", start);
  btnStop.addEventListener("click", stop);
  window.addEventListener("beforeunload", () => Camara.stopCamera(video));

  // La cámara se abre automáticamente al cargar la página.
  // (Si el usuario niega el permiso, el botón «Iniciar cámara» permite reintentar.)
  start();
})();
