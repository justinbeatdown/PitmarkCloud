(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const canvas = $('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const stage = $('stage');

  const state = {
    templateFile: null,
    templateName: 'paint',
    baseImage: null,
    versions: [],
    logos: [],
    selectedLogoId: null,
    fit: true,
    dragging: null,
  };

  const setStatus = (text, kind = '') => {
    const el = $('status');
    el.textContent = text;
    el.className = `status ${kind}`.trim();
  };

  const imageFromBlob = blob => new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => resolve({ img, url, blob });
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Could not read image.')); };
    img.src = url;
  });

  const imageFromFile = file => imageFromBlob(file);

  const baseName = name => (name || 'paint').replace(/\.[^.]+$/, '').replace(/[^a-z0-9_-]+/gi, '-');

  function updateButtons() {
    const loaded = !!state.baseImage;
    $('generateBtn').disabled = !loaded;
    $('resetBtn').disabled = !loaded;
    $('undoBtn').disabled = state.versions.length <= 1;
    $('pngBtn').disabled = !loaded;
    $('tgaBtn').disabled = !loaded;
  }

  function updateDisplay() {
    if (!canvas.width || !canvas.height) return;
    if (state.fit) {
      const maxW = Math.max(240, stage.clientWidth - 42);
      const maxH = Math.max(240, stage.clientHeight - 42);
      const scale = Math.min(maxW / canvas.width, maxH / canvas.height, 1);
      canvas.style.width = `${Math.max(1, Math.round(canvas.width * scale))}px`;
      canvas.style.height = `${Math.max(1, Math.round(canvas.height * scale))}px`;
    } else {
      canvas.style.width = `${canvas.width}px`;
      canvas.style.height = `${canvas.height}px`;
    }
    $('fitBtn').classList.toggle('active', state.fit);
    $('actualBtn').classList.toggle('active', !state.fit);
  }

  function selectedLogo() {
    return state.logos.find(x => x.id === state.selectedLogoId) || null;
  }

  function drawScene(forExport = false) {
    if (!state.baseImage) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(state.baseImage.img, 0, 0, canvas.width, canvas.height);
    for (const logo of state.logos) {
      if (!logo.visible) continue;
      ctx.save();
      ctx.globalAlpha = logo.opacity;
      ctx.drawImage(logo.img, logo.x, logo.y, logo.w, logo.h);
      ctx.restore();
    }
    if (!forExport) {
      const logo = selectedLogo();
      if (logo) {
        ctx.save();
        const ratio = canvas.width / Math.max(1, canvas.getBoundingClientRect().width);
        ctx.strokeStyle = '#ff5500';
        ctx.lineWidth = Math.max(2, 2 * ratio);
        ctx.setLineDash([8 * ratio, 5 * ratio]);
        ctx.strokeRect(logo.x, logo.y, logo.w, logo.h);
        ctx.restore();
      }
    }
  }

  function renderLogoList() {
    const list = $('logoList');
    if (!state.logos.length) {
      list.innerHTML = '<div class="empty">No logos added</div>';
      return;
    }
    list.innerHTML = '';
    state.logos.forEach(logo => {
      const row = document.createElement('div');
      row.className = `logo-item${logo.id === state.selectedLogoId ? ' active' : ''}`;
      const thumb = document.createElement('img');
      thumb.className = 'logo-thumb'; thumb.src = logo.url; thumb.alt = '';
      const name = document.createElement('div');
      name.className = 'logo-name'; name.textContent = logo.name;
      const eye = document.createElement('div');
      eye.className = 'logo-eye'; eye.textContent = logo.visible ? 'ON' : 'OFF';
      eye.title = 'Toggle visibility';
      eye.addEventListener('click', ev => {
        ev.stopPropagation(); logo.visible = !logo.visible; renderLogoList(); drawScene();
      });
      row.append(thumb, name, eye);
      row.addEventListener('click', () => selectLogo(logo.id));
      list.append(row);
    });
  }

  function selectLogo(id) {
    state.selectedLogoId = id;
    const logo = selectedLogo();
    $('selectedEmpty').classList.toggle('hidden', !!logo);
    $('logoControls').classList.toggle('hidden', !logo);
    if (logo) {
      $('scaleRange').value = String(Math.round(logo.scale * 100));
      $('opacityRange').value = String(Math.round(logo.opacity * 100));
    }
    renderLogoList();
    drawScene();
  }

  async function loadTemplate(file) {
    if (!file) return;
    setStatus('Loading template…', 'busy');
    try {
      const asset = await imageFromFile(file);
      state.versions.forEach(v => { if (v.url && v.url !== asset.url) URL.revokeObjectURL(v.url); });
      state.logos.forEach(v => v.url && URL.revokeObjectURL(v.url));
      state.templateFile = file;
      state.templateName = baseName(file.name);
      state.baseImage = asset;
      state.versions = [asset];
      state.logos = [];
      state.selectedLogoId = null;
      canvas.width = asset.img.naturalWidth;
      canvas.height = asset.img.naturalHeight;
      $('emptyStage').classList.add('hidden');
      $('templateMeta').textContent = `${file.name} · ${canvas.width} × ${canvas.height}`;
      $('canvasMeta').textContent = `${canvas.width} × ${canvas.height}px`;
      $('versionMeta').textContent = 'Version 1 · original';
      renderLogoList(); selectLogo(null); drawScene(); updateDisplay(); updateButtons();
      setStatus('Template ready');
    } catch (err) {
      setStatus(err.message || 'Template failed', 'error');
    }
  }

  function baseBlob() {
    return new Promise((resolve, reject) => {
      if (!state.baseImage) return reject(new Error('Load a template first.'));
      const scratch = document.createElement('canvas');
      scratch.width = canvas.width; scratch.height = canvas.height;
      const sctx = scratch.getContext('2d');
      sctx.drawImage(state.baseImage.img, 0, 0, scratch.width, scratch.height);
      scratch.toBlob(blob => blob ? resolve(blob) : reject(new Error('Could not prepare template.')), 'image/png');
    });
  }

  async function generate() {
    const prompt = $('prompt').value.trim();
    if (!prompt) { setStatus('Write a design brief first', 'error'); $('prompt').focus(); return; }
    $('generateBtn').disabled = true;
    setStatus('Generating paint pass…', 'busy');
    try {
      const current = await baseBlob();
      const form = new FormData();
      form.append('template', current, `${state.templateName}-working.png`);
      form.append('prompt', prompt);
      form.append('quality', $('quality').value);
      const ref = $('referenceInput').files[0];
      if (ref) form.append('reference', ref, ref.name);

      const response = await fetch('/api/control/content/paint-studio/generate', { method: 'POST', body: form });
      if (!response.ok) {
        let detail = `Generation failed (${response.status})`;
        try { detail = (await response.json()).detail || detail; } catch (_) {}
        throw new Error(detail);
      }
      const blob = await response.blob();
      const asset = await imageFromBlob(blob);
      state.baseImage = asset;
      state.versions.push(asset);
      $('versionMeta').textContent = `Version ${state.versions.length} · AI paint`;
      drawScene(); updateButtons();
      setStatus('Paint pass ready');
    } catch (err) {
      setStatus(err.message || 'Generation failed', 'error');
    } finally {
      updateButtons();
    }
  }

  async function addLogos(files) {
    for (const file of [...files]) {
      try {
        const asset = await imageFromFile(file);
        const ratio = asset.img.naturalHeight / Math.max(1, asset.img.naturalWidth);
        const baseW = canvas.width * .20;
        const logo = {
          id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
          name: file.name,
          img: asset.img,
          url: asset.url,
          x: canvas.width * .5 - baseW * .5,
          y: canvas.height * .5 - baseW * ratio * .5,
          baseW,
          ratio,
          scale: 1,
          w: baseW,
          h: baseW * ratio,
          opacity: 1,
          visible: true,
        };
        state.logos.push(logo);
        selectLogo(logo.id);
      } catch (_) {
        setStatus(`Could not load ${file.name}`, 'error');
      }
    }
    renderLogoList(); drawScene();
  }

  function pointFromEvent(ev) {
    const r = canvas.getBoundingClientRect();
    return { x: (ev.clientX - r.left) * canvas.width / r.width, y: (ev.clientY - r.top) * canvas.height / r.height };
  }

  function hitLogo(p) {
    for (let i = state.logos.length - 1; i >= 0; i--) {
      const l = state.logos[i];
      if (l.visible && p.x >= l.x && p.x <= l.x + l.w && p.y >= l.y && p.y <= l.y + l.h) return l;
    }
    return null;
  }

  canvas.addEventListener('pointerdown', ev => {
    if (!state.baseImage) return;
    const p = pointFromEvent(ev), logo = hitLogo(p);
    if (!logo) { selectLogo(null); return; }
    selectLogo(logo.id);
    state.dragging = { id: logo.id, dx: p.x - logo.x, dy: p.y - logo.y };
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener('pointermove', ev => {
    if (!state.dragging) return;
    const logo = selectedLogo(); if (!logo || logo.id !== state.dragging.id) return;
    const p = pointFromEvent(ev);
    logo.x = p.x - state.dragging.dx; logo.y = p.y - state.dragging.dy;
    drawScene();
  });
  canvas.addEventListener('pointerup', ev => { state.dragging = null; try { canvas.releasePointerCapture(ev.pointerId); } catch (_) {} });
  canvas.addEventListener('pointercancel', () => { state.dragging = null; });

  $('scaleRange').addEventListener('input', ev => {
    const logo = selectedLogo(); if (!logo) return;
    logo.scale = Number(ev.target.value) / 100;
    logo.w = logo.baseW * logo.scale; logo.h = logo.w * logo.ratio; drawScene();
  });
  $('opacityRange').addEventListener('input', ev => {
    const logo = selectedLogo(); if (!logo) return;
    logo.opacity = Number(ev.target.value) / 100; drawScene();
  });
  $('frontBtn').addEventListener('click', () => {
    const logo = selectedLogo(); if (!logo) return;
    state.logos = state.logos.filter(x => x.id !== logo.id); state.logos.push(logo); renderLogoList(); drawScene();
  });
  $('deleteLogoBtn').addEventListener('click', () => {
    const logo = selectedLogo(); if (!logo) return;
    state.logos = state.logos.filter(x => x.id !== logo.id); URL.revokeObjectURL(logo.url); selectLogo(null); renderLogoList(); drawScene();
  });

  function restoreVersion(index) {
    if (index < 0 || index >= state.versions.length) return;
    state.baseImage = state.versions[index];
    state.versions = state.versions.slice(0, index + 1);
    $('versionMeta').textContent = `Version ${state.versions.length}${index === 0 ? ' · original' : ' · AI paint'}`;
    drawScene(); updateButtons();
  }

  $('undoBtn').addEventListener('click', () => restoreVersion(state.versions.length - 2));
  $('resetBtn').addEventListener('click', () => restoreVersion(0));

  function sceneImageData() {
    drawScene(true);
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
    drawScene(false);
    return pixels;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1200);
  }

  $('pngBtn').addEventListener('click', () => {
    if (!state.baseImage) return;
    drawScene(true);
    canvas.toBlob(blob => {
      drawScene(false);
      if (blob) downloadBlob(blob, `${state.templateName}-pitmark.png`);
    }, 'image/png');
  });

  function encodeTga(imageData) {
    const { width, height, data } = imageData;
    const out = new Uint8Array(18 + width * height * 4);
    out[2] = 2;
    out[12] = width & 255; out[13] = (width >> 8) & 255;
    out[14] = height & 255; out[15] = (height >> 8) & 255;
    out[16] = 32; out[17] = 8;
    let o = 18;
    for (let y = height - 1; y >= 0; y--) {
      for (let x = 0; x < width; x++) {
        const i = (y * width + x) * 4;
        out[o++] = data[i + 2]; out[o++] = data[i + 1]; out[o++] = data[i]; out[o++] = data[i + 3];
      }
    }
    return new Blob([out], { type: 'application/octet-stream' });
  }

  $('tgaBtn').addEventListener('click', () => {
    if (!state.baseImage) return;
    const blob = encodeTga(sceneImageData());
    downloadBlob(blob, `${state.templateName}-pitmark.tga`);
  });

  $('templateInput').addEventListener('change', ev => loadTemplate(ev.target.files[0]));
  $('logoInput').addEventListener('change', ev => addLogos(ev.target.files));
  $('generateBtn').addEventListener('click', generate);
  $('fitBtn').addEventListener('click', () => { state.fit = true; updateDisplay(); });
  $('actualBtn').addEventListener('click', () => { state.fit = false; updateDisplay(); });
  window.addEventListener('resize', () => state.fit && updateDisplay());

  updateButtons();
})();
