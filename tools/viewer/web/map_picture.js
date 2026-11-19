// The Map picture dialog (Map menu; LWR map packs plan, 4.2): the picture the game shows for the map on its
// mission screens, 512 x 256. An image is chosen, dropped on the dialog or taken from the 3D view; a 2:1 frame over
// it is dragged, resized by its corners or zoomed with the wheel (map_picture_crop.js has the arithmetic); beside it
// is the result as the game will show it, after DXT1 (the server sends that back). Use this picture sends the cropped
// 512 x 256 PNG to the server (tools/viewer/pictures.py keeps it with the project) and hands its SHA-256 to the page,
// which saves it with the project. The image itself never leaves the browser: only the cropped picture is sent.
import { HEIGHT, WIDTH, clampFrame, dragCorner, moveFrame, scaleSteps, sourceRect, startFrame, zoomFrame } from './map_picture_crop.js';

const at = id => `/projects/${encodeURIComponent(id)}/picture.png`;
async function failure(response) {
  const value = await response.json().catch(() => ({}));
  return new Error(value.error || `The server said ${response.status}`);
}
// The server's side (viewer.py, the project routes)
export const pictureApi = {
  /** Keep a cropped picture (a PNG blob) with the project: { sha256 }. */
  async save(id, blob) {
    const response = await fetch(at(id), { method: 'PUT', headers: { 'Content-Type': 'image/png' }, body: blob });
    if (!response.ok) throw await failure(response);
    return response.json();
  },
  async remove(id) {
    const response = await fetch(at(id), { method: 'DELETE' });
    if (!response.ok) throw await failure(response);
    return response.json();
  },
  /** A cropped picture as the game shows it, after DXT1: a PNG blob. Nothing is kept. */
  async preview(blob) {
    const response = await fetch('/projects/picture-preview', { method: 'POST', headers: { 'Content-Type': 'image/png' }, body: blob });
    if (!response.ok) throw await failure(response);
    return response.blob();
  },
  /** The project's kept picture with that SHA-256 as the game shows it, or null. */
  async kept(id, sha256) {
    const response = await fetch(`${at(id)}?sha256=${encodeURIComponent(sha256)}&as=game`);
    return response.ok ? response.blob() : null;
  },
  /** The kept picture of project `from` with that SHA-256 kept with project `to` as well (Save as): the file as it
   *  is, so its SHA-256 stays the one the document names. */
  async copy(from, to, sha256) {
    const response = await fetch(`${at(from)}?sha256=${encodeURIComponent(sha256)}`);
    if (!response.ok) throw await failure(response);
    return this.save(to, await response.blob());
  },
  /** The game's own picture of a map, or null when it has none. */
  async base(map) {
    const response = await fetch(`/map-pictures/${encodeURIComponent(map)}.png`);
    return response.ok ? response.blob() : null;
  },
};

/** The frame of `source` (an image or a canvas, iw x ih) drawn as the 512 x 256 picture: halved in steps while it is
 *  more than twice the size, then one smooth step; opaque, on black. */
export function cropped(source, frame, iw, ih) {
  let from = source, rect = sourceRect(frame, iw, ih);
  for (const [w, h] of scaleSteps(rect[2])) {
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const g = canvas.getContext('2d');
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    g.fillStyle = '#000'; g.fillRect(0, 0, w, h);
    g.drawImage(from, ...rect, 0, 0, w, h);
    from = canvas; rect = [0, 0, w, h];
  }
  return from;
}
const pngOf = canvas => new Promise((resolve, reject) => canvas.toBlob(b => (b ? resolve(b) : reject(new Error('the picture could not be made'))), 'image/png'));
async function imageOf(blob) {
  const url = URL.createObjectURL(blob);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return image;
  } finally { URL.revokeObjectURL(url); }
}

const HANDLE = 9;       // half a corner handle's reach, in view pixels
const VIEW_W = 512, VIEW_H = 300;

/**
 * els: root, form, title, note, drop (the crop view's box, where files are dropped), canvas (the crop view), empty (its
 * words while no image is chosen), file (the hidden file input), choose, take, result (a 512 x 256 canvas),
 * resultNote, status, use, remove, close.
 * onUse({ sha256 }) and onRemove(): the page's, when the project's picture changes. grabView(): a canvas of the 3D
 * view as it is now, or null (Take from the view).
 */
