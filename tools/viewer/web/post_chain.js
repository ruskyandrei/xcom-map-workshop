// The Game look's frame (game-likeness plan, C3): the map's pieces drawn to a floating-point target, then the game's
// bloom, its gamma and the map's grade (post_grade.js), and only then the editor's own helpers (the gizmo, handles,
// markers, the grid, outlines), straight to the screen as in the Neutral look and against the scene's depth, so the
// grade never changes their colours. Our own passes on three.js's core (no post-processing add-on is vendored).
//
// The depth: the target is multisampled, and three resolves its depth into a depth texture with its colour; the last
// pass writes that depth to the screen beside the graded colour (gl_FragDepth), so a helper drawn afterwards is hidden
// where a piece is in front of it, as before.
import * as THREE from 'three';
import { GRADE_GLSL } from './post_grade.js';

const QUARTER = 4;            // the bloom's buffers: a quarter of the frame across, as the game gathers its bloom
const TAPS = 6;               // a blur's taps each side of the middle

const VERTEX = `varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4( position.xy, 0.0, 1.0 ); }`;

// the gather: four bilinear taps, each a two-by-two block of the frame, kept by how far over the threshold their
// brightest channel is, averaged and scaled by the bloom's scale (the game's DOFAndBloomGather)
const GATHER = `uniform sampler2D frame; uniform vec2 texel; uniform float threshold; uniform float scale; uniform float brightness;
varying vec2 vUv;
vec3 tap( vec2 at ) {
	vec3 c = texture2D( frame, at ).rgb * brightness;
	return c * clamp( ( max( max( c.r, c.g ), c.b ) - threshold ) * 0.5, 0.0, 1.0 );
}
void main() {
	vec3 sum = tap( vUv + texel * vec2( -1.0, -1.0 ) ) + tap( vUv + texel * vec2( 1.0, -1.0 ) )
		+ tap( vUv + texel * vec2( -1.0, 1.0 ) ) + tap( vUv + texel * vec2( 1.0, 1.0 ) );
	gl_FragColor = vec4( sum * 0.25 * scale, 1.0 );
}`;

// one direction of a Gaussian blur at the bloom's size, its spread from the map's kernel size
const BLUR = `uniform sampler2D image; uniform vec2 step; uniform float sigma;
varying vec2 vUv;
void main() {
	vec3 sum = vec3( 0.0 ); float weights = 0.0;
	for ( int k = -${TAPS}; k <= ${TAPS}; k ++ ) {
		float x = float( k ), w = exp( - x * x / ( 2.0 * sigma * sigma ) );
		sum += texture2D( image, vUv + step * x ).rgb * w; weights += w;
	}
	gl_FragColor = vec4( sum / weights, 1.0 );
}`;

// the frame as the game shows it: the scene's light scaled by the Brightness slider, the bloom added where the scene
// is dark, then the gamma and the grade; and the scene's depth, for the helpers drawn after it
const COMPOSITE = `uniform sampler2D frame; uniform sampler2D depth; uniform sampler2D bloom;
uniform float brightness; uniform float bloomOn; uniform vec3 bloomTint; uniform float bloomScreenBlend;
${GRADE_GLSL}
varying vec2 vUv;
void main() {
	vec3 c = texture2D( frame, vUv ).rgb * brightness;
	if ( bloomOn > 0.5 ) {
		float share = clamp( exp2( -3.0 * dot( c, vec3( 0.3, 0.59, 0.11 ) ) ) * bloomScreenBlend, 0.0, 1.0 );
		c += texture2D( bloom, vUv ).rgb * bloomTint * share;
	}
	gl_FragColor = vec4( gameGrade( c ), 1.0 );
	gl_FragDepth = texture2D( depth, vUv ).r;
}`;

const vec3 = () => ({ value: new THREE.Vector3() });

/** The chain for a renderer. `render(world, camera, parts, values, helpers)` draws a frame: `parts` the world's
 *  children that are the map (its pieces, its lights' likenesses, its effects'), every other child but a light a
 *  helper; `values` post_grade.postUniforms'; `helpers` false leaves them out (a picture of the view). `warm` compiles
 *  the pieces' shaders as the target draws them (they differ from the screen's: no tone curve, linear colour). */
