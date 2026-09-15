(() => {
  'use strict';

  const nativeFetch = window.fetch.bind(window);
  const CHUNK_BYTES = 768 * 1024;
  const MAX_TEMPLATE_BYTES = 150 * 1024 * 1024;
  const IMPORT_PATH = '/api/control/content/paint-studio/psd/import';
  const RENDER_PATH = '/api/control/content/paint-studio/psd/render';
  const CHUNK_PATH = '/api/control/content/paint-studio/psd/chunk';
  const COMPLETE_PATH = '/api/control/content/paint-studio/psd/complete';
  const RENDER_UPLOAD_PATH = '/api/control/content/paint-studio/psd/render-upload';

  const staged = { uploadId: '', fileName: '', fileSize: 0 };

  const setTransportStatus = text => {
    const el = document.getElementById('status');
    if (!el) return;
    el.textContent = text;
    el.className = 'status busy';
  };

  const errorDetail = async (response, fallback) => {
    try {
      const data = await response.clone().json();
      return data.detail || fallback;
    } catch (_) {
      return fallback;
    }
  };

  const pathOf = input => {
    try {
      const raw = typeof input === 'string' ? input : input.url;
      return new URL(raw, window.location.href).pathname;
    } catch (_) {
      return '';
    }
  };

  const realTemplateName = file => {
    const name = String(file && file.name || 'template.zip');
    return name.toLowerCase().endsWith('.zip.psd') ? name.slice(0, -4) : name;
  };

  function enableZipSelection() {
    const input = document.getElementById('templateInput');
    if (!input || input.dataset.zipBridge) return;
    input.dataset.zipBridge = '1';
    input.addEventListener('change', () => {
      const original = input.files && input.files[0];
      if (!original || !original.name.toLowerCase().endsWith('.zip')) return;
      try {
        const proxy = new File([original], `${original.name}.psd`, {
          type: original.type || 'application/zip',
          lastModified: original.lastModified,
        });
        const transfer = new DataTransfer();
        transfer.items.add(proxy);
        input.files = transfer.files;
      } catch (_) {
        // Modern Chromium supports File/DataTransfer. If a browser does not,
        // the main engine will surface its normal file-type error.
      }
    });
  }

  async function uploadTemplateInChunks(file) {
    if (!(file instanceof File)) throw new Error('Choose an iRacing template ZIP or PSD.');
    const filename = realTemplateName(file);
    const lower = filename.toLowerCase();
    const allowed = ['.zip', '.psd', '.png', '.tga', '.jpg', '.jpeg', '.webp'].some(ext => lower.endsWith(ext));
    if (!allowed) throw new Error('Choose an iRacing template ZIP, PSD, PNG, TGA, JPG, or WEBP.');
    if (!file.size) throw new Error('The selected template file is empty.');
    if (file.size > MAX_TEMPLATE_BYTES) {
      const mb = (file.size / (1024 * 1024)).toFixed(1);
      throw new Error(`This template is ${mb} MB. Paint Studio supports template files up to 150 MB.`);
    }

    const uploadId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const total = Math.ceil(file.size / CHUNK_BYTES);
    for (let index = 0; index < total; index += 1) {
      const start = index * CHUNK_BYTES;
      const end = Math.min(file.size, start + CHUNK_BYTES);
      const chunk = file.slice(start, end);
      const percent = Math.max(1, Math.round(((index + 1) / total) * 90));
      setTransportStatus(`Uploading template… ${percent}%`);
      const params = new URLSearchParams({
        upload_id: uploadId,
        filename,
        file_size: String(file.size),
        index: String(index),
        total: String(total),
      });
      let response;
      try {
        response = await nativeFetch(`${CHUNK_PATH}?${params}`, {
          method: 'POST',
          body: chunk,
          headers: { 'Content-Type': 'application/octet-stream' },
          credentials: 'same-origin',
          cache: 'no-store',
        });
      } catch (err) {
        throw new Error(`Template upload failed on chunk ${index + 1}/${total}: ${err && err.message ? err.message : 'network error'}`);
      }
      if (!response.ok) throw new Error(await errorDetail(response, `Template upload failed (${response.status})`));
    }

    setTransportStatus(lower.endsWith('.zip') ? 'Opening iRacing ZIP…' : 'Preparing template…');
    const complete = await nativeFetch(COMPLETE_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: uploadId }),
      credentials: 'same-origin',
      cache: 'no-store',
    });
    if (!complete.ok) throw new Error(await errorDetail(complete, `Template import failed (${complete.status})`));

    staged.uploadId = uploadId;
    staged.fileName = filename;
    staged.fileSize = file.size;
    return complete;
  }

  async function rerenderStagedTemplate(form) {
    if (!staged.uploadId) return null;
    const file = form.get('psd');
    if (!(file instanceof File)) return null;
    if (realTemplateName(file) !== staged.fileName || file.size !== staged.fileSize) return null;
    let overrides = {};
    try { overrides = JSON.parse(String(form.get('role_overrides_json') || '{}')); } catch (_) {}
    setTransportStatus('Updating template roles…');
    return nativeFetch(RENDER_UPLOAD_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: staged.uploadId, role_overrides: overrides }),
      credentials: 'same-origin',
      cache: 'no-store',
    });
  }

  enableZipSelection();

  window.fetch = async function pitmarkPaintStudioFetch(input, init = {}) {
    const path = pathOf(input);
    if (path === IMPORT_PATH && init && init.body instanceof FormData) {
      const file = init.body.get('psd');
      if (file instanceof File) return uploadTemplateInChunks(file);
    }
    if (path === RENDER_PATH && init && init.body instanceof FormData) {
      const response = await rerenderStagedTemplate(init.body);
      if (response) return response;
    }
    return nativeFetch(input, init);
  };

  window.__PITMARK_PAINT_STUDIO_UPLOAD_TRANSPORT__ = { version: 2, chunkBytes: CHUNK_BYTES, zipFirst: true };
})();
