// A material's program (the export's `program`, research/editor-contracts.md section 9: its compiled shaders'
// slice) as GLSL for the page's shader, and run on numbers (the node test holds it to shader_eval.py's golden values).
// Pure: no three.js. scene_pieces.js patches a piece's material with what programGlsl gives (game-likeness plan,
// A-S4).
//
// The program's registers become GLSL vec4s, its instructions one statement each (SM3's operations as Direct3D 9
// defines them), its inputs varyings made in the vertex shader from the mesh's streams in the game's axes (the view's
// x, z, y), its textures samplers and its constants uniforms (the material's own values and the page's engine values;
// literals are written in the text), so that materials whose programs are the same text share one compiled shader.

const C = 'xyzw';

/** The input kinds a program reads ({ uv: Set of channels, color, cameraVector, worldPosition, frame, sign, face,
 *  fragCoord }). */
export function inputsRead(program) {
  const out = { uv: new Set(), color: false, cameraVector: false, worldPosition: false, frame: false, sign: false,
                face: false, fragCoord: false };
  for (const sources of Object.values(program.inputs ?? {})) {
    for (const s of sources) {
      if (!s) continue;
      if (s.kind === 'uv') out.uv.add(s.channel);
      else if (s.kind === 'color') out.color = true;
      else if (s.kind === 'cameraVector') out.cameraVector = true;
      else if (s.kind === 'worldPosition') out.worldPosition = true;
      else if (s.kind === 'worldTangent' || s.kind === 'worldBinormal' || s.kind === 'worldNormal') out.frame = true;
      else if (s.kind === 'tangentSign') out.sign = true;
      else if (s.kind === 'vFace') out.face = true;
      else if (s.kind === 'vPos') out.fragCoord = true;
    }
  }
  return out;
}

const num = v => {
  if (!Number.isFinite(v)) return v > 0 ? '1e30' : v < 0 ? '-1e30' : '0.0';
  const s = String(+v.toPrecision(9));
  return /[.e]/.test(s) ? s : `${s}.0`;
};
const vec4 = values => `vec4(${values.map(num).join(', ')})`;
const isLiteral = record => !('uniform' in record || 'engine' in record || 'vector' in record || 'scalars' in record);

function sourceText(s, names) {
  let text = `${names(s.r)}.${s.w}`;
  if (s.a) text = `abs(${text})`;
  if (s.n) text = `(-${text})`;
  return text;
}

const OPS = {
  mov: s => s[0],
  add: s => `(${s[0]} + ${s[1]})`,
  sub: s => `(${s[0]} - ${s[1]})`,
  mul: s => `(${s[0]} * ${s[1]})`,
  mad: s => `(${s[0]} * ${s[1]} + ${s[2]})`,
  lrp: s => `mix(${s[2]}, ${s[1]}, ${s[0]})`,
  min: s => `min(${s[0]}, ${s[1]})`,
  max: s => `max(${s[0]}, ${s[1]})`,
  slt: s => `vec4(lessThan(${s[0]}, ${s[1]}))`,
  sge: s => `vec4(greaterThanEqual(${s[0]}, ${s[1]}))`,
  cmp: s => `mix(${s[2]}, ${s[1]}, step(vec4(0.0), ${s[0]}))`,
  frc: s => `fract(${s[0]})`,
  abs: s => `abs(${s[0]})`,
  sgn: s => `sign(${s[0]})`,
  rcp: s => `vec4(1.0 / ${s[0]}.x)`,
  rsq: s => `vec4(inversesqrt(abs(${s[0]}.x)))`,
  exp: s => `vec4(exp2(${s[0]}.x))`,
  log: s => `vec4(log2(abs(${s[0]}.x)))`,
  pow: s => `vec4(pow(max(abs(${s[0]}.x), 1e-30), ${s[1]}.x))`,
  dp3: s => `vec4(dot(${s[0]}.xyz, ${s[1]}.xyz))`,
  dp4: s => `vec4(dot(${s[0]}, ${s[1]}))`,
  dp2add: s => `vec4(dot(${s[0]}.xy, ${s[1]}.xy) + ${s[2]}.x)`,
  nrm: s => `progNrm(${s[0]})`,
  crs: s => `vec4(cross(${s[0]}.xyz, ${s[1]}.xyz), 0.0)`,
  sincos: s => `vec4(cos(${s[0]}.x), sin(${s[0]}.x), 0.0, 0.0)`,
  dsx: s => `dFdx(${s[0]})`,
  dsy: s => `dFdy(${s[0]})`,
};

