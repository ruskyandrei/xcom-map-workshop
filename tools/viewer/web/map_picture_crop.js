// The arithmetic of the Map picture dialog's crop view (map_picture.js; LWR map packs plan, 4.2): a 2:1 frame over an
// image, kept inside it whatever is dragged, and the sizes the frame is scaled through on its way to 512 x 256.
// Nothing here touches the page, so the node tests read it (tests/map_picture_test.mjs).
// A frame is { x, y, w, h } in the image's own pixels, h always w / 2.
export const WIDTH = 512, HEIGHT = 256, RATIO = WIDTH / HEIGHT;
// the smallest frame: 32 image pixels wide, or the largest the image holds when that is less
export const MIN_WIDTH = 32;

/** The widest 2:1 frame an image of w x h holds. */
export const widest = (w, h) => Math.min(w, h * RATIO);
const least = (w, h) => Math.min(MIN_WIDTH, widest(w, h));

/** The frame a new image starts with: the largest 2:1 frame, around the middle. */
export function startFrame(w, h) {
  const fw = widest(w, h), fh = fw / RATIO;
  return { x: (w - fw) / 2, y: (h - fh) / 2, w: fw, h: fh };
}

/** A frame of the width asked for (no wider than the image holds, no narrower than the least), its corner moved so
 *  the whole frame lies inside the image. */
export function clampFrame(frame, w, h) {
  const fw = Math.min(widest(w, h), Math.max(least(w, h), frame.w)), fh = fw / RATIO;
  return { x: Math.min(Math.max(0, frame.x), w - fw), y: Math.min(Math.max(0, frame.y), h - fh), w: fw, h: fh };
}

/** The frame moved by (dx, dy) image pixels, stopped at the image's edges. */
export const moveFrame = (frame, dx, dy, w, h) => clampFrame({ ...frame, x: frame.x + dx, y: frame.y + dy }, w, h);

/** The frame resized by dragging a corner ('nw', 'ne', 'sw', 'se') to (px, py): the opposite corner stays where it
 *  is, the frame keeps 2:1 (the larger of what the pointer asks for across and down), and stops at the image's edges. */
export function dragCorner(frame, corner, px, py, w, h) {
  const west = corner.includes('w'), north = corner.includes('n');
  const ax = west ? frame.x + frame.w : frame.x, ay = north ? frame.y + frame.h : frame.y;    // the corner that stays
  const asked = Math.max(west ? ax - px : px - ax, (north ? ay - py : py - ay) * RATIO);
  // as wide as the image leaves room for on the dragged corner's side
  const room = Math.min(west ? ax : w - ax, (north ? ay : h - ay) * RATIO);
  const fw = Math.max(Math.min(least(w, h), room), Math.min(asked, room)), fh = fw / RATIO;
  return { x: west ? ax - fw : ax, y: north ? ay - fh : ay, w: fw, h: fh };
}

/** The frame made `factor` times as wide (the wheel: under 1 zooms in) about the image point (cx, cy), which keeps its
 *  place in the frame while the frame has room. */
export function zoomFrame(frame, factor, cx, cy, w, h) {
  const fw = Math.min(widest(w, h), Math.max(least(w, h), frame.w * factor)), k = fw / frame.w;
  return clampFrame({ x: cx - (cx - frame.x) * k, y: cy - (cy - frame.y) * k, w: fw, h: fw / RATIO }, w, h);
}

/** The canvas sizes a frame `fw` image pixels wide is drawn through, [[w, h]...], the last 512 x 256: halved while
 *  the picture is still more than twice the size, then one smooth step. A frame up to twice the size, or smaller
 *  than the picture, goes in one step. */
export function scaleSteps(fw) {
  const steps = [];
  for (let cw = fw; cw > 2 * WIDTH;) {
    cw = Math.max(WIDTH, Math.ceil(cw / 2));
    if (cw > WIDTH) steps.push([cw, Math.round(cw / RATIO)]);
  }
  steps.push([WIDTH, HEIGHT]);
  return steps;
}

/** The frame as whole image pixels to draw from: [sx, sy, sw, sh], inside the image. */
export function sourceRect(frame, w, h) {
  const sw = Math.max(1, Math.min(w, Math.round(frame.w))), sh = Math.max(1, Math.min(h, Math.round(frame.h)));
  return [Math.min(Math.max(0, Math.round(frame.x)), w - sw), Math.min(Math.max(0, Math.round(frame.y)), h - sh), sw, sh];
}
