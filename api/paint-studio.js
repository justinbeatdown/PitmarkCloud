(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const canvas = $('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const stage = $('stage');

  const state = {
    sourceMode: 'none',
    psdFile: null,
    templateFile: null,
    templateName: 'paint',
    baseImage: null,
    guideImage: null,
    overlayImage: null,
    hasGuide: false,
    hasOverlay: false,
    guideVisible: true,
    layerManifest: [],
    roleOverrides: {},
    versions: [],
    logos: [],
    selectedLogoId: null,
    fit: true,
    dragging: null,
    roleBusy: false,
  };

  const setStatus = (text, kind = '') => {
    const el = $('status');
    el.textContent = text;
    el.className = `status ${kind}`.trim();
  };

  const baseName = name => (name || 'paint').replace(/\.[^.]+$/, '').replace(/[^a-z0-9_-]+/gi, '-');

  const imageFromBlob = blob => new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => resolve({ img, url, blob });
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Could not read image.'));
    };
    img.src = url;
  });

  const imageFromFile = file => imageFromBlob(file);

  function base64PngToBlob(encoded) {
    const binary = atob(encoded || '');
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: 'image/png' });
  }

  const imageFromBase64Png = encoded => imageFromBlob(base64PngToBlob(encoded));

  function revokeAsset(asset) {
    if (asset && asset.url) URL.revokeObjectURL(asset.url);
  }

  function revokeVersions(keep = null) {
    state.versions.forEach(asset => {
      if (asset && asset !== keep) revokeAsset(asset);
    });
  }

  function clearTemplateAssets() {
    revokeVersions();
    revokeAsset(state.guideImage);
    revokeAsset(state.overlayImage);
    state.logos.forEach(logo => revokeAsset(logo));
  }

  function updateButtons() {
    const loaded = !!state.baseImage;
    $('generateBtn').disabled = !loaded;
    $('resetBtn').disabled = !loaded;
    $('undoBtn').disabled = state.versions.length <= 1;
    $('pngBtn').disabled = !loaded;
    $('tgaBtn').disabled = !loaded;
    $('guideToggleBtn').disabled = !(loaded && state.hasGuide);
    $('guideToggleBtn').classList.toggle('active', !!(state.hasGuide && state.guideVisible));
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

  function drawAsset(asset) {
    if (asset && asset.img) ctx.drawImage(asset.img, 0, 0, canvas.width, canvas.height);
  }

  function drawScene(forExport = false) {
    if (!state.baseImage) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawAsset(state.baseImage);
    if (!forExport && state.hasGuide && state.guideVisible) drawAsset(state.guideImage);
    if (state.hasOverlay) drawAsset(state.overlayImage);

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
      thumb.className = 'logo-thumb';
      thumb.src = logo.url;
      thumb.alt = '';
      const name = document.createElement('div');
      name.className = 'logo-name';
      name.textContent = logo.name;
      const eye = document.createElement('div');
      eye.className = 'logo-eye';
      eye.textContent = logo.visible ? 'ON' : 'OFF';
      eye.title = 'Toggle visibility';
      eye.addEventListener('click', ev => {
        ev.stopPropagation();
        logo.visible = !logo.visible;
        renderLogoList();
        drawScene();
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

  function roleLabel(role) {
    return ({ paint: 'Paint', guide: 'Guide', overlay: 'Overlay', ignore: 'Ignore' })[role] || role;
  }

  function setRoleControlsDisabled(disabled) {
    document.querySelectorAll('.layer-role').forEach(select => { select.disabled = disabled; });
  }

  function createLayerNode(node, depth = 0) {
    const shell = document.createElement('div');
    shell.className = `layer-node${node.effective_visible === false ? ' dimmed' : ''}`;

    const row = document.createElement('div');
    row.className = 'layer-row';
    row.dataset.role = node.role;

    const info = document.createElement('div');
    info.className = 'layer-name';
    info.title = node.name;
    const title = document.createElement('span');
    title.textContent = `${node.children && node.children.length ? '▾ ' : ''}${node.name}`;
    const meta = document.createElement('span');
    meta.className = 'layer-meta';
    meta.textContent = `${node.kind || 'layer'}${node.visible === false ? ' · hidden' : ''}`;
    info.append(title, meta);

    const select = document.createElement('select');
    select.className = 'layer-role';
    select.dataset.layerId = node.id;
    const hasOverride = Object.prototype.hasOwnProperty.call(state.roleOverrides, node.id);
    const auto = document.createElement('option');
    auto.value = '__auto__';
    auto.textContent = `Auto · ${roleLabel(node.role)}`;
    auto.selected = !hasOverride;
    select.append(auto);
    ['paint', 'guide', 'overlay', 'ignore'].forEach(role => {
      const option = document.createElement('option');
      option.value = role;
      option.textContent = roleLabel(role);
      option.selected = hasOverride && state.roleOverrides[node.id] === role;
      select.append(option);
    });
    select.disabled = state.roleBusy;
    select.addEventListener('change', async () => {
      if (select.value === '__auto__') delete state.roleOverrides[node.id];
      else state.roleOverrides[node.id] = select.value;
      await rerenderPsd();
    });

    row.append(info, select);
    shell.append(row);

    if (node.children && node.children.length) {
      const children = document.createElement('div');
      children.className = 'layer-children';
      node.children.forEach(child => children.append(createLayerNode(child, depth + 1)));
      shell.append(children);
    }
    return shell;
  }

  function renderLayerTree() {
    const section = $('psdLayersSection');
    const tree = $('layerTree');
    const hasPsd = state.sourceMode === 'psd' && state.layerManifest.length;
    section.classList.toggle('hidden', !hasPsd);
    tree.innerHTML = '';
    if (!hasPsd) return;
    state.layerManifest.forEach(node => tree.append(createLayerNode(node)));
  }

  async function assetsFromPsdPayload(data) {
    const [paint, guide, overlay] = await Promise.all([
      imageFromBase64Png(data.paint_png),
      imageFromBase64Png(data.guide_png),
      imageFromBase64Png(data.overlay_png),
    ]);
    return { paint, guide, overlay };
  }

  function commitPsdPayload(file, data, assets, { preserveLogos = false } = {}) {
    const oldVersions = state.versions.slice();
    const oldGuide = state.guideImage;
    const oldOverlay = state.overlayImage;
    const oldLogos = preserveLogos ? [] : state.logos.slice();

    state.sourceMode = 'psd';
    state.psdFile = file;
    state.templateFile = file;
    state.templateName = baseName(file.name);
    state.baseImage = assets.paint;
    state.guideImage = assets.guide;
    state.overlayImage = assets.overlay;
    state.hasGuide = !!data.has_guide;
    state.hasOverlay = !!data.has_overlay;
    state.guideVisible = true;
    state.layerManifest = data.layers || [];
    state.versions = [assets.paint];
    if (!preserveLogos) {
      state.logos = [];
      state.selectedLogoId = null;
    }

    canvas.width = Number(data.width) || assets.paint.img.naturalWidth;
    canvas.height = Number(data.height) || assets.paint.img.naturalHeight;
    $('emptyStage').classList.add('hidden');
    $('templateMeta').textContent = `${file.name} · layered PSD · ${canvas.width} × ${canvas.height}`;
    $('canvasMeta').textContent = `${canvas.width} × ${canvas.height}px · PSD-aware`;
    $('versionMeta').textContent = 'Version 1 · PSD paint';

    oldVersions.forEach(revokeAsset);
    revokeAsset(oldGuide);
    revokeAsset(oldOverlay);
    oldLogos.forEach(revokeAsset);

    renderLayerTree();
    renderLogoList();
    selectLogo(state.selectedLogoId);
    drawScene();
    updateDisplay();
    updateButtons();
  }

  async function apiError(response, fallback) {
    try {
      const data = await response.json();
      return data.detail || fallback;
    } catch (_) {
      return fallback;
    }
  }

  async function loadPsd(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.psd')) {
      setStatus('Choose an iRacing .psd template', 'error');
      return;
    }
    setStatus('Reading PSD layers…', 'busy');
    try {
      const form = new FormData();
      form.append('psd', file, file.name);
      const response = await fetch('/api/control/content/paint-studio/psd/import', { method: 'POST', body: form });
      if (!response.ok) throw new Error(await apiError(response, `PSD import failed (${response.status})`));
      const data = await response.json();
      const assets = await assetsFromPsdPayload(data);
      state.roleOverrides = {};
      commitPsdPayload(file, data, assets);
      setStatus('PSD ready');
    } catch (err) {
      setStatus(err.message || 'PSD import failed', 'error');
    }
  }

  async function rerenderPsd() {
    if (!state.psdFile || state.roleBusy) return;
    state.roleBusy = true;
    setRoleControlsDisabled(true);
    setStatus('Rebuilding PSD roles…', 'busy');
    try {
      const form = new FormData();
      form.append('psd', state.psdFile, state.psdFile.name);
      form.append('role_overrides_json', JSON.stringify(state.roleOverrides));
      const response = await fetch('/api/control/content/paint-studio/psd/render', { method: 'POST', body: form });
      if (!response.ok) throw new Error(await apiError(response, `PSD re-render failed (${response.status})`));
      const data = await response.json();
      const assets = await assetsFromPsdPayload(data);
      commitPsdPayload(state.psdFile, data, assets, { preserveLogos: true });
      setStatus('Layer roles updated · paint reset');
    } catch (err) {
      setStatus(err.message || 'PSD re-render failed', 'error');
      renderLayerTree();
    } finally {
      state.roleBusy = false;
      setRoleControlsDisabled(false);
    }
  }

  async function loadLegacyTemplate(file) {
    if (!file) return;
    setStatus('Loading flattened template…', 'busy');
    try {
      const asset = await imageFromFile(file);
      clearTemplateAssets();
      state.sourceMode = 'raster';
      state.psdFile = null;
      state.templateFile = file;
      state.templateName = baseName(file.name);
      state.baseImage = asset;
      state.guideImage = null;
      state.overlayImage = null;
      state.hasGuide = false;
      state.hasOverlay = false;
      state.layerManifest = [];
      state.roleOverrides = {};
      state.versions = [asset];
      state.logos = [];
      state.selectedLogoId = null;
      canvas.width = asset.img.naturalWidth;
      canvas.height = asset.img.naturalHeight;
      $('emptyStage').classList.add('hidden');
      $('templateMeta').textContent = `${file.name} · legacy flattened · ${canvas.width} × ${canvas.height}`;
      $('canvasMeta').textContent = `${canvas.width} × ${canvas.height}px · flattened`;
      $('versionMeta').textContent = 'Version 1 · original';
      renderLayerTree();
      renderLogoList();
      selectLogo(null);
      drawScene();
      updateDisplay();
      updateButtons();
      setStatus('Flattened template ready');
    } catch (err) {
      setStatus(err.message || 'Template failed', 'error');
    }
  }

  function rasterBlob(asset) {
    return new Promise((resolve, reject) => {
      if (!asset || !canvas.width || !canvas.height) return reject(new Error('No image is loaded.'));
      const scratch = document.createElement('canvas');
      scratch.width = canvas.width;
      scratch.height = canvas.height;
      const sctx = scratch.getContext('2d');
      sctx.clearRect(0, 0, scratch.width, scratch.height);
      sctx.drawImage(asset.img, 0, 0, scratch.width, scratch.height);
      scratch.toBlob(blob => blob ? resolve(blob) : reject(new Error('Could not prepare image.')), 'image/png');
    });
  }

  async function generate() {
    const prompt = $('prompt').value.trim();
    if (!prompt) {
      setStatus('Write a design brief first', 'error');
      $('prompt').focus();
      return;
    }
    $('generateBtn').disabled = true;
    setStatus('Generating paint pass…', 'busy');
    try {
      const paint = await rasterBlob(state.baseImage);
      const form = new FormData();
      form.append('template', paint, `${state.templateName}-paint.png`);
      form.append('prompt', prompt);
      form.append('quality', $('quality').value);

      if (state.sourceMode === 'psd' && state.hasGuide && state.guideImage) {
        const guide = await rasterBlob(state.guideImage);
        form.append('guide', guide, `${state.templateName}-guide.png`);
      }
      const ref = $('referenceInput').files[0];
      if (ref) form.append('reference', ref, ref.name);

      const response = await fetch('/api/control/content/paint-studio/generate', { method: 'POST', body: form });
      if (!response.ok) throw new Error(await apiError(response, `Generation failed (${response.status})`));
      const blob = await response.blob();
      const asset = await imageFromBlob(blob);
      state.baseImage = asset;
      state.versions.push(asset);
      $('versionMeta').textContent = `Version ${state.versions.length} · AI paint`;
      drawScene();
      updateButtons();
      setStatus('Paint pass ready');
    } catch (err) {
      setStatus(err.message || 'Generation failed', 'error');
    } finally {
      updateButtons();
    }
  }

  async function addLogos(files) {
    if (!state.baseImage) {
      setStatus('Load a template before adding logos', 'error');
      return;
    }
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
    renderLogoList();
    drawScene();
  }

  function pointFromEvent(ev) {
    const r = canvas.getBoundingClientRect();
    return {
      x: (ev.clientX - r.left) * canvas.width / Math.max(1, r.width),
      y: (ev.clientY - r.top) * canvas.height / Math.max(1, r.height),
    };
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
    const p = pointFromEvent(ev);
    const logo = hitLogo(p);
    if (!logo) {
      selectLogo(null);
      return;
    }
    selectLogo(logo.id);
    state.dragging = { id: logo.id, dx: p.x - logo.x, dy: p.y - logo.y };
    canvas.setPointerCapture(ev.pointerId);
  });

  canvas.addEventListener('pointermove', ev => {
    if (!state.dragging) return;
    const logo = selectedLogo();
    if (!logo || logo.id !== state.dragging.id) return;
    const p = pointFromEvent(ev);
    logo.x = p.x - state.dragging.dx;
    logo.y = p.y - state.dragging.dy;
    drawScene();
  });

  canvas.addEventListener('pointerup', ev => {
    state.dragging = null;
    try { canvas.releasePointerCapture(ev.pointerId); } catch (_) {}
  });
  canvas.addEventListener('pointercancel', () => { state.dragging = null; });

  $('scaleRange').addEventListener('input', ev => {
    const logo = selectedLogo();
    if (!logo) return;
    logo.scale = Number(ev.target.value) / 100;
    logo.w = logo.baseW * logo.scale;
    logo.h = logo.w * logo.ratio;
    drawScene();
  });

  $('opacityRange').addEventListener('input', ev => {
    const logo = selectedLogo();
    if (!logo) return;
    logo.opacity = Number(ev.target.value) / 100;
    drawScene();
  });

  $('frontBtn').addEventListener('click', () => {
    const logo = selectedLogo();
    if (!logo) return;
    state.logos = state.logos.filter(x => x.id !== logo.id);
    state.logos.push(logo);
    renderLogoList();
    drawScene();
  });

  $('deleteLogoBtn').addEventListener('click', () => {
    const logo = selectedLogo();
    if (!logo) return;
    state.logos = state.logos.filter(x => x.id !== logo.id);
    revokeAsset(logo);
    selectLogo(null);
    renderLogoList();
    drawScene();
  });

  function restoreVersion(index) {
    if (index < 0 || index >= state.versions.length) return;
    const keep = state.versions.slice(0, index + 1);
    const removed = state.versions.slice(index + 1);
    removed.forEach(revokeAsset);
    state.versions = keep;
    state.baseImage = keep[index];
    $('versionMeta').textContent = `Version ${state.versions.length}${index === 0 ? (state.sourceMode === 'psd' ? ' · PSD paint' : ' · original') : ' · AI paint'}`;
    drawScene();
    updateButtons();
  }

  $('undoBtn').addEventListener('click', () => restoreVersion(state.versions.length - 2));
  $('resetBtn').addEventListener('click', () => restoreVersion(0));

  $('guideToggleBtn').addEventListener('click', () => {
    if (!state.hasGuide) return;
    state.guideVisible = !state.guideVisible;
    updateButtons();
    drawScene();
  });

  function sceneImageData() {
    drawScene(true);
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
    drawScene(false);
    return pixels;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.append(a);
    a.click();
    a.remove();
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
    out[12] = width & 255;
    out[13] = (width >> 8) & 255;
    out[14] = height & 255;
    out[15] = (height >> 8) & 255;
    out[16] = 32;
    out[17] = 8;
    let o = 18;
    for (let y = height - 1; y >= 0; y--) {
      for (let x = 0; x < width; x++) {
        const i = (y * width + x) * 4;
        out[o++] = data[i + 2];
        out[o++] = data[i + 1];
        out[o++] = data[i];
        out[o++] = data[i + 3];
      }
    }
    return new Blob([out], { type: 'application/octet-stream' });
  }

  $('tgaBtn').addEventListener('click', () => {
    if (!state.baseImage) return;
    const blob = encodeTga(sceneImageData());
    downloadBlob(blob, `${state.templateName}-pitmark.tga`);
  });

  $('templateInput').addEventListener('change', ev => loadPsd(ev.target.files[0]));
  $('legacyTemplateInput').addEventListener('change', ev => loadLegacyTemplate(ev.target.files[0]));
  $('logoInput').addEventListener('change', ev => addLogos(ev.target.files));
  $('generateBtn').addEventListener('click', generate);
  $('fitBtn').addEventListener('click', () => { state.fit = true; updateDisplay(); });
  $('actualBtn').addEventListener('click', () => { state.fit = false; updateDisplay(); });
  window.addEventListener('resize', () => state.fit && updateDisplay());

  renderLayerTree();
  updateButtons();
})();