/** The GLSL of a program: { vertexDeclarations, vertexBody (after three's worldpos_vertex), fragmentDeclarations,
 *  fragmentBody (fills progOut_<output> vec4s), uniforms: [{ name, constant }], samplers: [{ name, texture }],
 *  outputs: [names], key }. `outputs` limits the outputs written (all by default). Throws on an operation it doesn't
 *  carry out. */
// the components a row reads to make its destination's components `comps`, as [source position, register,
// component] (shader_slice.row_reads' rule)
const COMPONENTWISE = new Set(['mov', 'add', 'sub', 'mad', 'mul', 'min', 'max', 'slt', 'sge', 'lrp', 'frc', 'abs', 'cmp', 'sgn', 'dsx', 'dsy']);
function rowReads(row, comps) {
  const out = [], sw = (s, k) => C.indexOf(s.w[k]);
  const each = (p, s, ks) => ks.forEach(k => out.push([p, s.r, sw(s, k)]));
  if (COMPONENTWISE.has(row.op)) row.s.forEach((s, p) => each(p, s, comps));
  else if (['rcp', 'rsq', 'exp', 'log', 'pow', 'sincos'].includes(row.op)) row.s.forEach((s, p) => each(p, s, [0]));
  else if (['dp3', 'nrm', 'crs'].includes(row.op)) row.s.forEach((s, p) => each(p, s, [0, 1, 2]));
  else if (row.op === 'dp4') row.s.forEach((s, p) => each(p, s, [0, 1, 2, 3]));
  else if (row.op === 'dp2add') { each(0, row.s[0], [0, 1]); each(1, row.s[1], [0, 1]); each(2, row.s[2], [0]); }
  else if (row.op === 'texld') { each(0, row.s[0], row.texld ? [0, 1, 3] : [0, 1]); out.push([1, row.s[1].r, 0]); }
  else throw new Error(`a program operation ${row.op}`);
  return out;
}

/** The program cut to what `outputs` need: its rows, inputs, constants and textures no wanted output reads left out
 *  (so the shader declares and fills only those). */
export function programFor(program, outputs) {
  const needed = new Set();
  const want = (r, c) => needed.add(`${r}.${c}`);
  for (const name of outputs) {
    const o = program.outputs?.[name];
    if (o && 'r' in o) for (const c of o.m) want(o.r, C.indexOf(c));
  }
  const kept = [];
  for (const row of [...(program.code ?? [])].reverse()) {
    const comps = [...row.m].map(c => C.indexOf(c)).filter(k => needed.has(`${row.d}.${k}`));
    if (!comps.length) continue;
    comps.forEach(k => needed.delete(`${row.d}.${k}`));
    for (const [, r, c] of rowReads(row, comps)) want(r, c);
    kept.push({ ...row, m: comps.map(k => C[k]).join('') });
  }
  kept.reverse();
  const used = new Set(kept.flatMap(row => row.s.map(s => s.r)));
  for (const name of outputs) { const o = program.outputs?.[name]; if (o && 'r' in o) used.add(o.r); }
  const only = table => Object.fromEntries(Object.entries(table ?? {}).filter(([k]) => used.has(k)));
  return { ...program, code: kept, inputs: only(program.inputs), constants: only(program.constants), textures: only(program.textures),
           outputs: Object.fromEntries(outputs.filter(o => program.outputs?.[o]).map(o => [o, program.outputs[o]])) };
}