export function createMapPicture({ els, api = pictureApi, onUse, onRemove, grabView = null }) {
  let lastFocus = null, context = null;      // { id, name, map, own: sha256 or null }
  let source = null, iw = 0, ih = 0, frame = null, scale = 1, drag = null;
  let previewToken = 0, previewTimer = 0, busy = false;

  const say = (message, warn = false) => { els.status.textContent = message; els.status.hidden = !message; els.status.classList.toggle('warn', warn); };
  function update() {
    els.use.disabled = busy || !source;
    els.remove.disabled = busy || !context?.own;
    els.take.hidden = !grabView;
    els.empty.hidden = Boolean(source);
    els.canvas.hidden = !source;
  }
  function drawResult(image) {
    const g = els.result.getContext('2d');
    g.fillStyle = '#000'; g.fillRect(0, 0, WIDTH, HEIGHT);
    if (image) g.drawImage(image, 0, 0, WIDTH, HEIGHT);
  }
  // What the game shows now, with no image chosen: the project's own picture, else the base map's, else none
  async function showCurrent() {
    const token = ++previewToken, { id, map, own } = context;
    drawResult(null);
    els.resultNote.textContent = '';
    let blob = own ? await api.kept(id, own).catch(() => null) : null;
    if (token !== previewToken) return;
    if (blob) els.resultNote.textContent = 'The map\'s own picture, as the game shows it.';
    else {
      blob = await api.base(map).catch(() => null);
      if (token !== previewToken) return;
      els.resultNote.textContent = own ? 'The picture\'s file is not on this computer: choose the image again.'
        : blob ? `No picture of its own: a map pack borrows ${map}'s, shown here.`
        : `No picture of its own, and the game has none of ${map}: the mission screens show no picture.`;
    }
    if (blob) { const image = await imageOf(blob).catch(() => null); if (token === previewToken) drawResult(image); }
  }
  function drawCrop() {
    if (!source) return;
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    scale = Math.min(VIEW_W / iw, VIEW_H / ih);
    const w = Math.max(1, Math.round(iw * scale)), h = Math.max(1, Math.round(ih * scale));
    if (els.canvas.width !== Math.round(w * ratio) || els.canvas.height !== Math.round(h * ratio)) {
      els.canvas.width = Math.round(w * ratio); els.canvas.height = Math.round(h * ratio);
      els.canvas.style.width = `${w}px`; els.canvas.style.height = `${h}px`;
    }
    const g = els.canvas.getContext('2d');
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.imageSmoothingQuality = 'high';
    g.drawImage(source, 0, 0, w, h);
    const x = frame.x * scale, y = frame.y * scale, fw = frame.w * scale, fh = frame.h * scale;
    g.fillStyle = 'rgba(0, 0, 0, 0.6)';
    g.fillRect(0, 0, w, y); g.fillRect(0, y + fh, w, h - y - fh); g.fillRect(0, y, x, fh); g.fillRect(x + fw, y, w - x - fw, fh);
    g.strokeStyle = '#fff'; g.lineWidth = 1.5; g.strokeRect(x + 0.75, y + 0.75, fw - 1.5, fh - 1.5);
    g.fillStyle = '#fff';
    for (const [cx, cy] of [[x, y], [x + fw, y], [x, y + fh], [x + fw, y + fh]])
      g.fillRect(Math.min(Math.max(cx - 4, 0), w - 8), Math.min(Math.max(cy - 4, 0), h - 8), 8, 8);
  }
  function frameChanged() {
    drawCrop();
    // the result at once as cropped, then as the game shows it once the server has answered
    const canvas = cropped(source, frame, iw, ih);
    drawResult(canvas);
    els.resultNote.textContent = 'As the game will show it.';
    const token = ++previewToken;
    clearTimeout(previewTimer);
    previewTimer = setTimeout(async () => {
      try {
        const image = await imageOf(await api.preview(await pngOf(canvas)));
        if (token === previewToken) drawResult(image);
      } catch { /* the cropped picture stays shown */ }
    }, 200);
  }
  function setImage(image, w, h) {
    if (!(w >= 2 && h >= 1)) { say('That image is too small to crop.', true); return; }
    source = image; iw = w; ih = h; frame = startFrame(w, h);
    say('Drag the frame to move it; drag a corner or turn the wheel to resize it.');
    update(); frameChanged();
  }
  async function setFile(file) {
    if (!file) return;
    try {
      const image = await imageOf(file);
      setImage(image, image.naturalWidth, image.naturalHeight);
    } catch { say(`${file.name || 'That file'} is not an image the browser can show (.png, .jpg, .bmp and .webp are).`, true); }
  }

  // the pointer in image pixels
  function pointer(e) {
    const box = els.canvas.getBoundingClientRect();
    return [(e.clientX - box.left) / scale, (e.clientY - box.top) / scale];
  }
  function cornerAt(px, py) {
    const reach = HANDLE / scale;
    for (const [name, cx, cy] of [['nw', frame.x, frame.y], ['ne', frame.x + frame.w, frame.y], ['sw', frame.x, frame.y + frame.h],
                                  ['se', frame.x + frame.w, frame.y + frame.h]])
      if (Math.abs(px - cx) <= reach && Math.abs(py - cy) <= reach) return name;
    return null;
  }
  const inside = (px, py) => px >= frame.x && px <= frame.x + frame.w && py >= frame.y && py <= frame.y + frame.h;
  els.canvas.addEventListener('pointerdown', e => {
    if (!source || e.button !== 0) return;
    const [px, py] = pointer(e), corner = cornerAt(px, py);
    if (!corner && !inside(px, py)) return;
    drag = { corner, px, py, frame: { ...frame } };
    els.canvas.setPointerCapture(e.pointerId);
    e.preventDefault();
  });
  els.canvas.addEventListener('pointermove', e => {
    if (!source) return;
    const [px, py] = pointer(e);
    if (!drag) {
      const corner = cornerAt(px, py);
      els.canvas.style.cursor = corner ? (corner === 'nw' || corner === 'se' ? 'nwse-resize' : 'nesw-resize') : inside(px, py) ? 'move' : 'default';
      return;
    }
    frame = drag.corner ? dragCorner(drag.frame, drag.corner, px, py, iw, ih) : moveFrame(drag.frame, px - drag.px, py - drag.py, iw, ih);
    frameChanged();
  });
  const endDrag = e => { if (drag) { drag = null; els.canvas.releasePointerCapture?.(e.pointerId); } };
  els.canvas.addEventListener('pointerup', endDrag);
  els.canvas.addEventListener('pointercancel', endDrag);
  els.canvas.addEventListener('wheel', e => {
    if (!source) return;
    e.preventDefault();
    const [px, py] = pointer(e);
    frame = zoomFrame(frame, e.deltaY > 0 ? 1.08 : 1 / 1.08, px, py, iw, ih);
    frameChanged();
  }, { passive: false });
  // the keyboard's way: arrows move the frame, + and - resize it about its middle
  els.canvas.addEventListener('keydown', e => {
    if (!source) return;
    const step = Math.max(1, frame.w / 40) * (e.shiftKey ? 4 : 1);
    const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (moves[e.key]) frame = moveFrame(frame, ...moves[e.key], iw, ih);
    else if (e.key === '+' || e.key === '=') frame = zoomFrame(frame, 1 / 1.08, frame.x + frame.w / 2, frame.y + frame.h / 2, iw, ih);
    else if (e.key === '-') frame = zoomFrame(frame, 1.08, frame.x + frame.w / 2, frame.y + frame.h / 2, iw, ih);
    else return;
    e.preventDefault(); e.stopPropagation();
    frameChanged();
  });

  els.choose.onclick = () => els.file.click();
  els.file.onchange = () => { const file = els.file.files[0]; els.file.value = ''; setFile(file); };
  for (const type of ['dragenter', 'dragover']) els.root.addEventListener(type, e => {
    if (![...(e.dataTransfer?.types ?? [])].includes('Files')) return;
    e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; els.drop.classList.add('over');
  });
  els.root.addEventListener('dragleave', e => { if (!els.root.contains(e.relatedTarget)) els.drop.classList.remove('over'); });
  els.root.addEventListener('drop', e => {
    if (![...(e.dataTransfer?.types ?? [])].includes('Files')) return;
    e.preventDefault(); els.drop.classList.remove('over');
    setFile(e.dataTransfer.files[0]);
  });
  els.take.onclick = () => {
    const canvas = grabView?.();
    if (!canvas) { say('The view could not be read just now: try again.', true); return; }
    setImage(canvas, canvas.width, canvas.height);
  };

  function hide() {
    previewToken++; clearTimeout(previewTimer);
    els.root.hidden = true; source = null; frame = null; context = null;
    lastFocus?.focus?.();
  }
  els.form.onsubmit = async e => {
    e.preventDefault();
    if (busy || !source || !context) return;
    busy = true; update(); say('Keeping the picture…');
    try {
      const result = await api.save(context.id, await pngOf(cropped(source, frame, iw, ih)));
      const use = onUse;
      hide();
      use?.(result);
    } catch (error) { say(`The picture was not kept: ${error.message}`, true); }
    finally { busy = false; if (context) update(); }
  };
  els.remove.onclick = async () => {
    if (busy || !context?.own) return;
    busy = true; update();
    try {
      await api.remove(context.id);
      const remove = onRemove;
      hide();
      remove?.();
    } catch (error) { say(`The picture was not removed: ${error.message}`, true); }
    finally { busy = false; if (context) update(); }
  };
  els.close.onclick = hide;
  els.root.addEventListener('keydown', e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); hide(); } });

  return {
    /** project: { id, name }; map: the base map's name; own: the SHA-256 of the project's picture, or null. */
    show({ project, map, own }) {
      lastFocus = document.activeElement;
      context = { id: project.id, name: project.name, map, own: own ?? null };
      source = null; frame = null; busy = false;
      els.title.textContent = `Map picture of ${project.name}`;
      els.note.textContent = 'The picture of the map on the game\'s mission screens. Long War Rebalance 3 shows a map\'s own picture; '
        + 'plain Enemy Within and earlier Long War versions don\'t look for one. Choose an image or drop one here, then set the frame: '
        + 'the Build writes the picture into the map.';
      say('');
      update();
      els.root.hidden = false;
      showCurrent();
      setTimeout(() => els.choose.focus(), 0);
    },
    get open() { return !els.root.hidden; },
    /** (for the checks) the frame and the image's size now */
    state: () => (source ? { frame: { ...frame }, width: iw, height: ih } : null),
    setFile,
  };
}
