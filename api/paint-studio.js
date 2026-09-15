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
    assets: [],
    logos: [],
    selectedLogoId: null,
    fit: true,
    dragging: null,
    roleBusy: false,
    generating: false,
  };

  const setStatus = (text, kind = '') => {
    const el = $('status');
    el.textContent = text;
    el.className = `status ${kind}`.trim();
  };

  const baseName = name => (name || 'paint').replace(/\.[^.]+$/, '').replace(/[^a-z0-9_-]+/gi, '-');
  const makeId = () => crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;

  const imageFromBlob = blob => new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => resolve({ img, url, blob });
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Could not read image.')); };
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

  function revokeAsset(asset) { if (asset && asset.url) URL.revokeObjectURL(asset.url); }
  function revokeVersions(keep = null) { state.versions.forEach(asset => { if (asset && asset !== keep) revokeAsset(asset); }); }
  function clearTemplateAssets() {
    revokeVersions();
    revokeAsset(state.guideImage);
    revokeAsset(state.overlayImage);
    state.logos = [];
    state.selectedLogoId = null;
  }

  function appendChat(text, type = 'assistant') {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${type}`;
    bubble.textContent = text;
    $('conversationHistory').append(bubble);
    $('conversationHistory').scrollTop = $('conversationHistory').scrollHeight;
  }

  function updateButtons() {
    const loaded = !!state.baseImage;
    const hasPrompt = !!$('prompt').value.trim();
    $('generateBtn').disabled = !(loaded && hasPrompt) || state.generating;
    $('generateBtn').textContent = state.generating ? 'Generating…' : (state.versions.length > 1 ? 'Send revision' : 'Generate paint');
    $('resetBtn').disabled = !loaded || state.versions.length <= 1;
    $('undoBtn').disabled = state.versions.length <= 1;
    $('pngBtn').disabled = !loaded;
    $('tgaBtn').disabled = !loaded;
    $('guideToggleBtn').disabled = !(loaded && state.hasGuide);
    $('guideToggleBtn').classList.toggle('active', !!(state.hasGuide && state.guideVisible));
    document.querySelectorAll('[data-place-asset]').forEach(btn => { btn.disabled = !loaded; });
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

  function selectedLogo() { return state.logos.find(x => x.id === state.selectedLogoId) || null; }
  function drawAsset(asset) { if (asset && asset.img) ctx.drawImage(asset.img, 0, 0, canvas.width, canvas.height); }

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

  function renderAssets() {
    const list = $('assetList');
    list.innerHTML = '';
    if (!state.assets.length) {
      list.innerHTML = '<div class="empty">No attachments yet</div>';
      updateButtons();
      return;
    }
    state.assets.forEach(asset => {
      const row = document.createElement('div');
      row.className = 'asset-item';
      const thumb = document.createElement('img');
      thumb.className = 'asset-thumb';
      thumb.src = asset.url;
      thumb.alt = '';
      const center = document.createElement('div');
      const name = document.createElement('div');
      name.className = 'asset-name';
      name.textContent = asset.name;
      const meta = document.createElement('div');
      meta.className = 'asset-meta';
      for (const role of ['reference', 'logo']) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = `asset-role${asset.role === role ? ' active' : ''}`;
        b.textContent = role === 'reference' ? 'Reference' : 'Logo';
        b.addEventListener('click', () => { asset.role = role; renderAssets(); });
        meta.append(b);
      }
      center.append(name, meta);
      const actions = document.createElement('div');
      actions.className = 'asset-actions';
      if (asset.role === 'logo') {
        const place = document.createElement('button');
        place.type = 'button';
        place.className = 'asset-action';
        place.dataset.placeAsset = asset.id;
        place.textContent = 'Place exact';
        place.disabled = !state.baseImage;
        place.addEventListener('click', () => placeExactLogo(asset.id));
        actions.append(place);
      }
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'asset-action remove';
      remove.textContent = 'Remove';
      remove.addEventListener('click', () => removeAttachment(asset.id));
      actions.append(remove);
      row.append(thumb, center, actions);
      list.append(row);
    });
    updateButtons();
  }

  async function addAssets(files) {
    for (const file of [...files]) {
      try {
        const image = await imageFromFile(file);
        const role = /logo|sponsor|badge|mark/i.test(file.name) ? 'logo' : 'reference';
        state.assets.push({ id: makeId(), name: file.name, file, role, img: image.img, url: image.url });
      } catch (_) {
        setStatus(`Could not load ${file.name}`, 'error');
      }
    }
    renderAssets();
    if (state.assets.length) setStatus(`${state.assets.length} attachment${state.assets.length === 1 ? '' : 's'} ready`);
  }

  function removeAttachment(id) {
    const asset = state.assets.find(x => x.id === id);
    if (!asset) return;
    state.logos = state.logos.filter(logo => logo.sourceAssetId !== id);
    if (selectedLogo() && selectedLogo().sourceAssetId === id) state.selectedLogoId = null;
    revokeAsset(asset);
    state.assets = state.assets.filter(x => x.id !== id);
    renderAssets();
    selectLogo(state.selectedLogoId);
    drawScene();
  }

  function placeExactLogo(assetId) {
    if (!state.baseImage) return;
    const asset = state.assets.find(x => x.id === assetId);
    if (!asset) return;
    const ratio = asset.img.naturalHeight / Math.max(1, asset.img.naturalWidth);
    const baseW = canvas.width * .20;
    const logo = {
      id: makeId(), sourceAssetId: asset.id, name: asset.name, img: asset.img,
      x: canvas.width * .5 - baseW * .5, y: canvas.height * .5 - baseW * ratio * .5,
      baseW, ratio, scale: 1, w: baseW, h: baseW * ratio, opacity: 1, visible: true,
    };
    state.logos.push(logo);
    selectLogo(logo.id);
    drawScene();
  }

  function selectLogo(id) {
    state.selectedLogoId = id;
    const logo = selectedLogo();
    $('selectedEmpty').classList.toggle('hidden', !!logo);
    $('logoControls').classList.toggle('hidden', !logo);
    if (logo) {
      $('selectedLogoName').textContent = logo.name;
      $('scaleRange').value = String(Math.round(logo.scale * 100));
      $('opacityRange').value = String(Math.round(logo.opacity * 100));
    }
    drawScene();
  }

  function roleLabel(role) { return ({ paint:'Paint', guide:'Guide', overlay:'Overlay', ignore:'Ignore' })[role] || role; }
  function setRoleControlsDisabled(disabled) { document.querySelectorAll('.layer-role').forEach(select => { select.disabled = disabled; }); }

  function createLayerNode(node) {
    const shell = document.createElement('div');
    shell.className = `layer-node${node.effective_visible === false ? ' dimmed' : ''}`;
    const row = document.createElement('div');
    row.className = 'layer-row';
    const info = document.createElement('div');
    info.className = 'layer-name';
    const title = document.createElement('span');
    title.textContent = `${node.children && node.children.length ? '▾ ' : ''}${node.name}`;
    const meta = document.createElement('span');
    meta.className = 'layer-meta';
    meta.textContent = `${node.kind || 'layer'}${node.visible === false ? ' · hidden' : ''}`;
    info.append(title, meta);
    const select = document.createElement('select');
    select.className = 'layer-role';
    const hasOverride = Object.prototype.hasOwnProperty.call(state.roleOverrides, node.id);
    const auto = document.createElement('option');
    auto.value = '__auto__'; auto.textContent = `Auto · ${roleLabel(node.role)}`; auto.selected = !hasOverride;
    select.append(auto);
    ['paint','guide','overlay','ignore'].forEach(role => {
      const option = document.createElement('option');
      option.value = role; option.textContent = roleLabel(role); option.selected = hasOverride && state.roleOverrides[node.id] === role;
      select.append(option);
    });
    select.disabled = state.roleBusy;
    select.addEventListener('change', async () => {
      if (select.value === '__auto__') delete state.roleOverrides[node.id]; else state.roleOverrides[node.id] = select.value;
      await rerenderPsd();
    });
    row.append(info, select); shell.append(row);
    if (node.children && node.children.length) {
      const children = document.createElement('div'); children.className = 'layer-children';
      node.children.forEach(child => children.append(createLayerNode(child))); shell.append(children);
    }
    return shell;
  }

  function renderLayerTree() {
    const section = $('psdLayersSection'); const tree = $('layerTree');
    const hasPsd = state.sourceMode === 'psd' && state.layerManifest.length;
    section.classList.toggle('hidden', !hasPsd); tree.innerHTML = '';
    if (!hasPsd) return;
    state.layerManifest.forEach(node => tree.append(createLayerNode(node)));
  }

  async function assetsFromPsdPayload(data) {
    const [paint, guide, overlay] = await Promise.all([imageFromBase64Png(data.paint_png), imageFromBase64Png(data.guide_png), imageFromBase64Png(data.overlay_png)]);
    return { paint, guide, overlay };
  }

  function commitPsdPayload(file, data, parsed, { preservePaintHistory = false } = {}) {
    const oldVersions = state.versions.slice(); const oldGuide = state.guideImage; const oldOverlay = state.overlayImage;
    state.sourceMode = 'psd'; state.psdFile = file; state.templateFile = file; state.templateName = baseName(file.name);
    state.baseImage = parsed.paint; state.guideImage = parsed.guide; state.overlayImage = parsed.overlay;
    state.hasGuide = !!data.has_guide; state.hasOverlay = !!data.has_overlay; state.guideVisible = true; state.layerManifest = data.layers || [];
    if (!preservePaintHistory) { oldVersions.forEach(revokeAsset); state.versions = [parsed.paint]; }
    else { state.versions = [parsed.paint]; oldVersions.forEach(revokeAsset); }
    state.logos = []; state.selectedLogoId = null;
    canvas.width = Number(data.width) || parsed.paint.img.naturalWidth; canvas.height = Number(data.height) || parsed.paint.img.naturalHeight;
    $('emptyStage').classList.add('hidden');
    $('templateMeta').textContent = `${file.name} · ${canvas.width} × ${canvas.height} · PSD ready`;
    $('canvasMeta').textContent = `${canvas.width} × ${canvas.height}px · PSD-aware`;
    $('versionMeta').textContent = 'Version 1 · source paint';
    revokeAsset(oldGuide); revokeAsset(oldOverlay);
    renderLayerTree(); renderAssets(); selectLogo(null); drawScene(); updateDisplay(); updateButtons();
  }

  async function apiError(response, fallback) {
    try { const data = await response.json(); return data.detail || fallback; } catch (_) { return fallback; }
  }

  async function loadPsd(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.psd')) { setStatus('Choose an iRacing .psd template', 'error'); return; }
    setStatus('Reading PSD…', 'busy');
    try {
      const form = new FormData(); form.append('psd', file, file.name);
      const response = await fetch('/api/control/content/paint-studio/psd/import', { method:'POST', body:form });
      if (!response.ok) throw new Error(await apiError(response, `PSD import failed (${response.status})`));
      const data = await response.json(); const parsed = await assetsFromPsdPayload(data);
      state.roleOverrides = {}; commitPsdPayload(file, data, parsed); setStatus('PSD ready');
      appendChat(`Template loaded: ${file.name}. Tell me what you want painted.`, 'assistant');
    } catch (err) { setStatus(err.message || 'PSD import failed', 'error'); appendChat(err.message || 'PSD import failed', 'error'); }
  }

  async function rerenderPsd() {
    if (!state.psdFile || state.roleBusy) return;
    state.roleBusy = true; setRoleControlsDisabled(true); setStatus('Updating template roles…', 'busy');
    try {
      const form = new FormData(); form.append('psd', state.psdFile, state.psdFile.name); form.append('role_overrides_json', JSON.stringify(state.roleOverrides));
      const response = await fetch('/api/control/content/paint-studio/psd/render', { method:'POST', body:form });
      if (!response.ok) throw new Error(await apiError(response, `PSD re-render failed (${response.status})`));
      const data = await response.json(); const parsed = await assetsFromPsdPayload(data); commitPsdPayload(state.psdFile, data, parsed, { preservePaintHistory:false });
      setStatus('Template roles updated');
    } catch (err) { setStatus(err.message || 'PSD re-render failed', 'error'); renderLayerTree(); }
    finally { state.roleBusy = false; setRoleControlsDisabled(false); }
  }

  async function loadLegacyTemplate(file) {
    if (!file) return;
    setStatus('Loading flattened template…', 'busy');
    try {
      const parsed = await imageFromFile(file); clearTemplateAssets();
      state.sourceMode='raster'; state.psdFile=null; state.templateFile=file; state.templateName=baseName(file.name);
      state.baseImage=parsed; state.guideImage=null; state.overlayImage=null; state.hasGuide=false; state.hasOverlay=false; state.layerManifest=[]; state.roleOverrides={}; state.versions=[parsed];
      canvas.width=parsed.img.naturalWidth; canvas.height=parsed.img.naturalHeight; $('emptyStage').classList.add('hidden');
      $('templateMeta').textContent=`${file.name} · legacy flattened · ${canvas.width} × ${canvas.height}`; $('canvasMeta').textContent=`${canvas.width} × ${canvas.height}px · flattened`; $('versionMeta').textContent='Version 1 · original';
      renderLayerTree(); renderAssets(); drawScene(); updateDisplay(); updateButtons(); setStatus('Flattened template ready');
    } catch (err) { setStatus(err.message || 'Template failed', 'error'); }
  }

  function rasterBlob(asset) {
    return new Promise((resolve,reject) => {
      if (!asset || !canvas.width || !canvas.height) return reject(new Error('No image is loaded.'));
      const scratch=document.createElement('canvas'); scratch.width=canvas.width; scratch.height=canvas.height;
      const sctx=scratch.getContext('2d'); sctx.clearRect(0,0,scratch.width,scratch.height); sctx.drawImage(asset.img,0,0,scratch.width,scratch.height);
      scratch.toBlob(blob => blob ? resolve(blob) : reject(new Error('Could not prepare image.')), 'image/png');
    });
  }

  async function generate() {
    const prompt = $('prompt').value.trim();
    if (!state.baseImage) { setStatus('Load an iRacing PSD first', 'error'); return; }
    if (!prompt) { setStatus('Tell me what to paint first', 'error'); $('prompt').focus(); return; }
    state.generating = true; updateButtons(); setStatus(state.versions.length > 1 ? 'Applying revision…' : 'Creating paint…', 'busy'); appendChat(prompt, 'user');
    try {
      const paint = await rasterBlob(state.baseImage); const form = new FormData();
      form.append('template', paint, `${state.templateName}-paint.png`); form.append('prompt', prompt); form.append('quality', $('quality').value);
      if (state.sourceMode === 'psd' && state.hasGuide && state.guideImage) { const guide = await rasterBlob(state.guideImage); form.append('guide', guide, `${state.templateName}-guide.png`); }
      state.assets.forEach(asset => form.append('assets', asset.file, asset.name));
      form.append('asset_roles_json', JSON.stringify(state.assets.map(asset => asset.role)));
      const response = await fetch('/api/control/content/paint-studio/generate', { method:'POST', body:form });
      if (!response.ok) throw new Error(await apiError(response, `Generation failed (${response.status})`));
      const blob = await response.blob(); const next = await imageFromBlob(blob); state.baseImage = next; state.versions.push(next);
      $('versionMeta').textContent = `Version ${state.versions.length} · AI paint`; $('prompt').value=''; drawScene(); appendChat('Paint pass ready. Tell me what you want changed next.', 'assistant'); setStatus('Paint ready');
    } catch (err) { appendChat(err.message || 'Generation failed', 'error'); setStatus(err.message || 'Generation failed', 'error'); }
    finally { state.generating=false; updateButtons(); }
  }

  function pointFromEvent(ev) {
    const r=canvas.getBoundingClientRect(); return { x:(ev.clientX-r.left)*canvas.width/Math.max(1,r.width), y:(ev.clientY-r.top)*canvas.height/Math.max(1,r.height) };
  }
  function hitLogo(p) { for(let i=state.logos.length-1;i>=0;i--){const l=state.logos[i]; if(l.visible&&p.x>=l.x&&p.x<=l.x+l.w&&p.y>=l.y&&p.y<=l.y+l.h)return l;} return null; }
  canvas.addEventListener('pointerdown',ev=>{ if(!state.baseImage)return; const p=pointFromEvent(ev); const logo=hitLogo(p); if(!logo){selectLogo(null);return;} selectLogo(logo.id); state.dragging={id:logo.id,dx:p.x-logo.x,dy:p.y-logo.y}; canvas.setPointerCapture(ev.pointerId); });
  canvas.addEventListener('pointermove',ev=>{ if(!state.dragging)return; const logo=selectedLogo(); if(!logo||logo.id!==state.dragging.id)return; const p=pointFromEvent(ev); logo.x=p.x-state.dragging.dx; logo.y=p.y-state.dragging.dy; drawScene(); });
  canvas.addEventListener('pointerup',ev=>{state.dragging=null;try{canvas.releasePointerCapture(ev.pointerId);}catch(_){}}); canvas.addEventListener('pointercancel',()=>{state.dragging=null;});

  $('scaleRange').addEventListener('input',ev=>{const logo=selectedLogo();if(!logo)return;logo.scale=Number(ev.target.value)/100;logo.w=logo.baseW*logo.scale;logo.h=logo.w*logo.ratio;drawScene();});
  $('opacityRange').addEventListener('input',ev=>{const logo=selectedLogo();if(!logo)return;logo.opacity=Number(ev.target.value)/100;drawScene();});
  $('frontBtn').addEventListener('click',()=>{const logo=selectedLogo();if(!logo)return;state.logos=state.logos.filter(x=>x.id!==logo.id);state.logos.push(logo);drawScene();});
  $('deleteLogoBtn').addEventListener('click',()=>{const logo=selectedLogo();if(!logo)return;state.logos=state.logos.filter(x=>x.id!==logo.id);selectLogo(null);drawScene();});

  function restoreVersion(index) {
    if(index<0||index>=state.versions.length)return; const keep=state.versions.slice(0,index+1); const removed=state.versions.slice(index+1); removed.forEach(revokeAsset); state.versions=keep; state.baseImage=keep[index];
    $('versionMeta').textContent=`Version ${state.versions.length}${index===0?' · source paint':' · AI paint'}`; drawScene(); updateButtons();
  }
  $('undoBtn').addEventListener('click',()=>restoreVersion(state.versions.length-2)); $('resetBtn').addEventListener('click',()=>restoreVersion(0));
  $('guideToggleBtn').addEventListener('click',()=>{if(!state.hasGuide)return;state.guideVisible=!state.guideVisible;updateButtons();drawScene();});

  function sceneImageData(){drawScene(true);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);drawScene(false);return pixels;}
  function downloadBlob(blob,filename){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1200);}
  $('pngBtn').addEventListener('click',()=>{if(!state.baseImage)return;drawScene(true);canvas.toBlob(blob=>{drawScene(false);if(blob)downloadBlob(blob,`${state.templateName}-pitmark.png`);},'image/png');});
  function encodeTga(imageData){const{width,height,data}=imageData;const out=new Uint8Array(18+width*height*4);out[2]=2;out[12]=width&255;out[13]=(width>>8)&255;out[14]=height&255;out[15]=(height>>8)&255;out[16]=32;out[17]=8;let o=18;for(let y=height-1;y>=0;y--){for(let x=0;x<width;x++){const i=(y*width+x)*4;out[o++]=data[i+2];out[o++]=data[i+1];out[o++]=data[i];out[o++]=data[i+3];}}return new Blob([out],{type:'application/octet-stream'});}
  $('tgaBtn').addEventListener('click',()=>{if(!state.baseImage)return;downloadBlob(encodeTga(sceneImageData()),`${state.templateName}-pitmark.tga`);});

  $('templateInput').addEventListener('change',ev=>loadPsd(ev.target.files[0]));
  $('legacyTemplateInput').addEventListener('change',ev=>loadLegacyTemplate(ev.target.files[0]));
  $('assetInput').addEventListener('change',ev=>{addAssets(ev.target.files);ev.target.value='';});
  $('prompt').addEventListener('input',updateButtons);
  $('generateBtn').addEventListener('click',generate);
  $('fitBtn').addEventListener('click',()=>{state.fit=true;updateDisplay();}); $('actualBtn').addEventListener('click',()=>{state.fit=false;updateDisplay();});
  window.addEventListener('resize',()=>state.fit&&updateDisplay());

  window.__PITMARK_PAINT_STUDIO_BOOTED__ = true;
  renderLayerTree(); renderAssets(); updateButtons(); setStatus('Ready');
})();