export function programGlsl(whole, outputs = null) {
  const wanted = outputs ?? Object.keys(whole.outputs ?? {});
  const program = outputs ? programFor(whole, wanted) : whole;
  const read = inputsRead(program);
  const vDecl = [], vBody = [], fDecl = [], fBody = [];
  const uniforms = [], samplers = [];
  // the vertex shader's part: the varyings each input kind needs
  for (const channel of [...read.uv].sort()) {
    const attr = channel === 0 ? 'uv' : `uv${channel}`;
    if (channel > 0) vDecl.push(`#ifndef USE_UV${channel}\nattribute vec2 ${attr};\n#endif`);
    vDecl.push(`varying vec2 vProgUv${channel};`);
    fDecl.push(`varying vec2 vProgUv${channel};`);
    vBody.push(`vProgUv${channel} = ${attr};`);
  }
  if (read.color) {
    vDecl.push('#if !defined(USE_COLOR) && !defined(USE_COLOR_ALPHA)\nattribute vec4 color;\n#endif', 'varying vec4 vProgColor;');
    fDecl.push('varying vec4 vProgColor;');
    vBody.push('vProgColor = vec4(color);');
  }
  const viewFrame = wanted.includes('normal') && program.outputs.normal && 'r' in program.outputs.normal;
  const frame = read.cameraVector || read.frame || read.sign || viewFrame;
  if (frame) {
    vDecl.push('#ifndef USE_TANGENT\nattribute vec4 tangent;\n#endif');
    // the tangent frame in the world (the view's axes): the export wrote tangents with their w flipped, so three's own
    // bitangent (cross(normal, tangent) * w) is the game's binormal in the view's axes
    vBody.push('vec3 progN = normalize(mat3(modelMatrix) * normal);',
               'vec3 progT = normalize(mat3(modelMatrix) * tangent.xyz);',
               'vec3 progB = normalize(mat3(modelMatrix) * (cross(normal, tangent.xyz) * tangent.w));');
  }
  if (viewFrame) {
    // the normal's tangent frame in the view's space (three's vNormal is the third axis), for the lights
    vDecl.push('varying vec3 vProgViewT;', 'varying vec3 vProgViewB;');
    fDecl.push('varying vec3 vProgViewT;', 'varying vec3 vProgViewB;');
    vBody.push('vProgViewT = normalMatrix * tangent.xyz;', 'vProgViewB = normalMatrix * (cross(normal, tangent.xyz) * tangent.w);');
  }
  if (read.cameraVector || read.worldPosition) vBody.push('vec3 progWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;');
  if (read.cameraVector) {
    vDecl.push('varying vec3 vProgCamera;');
    fDecl.push('varying vec3 vProgCamera;');
    vBody.push('vec3 progToCamera = cameraPosition - progWorld;',
               'vProgCamera = vec3(dot(progT, progToCamera), dot(progB, progToCamera), dot(progN, progToCamera));');
  }
  if (read.worldPosition) {
    vDecl.push('varying vec3 vProgWorld;');
    fDecl.push('varying vec3 vProgWorld;');
    vBody.push('vProgWorld = (progWorld - cameraPosition).xzy;');       // camera-relative, the game's axes
  }
  if (read.frame) {
    vDecl.push('varying vec3 vProgT;', 'varying vec3 vProgB;', 'varying vec3 vProgN;');
    fDecl.push('varying vec3 vProgT;', 'varying vec3 vProgB;', 'varying vec3 vProgN;');
    vBody.push('vProgT = progT.xzy;', 'vProgB = progB.xzy;', 'vProgN = progN.xzy;');
  }
  if (read.sign) {
    vDecl.push('varying float vProgSign;');
    fDecl.push('varying float vProgSign;');
    vBody.push('vProgSign = -tangent.w * sign(determinant(mat3(modelMatrix)));');
  }
  const kinds = { worldTangent: 'vProgT', worldBinormal: 'vProgB', worldNormal: 'vProgN' };
  function component(s) {
    if (!s) return '0.0';
    const k = s.kind, scale = s.scale ?? 1, bias = s.bias ?? 0;
    const affine = text => (scale === 1 && bias === 0 ? text : `(${text} * ${num(scale)} + ${num(bias)})`);
    if (k === 'const') return num(s.value);
    if (k === 'uv') return affine(`vProgUv${s.channel}.${C[s.component]}`);
    if (k === 'color') return affine(`vProgColor.${C[s.component]}`);
    if (k === 'cameraVector') return affine(`vProgCamera.${C[s.component]}`);
    if (k === 'worldPosition') return s.component === 3 ? num(scale) : affine(`vProgWorld.${C[s.component]}`);
    if (k in kinds) return affine(`${kinds[k]}.${C[s.component]}`);
    if (k === 'tangentSign') return affine('vProgSign');
    if (k === 'vFace') return '(gl_FrontFacing ? 1.0 : -1.0)';
    if (k === 'vPos') return s.component < 2 ? `gl_FragCoord.${C[s.component]}` : '0.0';
    throw new Error(`a program input of kind ${k}`);
  }
  fDecl.push('vec4 progNrm(vec4 v) { float f = inversesqrt(max(dot(v.xyz, v.xyz), 1e-30)); return v * f; }');
  // registers: inputs, constants (literals in the text, the rest uniforms), samplers, temporaries
  const names = new Map();
  for (const [name, sources] of Object.entries(program.inputs ?? {})) {
    names.set(name, `progIn_${name}`);
    fBody.push(`vec4 progIn_${name} = vec4(${sources.map(component).join(', ')});`);
  }
  for (const [name, record] of Object.entries(program.constants ?? {})) {
    if (isLiteral(record)) {
      names.set(name, `progLit_${name}`);
      fBody.push(`vec4 progLit_${name} = ${vec4(record.value)};`);
    } else {
      names.set(name, `progK_${name}`);
      fDecl.push(`uniform vec4 progK_${name};`);
      uniforms.push({ name: `progK_${name}`, constant: name });
    }
  }
  for (const [name, record] of Object.entries(program.textures ?? {})) {
    names.set(name, `progT_${name}`);
    fDecl.push(`uniform sampler2D progT_${name};`);
    samplers.push({ name: `progT_${name}`, texture: name, record });
  }
  const temps = new Set();
  const named = r => {
    if (names.has(r)) return names.get(r);
    temps.add(r);
    return `progR_${r}`;
  };
  for (const row of program.code ?? []) {
    let text;
    if (row.op === 'texld') {
      const coords = sourceText(row.s[0], named), sampler = named(row.s[1].r);
      if (row.texld === 'project') text = `texture2D(${sampler}, ${coords}.xy / ${coords}.w)`;
      else if (row.texld === 'bias') text = `texture2D(${sampler}, ${coords}.xy, ${coords}.w)`;
      else text = `texture2D(${sampler}, ${coords}.xy)`;
    } else {
      const op = OPS[row.op];
      if (!op) throw new Error(`a program operation ${row.op}`);
      text = op(row.s.map(s => sourceText(s, named)));
    }
    if (row.sat) text = `clamp(${text}, 0.0, 1.0)`;
    fBody.push(`${named(row.d)}.${row.m} = (${text}).${row.m};`);
  }
  for (const out of wanted) {
    const o = program.outputs[out];
    if (!o) continue;
    const value = 'value' in o ? [...o.value] : null;
    const text = value ? vec4([...value, 0, 0, 0, 0].slice(0, 4))
      : `vec4(${[...o.m].map(c => `${named(o.r)}.${c}`).concat(['0.0', '0.0', '0.0']).slice(0, 4).join(', ')})`;
    fBody.push(`progOut_${out} = ${text};`);
  }
  const fragmentBody = [...[...temps].sort().map(r => `vec4 progR_${r} = vec4(0.0);`), ...fBody].join('\n');
  const outputDecl = wanted.filter(o => program.outputs[o]).map(o => `vec4 progOut_${o} = vec4(0.0);`);
  const result = {
    vertexDeclarations: vDecl.join('\n'), vertexBody: vBody.join('\n'),
    fragmentDeclarations: fDecl.join('\n'), fragmentBody: `${outputDecl.join('\n')}\n{\n${fragmentBody}\n}`,
    uniforms, samplers, outputs: wanted.filter(o => program.outputs[o]),
  };
  result.key = hash(result.vertexDeclarations + result.vertexBody + result.fragmentDeclarations + result.fragmentBody);
  return result;
}