export function createPostChain(renderer) {
  const size = new THREE.Vector2();
  let target = null, bloomA = null, bloomB = null;
  const quadScene = new THREE.Scene(), quadCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
  quad.frustumCulled = false;
  quadScene.add(quad);
  const pass = (fragmentShader, uniforms, extra = {}) => new THREE.ShaderMaterial({
    vertexShader: VERTEX, fragmentShader, uniforms, depthTest: false, depthWrite: false, toneMapped: false, ...extra });
  const gather = pass(GATHER, { frame: { value: null }, texel: { value: new THREE.Vector2() }, threshold: { value: 1 },
                                scale: { value: 1 }, brightness: { value: 1 } });
  const blur = pass(BLUR, { image: { value: null }, step: { value: new THREE.Vector2() }, sigma: { value: 2 } });
  const composite = pass(COMPOSITE, {
    frame: { value: null }, depth: { value: null }, bloom: { value: null }, brightness: { value: 1 }, bloomOn: { value: 0 },
    bloomTint: vec3(), bloomScreenBlend: { value: 10 }, gradeShadows: vec3(), gradeInverseHighlights: vec3(),
    gradeMidTones: vec3(), gradeKeep: { value: 1 }, gradeLuminance: vec3(), gradeColorize: vec3(),
  }, { depthTest: true, depthWrite: true, depthFunc: THREE.AlwaysDepth });     // (depth is only written where tested)

  function fit() {
    renderer.getDrawingBufferSize(size);
    const w = Math.max(1, size.x), h = Math.max(1, size.y);
    if (target && target.width === w && target.height === h) return;
    for (const t of [target, bloomA, bloomB]) t?.dispose();
    target = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: 4,
      depthTexture: new THREE.DepthTexture(w, h, THREE.FloatType) });
    const bw = Math.max(1, Math.ceil(w / QUARTER)), bh = Math.max(1, Math.ceil(h / QUARTER));
    const small = { type: THREE.HalfFloatType, depthBuffer: false };
    bloomA = new THREE.WebGLRenderTarget(bw, bh, small);
    bloomB = new THREE.WebGLRenderTarget(bw, bh, small);
  }
  const draw = (material, to) => { quad.material = material; renderer.setRenderTarget(to); renderer.render(quadScene, quadCamera); };
  // hide some of the world's children for one draw
  function only(world, keep, draw) {
    const hidden = [];
    for (const child of world.children) {
      if (child.isLight || keep(child) || !child.visible) continue;
      child.visible = false; hidden.push(child);
    }
    try { draw(); } finally { for (const child of hidden) child.visible = true; }
  }

  function render(world, camera, parts, values, helpers = true) {
    fit();
    const before = renderer.getRenderTarget();
    // the map's pieces, in linear light: the target takes no tone curve and no colour space
    only(world, child => parts.has(child), () => { renderer.setRenderTarget(target); renderer.render(world, camera); });
    const u = composite.uniforms;
    u.bloomOn.value = values.bloomOn;
    if (values.bloomOn) {
      gather.uniforms.threshold.value = values.bloomThreshold;
      gather.uniforms.scale.value = values.bloomScale; gather.uniforms.brightness.value = values.brightness;
      gather.uniforms.frame.value = target.texture; gather.uniforms.texel.value.set(1 / target.width, 1 / target.height);
      draw(gather, bloomA);
      // the kernel size is in the frame's pixels; its half is the blur's reach, two spreads of it
      blur.uniforms.sigma.value = Math.max(0.5, values.bloomKernel / QUARTER / 4);
      const stride = Math.max(1, blur.uniforms.sigma.value * 3 / TAPS);
      blur.uniforms.image.value = bloomA.texture; blur.uniforms.step.value.set(stride / bloomA.width, 0); draw(blur, bloomB);
      blur.uniforms.image.value = bloomB.texture; blur.uniforms.step.value.set(0, stride / bloomA.height); draw(blur, bloomA);
    }
    u.frame.value = target.texture; u.depth.value = target.depthTexture; u.bloom.value = bloomA.texture;
    u.brightness.value = values.brightness; u.bloomTint.value.set(...values.bloomTint); u.bloomScreenBlend.value = values.bloomScreenBlend;
    for (const name of ['shadows', 'inverseHighlights', 'midTones', 'luminance', 'colorize']) {
      u[`grade${name[0].toUpperCase()}${name.slice(1)}`].value.set(...values[name]);
    }
    u.gradeKeep.value = values.keep;
    draw(composite, before);
    if (!helpers) return;
    // the helpers, straight to the screen against the scene's depth: no clearing, no background
    const background = world.background, autoClear = renderer.autoClear;
    world.background = null; renderer.autoClear = false;
    try { only(world, child => !parts.has(child), () => renderer.render(world, camera)); }
    finally { world.background = background; renderer.autoClear = autoClear; }
  }

  /** Compile the pieces' shaders for the target ahead of the first frame (a promise; compileAsync's). */
  function warm(world, camera) {
    fit();
    const before = renderer.getRenderTarget();
    renderer.setRenderTarget(target);
    try { return renderer.compileAsync(world, camera); } finally { renderer.setRenderTarget(before); }
  }

  /** The chain's GPU memory in bytes, for the perf probe: the target (four samples and its resolved copy, colour and
   *  depth) and the bloom's two buffers. */
  function memory() {
    if (!target) return 0;
    return target.width * target.height * (8 * 4 + 4 * 4 + 8 + 4) + 2 * bloomA.width * bloomA.height * 8;
  }

  return { render, warm, memory, get target() { return target; } };
}
