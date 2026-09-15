(() => {
  'use strict';

  const nativeFetch = window.fetch.bind(window);
  const PSD_CHUNK_BYTES = 768 * 1024;
  const MAX_PSD_BYTES = 80 * 1024 * 1024;
  const IMPORT_PATH = '/api/control/content/paint-studio/psd/import';
  const RENDER_PATH = '/api/control/content/paint-studio/psd/render';
  const CHUNK_PATH = '/api/control/content/paint-studio/psd/chunk';
  const COMPLETE_PATH = '/api/control/content/paint-studio/psd/complete';
  const RENDER_UPLOAD_PATH = '/api/control/content/paint-studio/psd/render-upload';

  const staged = {
    uploadId: '',
    fileName: '',
    fileSize: 0,
  };

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

  async function uploadPsdInChunks(file) {
    if (!(file instanceof File)) throw new Error('Choose an original iRacing .psd template.');
    if (!file.name.toLowerCase().endsWith('.psd')) throw new Error('Choose an original iRacing .psd template.');
    if (!file.size) throw new Error('PSD file is empty.');
    if (file.size > MAX_PSD_BYTES) {
      const mb = (file.size / (1024 * 1024)).toFixed(1);
      throw new Error(`This PSD is ${mb} MB. Paint Studio currently supports PSDs up to 80 MB.`);
    }

    const uploadId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const total = Math.ceil(file.size / PSD_CHUNK_BYTES);

    for (let index = 0; index < total; index += 1) {
      const start = index * PSD_CHUNK_BYTES;
      const end = Math.min(file.size, start + PSD_CHUNK_BYTES);
      const chunk = file.slice(start, end);
      const percent = Math.max(1, Math.round(((index + 1) / total) * 90));
      setTransportStatus(`Uploading PSD… ${percent}%`);

      const params = new URLSearchParams({
        upload_id: uploadId,
        filename: file.name,
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
        throw new Error(`PSD upload failed on chunk ${index + 1}/${total}: ${err && err.message ? err.message : 'network error'}`);
      }
      if (!response.ok) {
        throw new Error(await errorDetail(response, `PSD upload failed (${response.status})`));
      }
    }

    setTransportStatus('Parsing PSD…');
    const complete = await nativeFetch(COMPLETE_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: uploadId }),
      credentials: 'same-origin',
      cache: 'no-store',
    });
    if (!complete.ok) {
      throw new Error(await errorDetail(complete, `PSD import failed (${complete.status})`));
    }

    staged.uploadId = uploadId;
    staged.fileName = file.name;
    staged.fileSize = file.size;
    return complete;
  }

  async function rerenderStagedPsd(form) {
    if (!staged.uploadId) return null;
    const psd = form.get('psd');
    if (!(psd instanceof File)) return null;
    if (psd.name !== staged.fileName || psd.size !== staged.fileSize) return null;

    let overrides = {};
    try {
      overrides = JSON.parse(String(form.get('role_overrides_json') || '{}'));
    } catch (_) {
      overrides = {};
    }

    setTransportStatus('Updating template roles…');
    return nativeFetch(RENDER_UPLOAD_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: staged.uploadId, role_overrides: overrides }),
      credentials: 'same-origin',
      cache: 'no-store',
    });
  }

  window.fetch = async function pitmarkPaintStudioFetch(input, init = {}) {
    const path = pathOf(input);
    if (path === IMPORT_PATH && init && init.body instanceof FormData) {
      const file = init.body.get('psd');
      if (file instanceof File) return uploadPsdInChunks(file);
    }
    if (path === RENDER_PATH && init && init.body instanceof FormData) {
      const response = await rerenderStagedPsd(init.body);
      if (response) return response;
    }
    return nativeFetch(input, init);
  };

  window.__PITMARK_PAINT_STUDIO_UPLOAD_TRANSPORT__ = {
    version: 1,
    chunkBytes: PSD_CHUNK_BYTES,
  };
})();