/** A short hash of a text (FNV-1a), for a shader's cache key. */
export function hash(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0).toString(16).padStart(8, '0');
}

// ---------------------------------------------------------------------------------------------------------------
// The same program run on numbers (one sample): the node test's check against shader_eval.py.

const swz = (v, w) => [...w].map(c => v[C.indexOf(c)]);
function apply(op, s, sample, texld) {
  const each = f => [0, 1, 2, 3].map(f);
  switch (op) {
    case 'mov': return [...s[0]];
    case 'add': return each(k => s[0][k] + s[1][k]);
    case 'sub': return each(k => s[0][k] - s[1][k]);
    case 'mul': return each(k => s[0][k] * s[1][k]);
    case 'mad': return each(k => s[0][k] * s[1][k] + s[2][k]);
    case 'lrp': return each(k => s[0][k] * s[1][k] + (1 - s[0][k]) * s[2][k]);
    case 'min': return each(k => Math.min(s[0][k], s[1][k]));
    case 'max': return each(k => Math.max(s[0][k], s[1][k]));
    case 'slt': return each(k => (s[0][k] < s[1][k] ? 1 : 0));
    case 'sge': return each(k => (s[0][k] >= s[1][k] ? 1 : 0));
    case 'cmp': return each(k => (s[0][k] >= 0 ? s[1][k] : s[2][k]));
    case 'frc': return each(k => s[0][k] - Math.floor(s[0][k]));
    case 'abs': return each(k => Math.abs(s[0][k]));
    case 'sgn': return each(k => Math.sign(s[0][k]));
    case 'rcp': return each(() => 1 / s[0][0]);
    case 'rsq': return each(() => 1 / Math.sqrt(Math.abs(s[0][0])));
    case 'exp': return each(() => 2 ** s[0][0]);
    case 'log': return each(() => Math.log2(Math.abs(s[0][0])));
    case 'pow': return each(() => (s[0][0] === 0 ? (s[1][0] > 0 ? 0 : 1) : Math.abs(s[0][0]) ** s[1][0]));
    case 'dp3': { const d = s[0][0] * s[1][0] + s[0][1] * s[1][1] + s[0][2] * s[1][2]; return [d, d, d, d]; }
    case 'dp4': { const d = s[0].reduce((a, v, k) => a + v * s[1][k], 0); return [d, d, d, d]; }
    case 'dp2add': { const d = s[0][0] * s[1][0] + s[0][1] * s[1][1] + s[2][0]; return [d, d, d, d]; }
    case 'nrm': { const f = 1 / Math.sqrt(Math.max(s[0][0] ** 2 + s[0][1] ** 2 + s[0][2] ** 2, 1e-30)); return s[0].map(v => v * f); }
    case 'crs': return [s[0][1] * s[1][2] - s[0][2] * s[1][1], s[0][2] * s[1][0] - s[0][0] * s[1][2], s[0][0] * s[1][1] - s[0][1] * s[1][0], 0];
    case 'sincos': return [Math.cos(s[0][0]), Math.sin(s[0][0]), 0, 0];
    case 'texld': {
      const c = texld === 'project' ? [s[0][0] / s[0][3], s[0][1] / s[0][3]] : [s[0][0], s[0][1]];
      return sample(c);
    }
    case 'dsx': case 'dsy': return [0, 0, 0, 0];
    default: throw new Error(`a program operation ${op}`);
  }
}

/** { output: [values] } of a program on one sample: `inputs` { uv0: [u, v], ..., color: [r, g, b, a], cameraVector:
 *  [x, y, z], worldPosition: [x, y, z] }, `textures` { texture key: ([u, v]) => [r, g, b, a] }. */
export function runProgram(program, inputs, textures) {
  const regs = new Map();
  const comp = s => {
    if (!s) return 0;
    const sc = s.scale ?? 1, b = s.bias ?? 0;
    if (s.kind === 'const') return s.value;
    if (s.kind === 'uv') return inputs[`uv${s.channel}`][s.component] * sc + b;
    if (s.kind === 'color') return inputs.color[s.component] * sc + b;
    if (s.kind === 'worldPosition' && s.component === 3) return sc;
    if (['cameraVector', 'worldPosition', 'worldTangent', 'worldBinormal', 'worldNormal'].includes(s.kind)) return inputs[s.kind][s.component] * sc;
    if (s.kind === 'tangentSign') return (inputs.tangentSign ?? 1) * sc;
    if (s.kind === 'vFace') return inputs.vFace ?? 1;
    throw new Error(`a program input of kind ${s.kind}`);
  };
  for (const [name, sources] of Object.entries(program.inputs ?? {})) regs.set(name, sources.map(comp));
  for (const [name, record] of Object.entries(program.constants ?? {})) regs.set(name, [...record.value]);
  for (const row of program.code ?? []) {
    let sample = null;
    const s = row.s.map(x => {
      if (x.r.startsWith('t')) { sample = textures[x.r]; return [0, 0, 0, 0]; }
      let v = swz(regs.get(x.r) ?? [0, 0, 0, 0], x.w);
      if (x.a) v = v.map(Math.abs);
      if (x.n) v = v.map(y => -y);
      return v;
    });
    let r = apply(row.op, s, sample, row.texld);
    if (row.sat) r = r.map(v => Math.min(1, Math.max(0, v)));
    const dest = regs.get(row.d) ?? [0, 0, 0, 0];
    for (const c of row.m) dest[C.indexOf(c)] = r[C.indexOf(c)];
    regs.set(row.d, dest);
  }
  const out = {};
  for (const [name, o] of Object.entries(program.outputs ?? {})) {
    out[name] = 'value' in o ? [...o.value] : [...o.m].map(c => (regs.get(o.r) ?? [0, 0, 0, 0])[C.indexOf(c)]);
  }
  return out;
}

// ---------------------------------------------------------------------------------------------------------------
// A uniform that moves with time (game-likeness plan, A8): its expression tree (the export's `vector`, or `scalars`'
// trees) worked out each frame, as shader_slice.evaluate_uniform does it at time 0.

const ONE = { SquareRoot: x => Math.sqrt(Math.max(x, 0)), Abs: Math.abs, Floor: Math.floor, Ceil: Math.ceil,
              Frac: x => x - Math.floor(x), Periodic: x => x - Math.floor(x) };
/** [r, g, b, a] of a uniform expression (the export's JSON form) with the material's values ({ vectors, scalars })
 *  at `time` (seconds). Throws on a kind it doesn't work out. */
export function evaluateUniform(expr, values, time) {
  const ev = e => evaluateUniform(e, values, time), a = expr.args ?? [];
  switch (expr.kind) {
    case 'Constant': return [...expr.value];
    case 'VectorParameter': { const v = values?.vectors?.[expr.name] ?? expr.default; return [0, 1, 2, 3].map(k => +(v[k] ?? 0)); }
    case 'ScalarParameter': { const v = +(values?.scalars?.[expr.name] ?? expr.default); return [v, v, v, v]; }
    case 'XComVectorParameter': return [1, 1, 1, 1];
    case 'Time': case 'RealTime': return [time, time, time, time];
    case 'Sine': { const x = ev(a[0])[0], s = expr.cosine ? Math.cos(x) : Math.sin(x); return [s, s, s, s]; }
    case 'Length': { const x = ev(a[0]), l = Math.hypot(x[0], x[1], x[2]); return [l, l, l, l]; }
    case 'Min': case 'Max': case 'Fmod': {
      const x = ev(a[0]), y = ev(a[1]);
      const f = expr.kind === 'Min' ? Math.min : expr.kind === 'Max' ? Math.max : (p, q) => (q ? p % q : 0);
      return x.map((p, k) => f(p, y[k]));
    }
    case 'Clamp': { const x = ev(a[0]), lo = ev(a[1]), hi = ev(a[2]); return x.map((p, k) => Math.min(Math.max(p, lo[k]), hi[k])); }
    case 'FoldedMath': {
      const x = ev(a[0]), y = ev(a[1]);
      if (expr.op === 'dot') { const d = x[0] * y[0] + x[1] * y[1] + x[2] * y[2]; return [d, d, d, d]; }
      const f = { add: (p, q) => p + q, sub: (p, q) => p - q, mul: (p, q) => p * q, div: (p, q) => (q ? p / q : 0) }[expr.op];
      if (!f) throw new Error(`folded maths ${expr.op}`);
      return x.map((p, k) => f(p, y[k]));
    }
    case 'AppendVector': { const x = ev(a[0]), y = ev(a[1]), n = expr.componentsA; return [...x.slice(0, n), ...y].slice(0, 4).concat([0, 0, 0, 0]).slice(0, 4); }
    default:
      if (ONE[expr.kind]) return ev(a[0]).map(ONE[expr.kind]);
      throw new Error(`a uniform expression of kind ${expr.kind}`);
  }
}

/** A program constant's four values at `time`: its `vector`'s, or its `scalars`' one a component, else its value. */
export function constantAt(record, values, time) {
  if (record.vector) return evaluateUniform(record.vector, values, time);
  if (record.scalars) return record.value.map((v, k) => (record.scalars[k] ? evaluateUniform(record.scalars[k], values, time)[0] : v));
  return [...record.value];
}

/** [r, g, b] the game multiplies a light by at `time` (seconds): its light function's program (a light record's
 *  `lightFunction.program`, export 46; game-likeness plan, F1), its constants worked out at that time and run with no
 *  inputs. Throws on a kind it doesn't work out. */
export function lightFunctionAt(program, time) {
  const constants = Object.fromEntries(Object.entries(program.constants ?? {})
    .map(([name, record]) => [name, { value: constantAt(record, {}, time) }]));
  return runProgram({ ...program, constants }, {}, {}).light.slice(0, 3);
}
