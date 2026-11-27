// The map's height fog as the game draws it (game-likeness plan, C2): the exponential height fog of the game's
// global shader cache (TExponentialHeightFogPixelShader, read 27 November 2026), worked out in each lit material's
// shader so that a change of a value recompiles nothing (one shared set of uniforms). Pure: GLSL text and numbers, no
// three.js; lighting.js puts the chunk in the shared local-lights patch and sets the shared uniforms, and the effects'
// likenesses (effects_preview.js) draw in the same fog.
//
// The game's shader (exp is base 2 in SM3): ray = the pixel less the camera (game units, z up);
//   rz = |ray.z| < 0.01 ? 0.01 : ray.z;  integral = (1 - 2^(-rz f)) / (rz f);
//   amount = max(length(ray) - start, 0) * density * 2^(-f (camera z - height)) * integral;
//   T = max(saturate(2^-amount), 1 - max opacity);  lobe = pow(0.5 - 0.499 dot(L, ray / length), p);
//   pixel = pixel * T + (1 - T) * mix(opposite colour, inscattering colour, lobe)
// with L the dominant light's direction of travel. UE3 keeps the density and falloff a thousand times smaller than its
// artists edit them, and works out p so that the colours are half and half at the light terminator angle.

/** The uniforms' names and the values of no fog (the Neutral look, a map without fog). */
export function fogUniformsNone() {
  return { fogOn: 0, fogDensity: 0, fogHeight: 0, fogFalloff: 0.001, fogStart: 0, fogFloor: 1, fogPower: 1,
           fogInscatter: [0, 0, 0], fogOpposite: [0, 0, 0], fogLight: [0, 0, -1] };
}

// the colours are UE3 Colors (a byte a channel: the export gives them over 255), which the engine makes linear by its
// 2.2 power before the fog's shader takes them (an FLinearColor of an FColor)
const linear = c => (Array.isArray(c) ? c.slice(0, 3).map(v => Math.pow(Math.max(0, Number(v) || 0), 2.2)) : [0, 0, 0]);

/** The power that makes the colours half and half at `angle` degrees from the light (UE3's light terminator). */
export function terminatorPower(angle) {
  const base = 0.5 + 0.499 * Math.cos((Math.min(179, Math.max(1, angle)) * Math.PI) / 180);
  return Math.log(0.5) / Math.log(Math.min(0.999, Math.max(0.001, base)));
}

/** The uniforms' values for a map's fog (the export's atmosphere.world.fog: every member filled) and its dominant
 *  light's direction of travel in the game's axes ([x, y, z], or null). No fog where it is off or absent. */
export function fogUniforms(fog, lightDirection = null) {
  if (!fog || !fog.bEnabled) return fogUniformsNone();
  const scale = (colour, brightness) => linear(colour).map(v => v * (Number(brightness) || 0));
  const d = lightDirection && Math.hypot(...lightDirection) > 0 ? lightDirection.map(v => v / Math.hypot(...lightDirection)) : [0, 0, -1];
  return {
    fogOn: 1,
    fogDensity: (Number(fog.FogDensity) || 0) / 1000,
    fogHeight: Number(fog.FogHeight) || 0,
    fogFalloff: Math.max(1e-6, (Number(fog.FogHeightFalloff) || 0) / 1000),
    fogStart: Number(fog.StartDistance) || 0,
    fogFloor: 1 - Math.min(1, Math.max(0, Number(fog.FogMaxOpacity ?? 1))),
    fogPower: terminatorPower(Number(fog.LightTerminatorAngle ?? 45)),
    fogInscatter: scale(fog.LightInscatteringColor, fog.LightInscatteringBrightness),
    fogOpposite: scale(fog.OppositeLightColor, fog.OppositeLightBrightness),
    fogLight: d,
  };
}

/** The fog's transmittance and colour for a pixel, in numbers ([T, [r, g, b]]): the node test holds the GLSL's sums
 *  to it, and a tool can ask how much fog a place has. `world` and `camera` in the game's axes. */
export function fogAt(u, world, camera) {
  if (!u.fogOn) return [1, [0, 0, 0]];
  const ray = [0, 1, 2].map(k => world[k] - camera[k]);
  const length = Math.hypot(...ray);
  const rz = Math.abs(ray[2]) < 0.01 ? 0.01 : ray[2];
  const integral = (1 - 2 ** (-rz * u.fogFalloff)) / (rz * u.fogFalloff);
  const collapsed = u.fogDensity * 2 ** Math.min(126, Math.max(-125, -u.fogFalloff * (camera[2] - u.fogHeight)));
  const amount = Math.max(length - u.fogStart, 0) * collapsed * integral;
  const t = Math.max(Math.min(1, Math.max(0, 2 ** -amount)), u.fogFloor);
  const dot = length > 0 ? (u.fogLight[0] * ray[0] + u.fogLight[1] * ray[1] + u.fogLight[2] * ray[2]) / length : 0;
  const lobe = Math.pow(Math.max(0, 0.5 - 0.499 * dot), u.fogPower);
  return [t, [0, 1, 2].map(k => (1 - t) * (u.fogOpposite[k] + lobe * (u.fogInscatter[k] - u.fogOpposite[k])))];
}

/** The one set of fog uniforms every shader drawn in the map's fog shares ({ value } holders, which three reads as
 *  they are: a vec3's value an array): lighting.js sets them with the look, so a change recompiles nothing. */
export const fogShared = Object.fromEntries(Object.entries(fogUniformsNone()).map(([name, value]) => [name, { value }]));
/** Set the shared uniforms (fogUniforms' or fogUniformsNone's values). */
export function setFog(values) {
  for (const [name, value] of Object.entries(values)) fogShared[name].value = Array.isArray(value) ? [...value] : value;
}

/** The uniforms' declarations and the fog as a function of a pixel's world place in the view's axes (x, up, y): the
 *  fog's colour already weighed by how much of it there is (rgb) and how much of the pixel shows through it (a).
 *  cameraPosition is three's (every material but a raw shader has it). Fragment. */
export const FOG_PARS = `uniform float fogOn;
uniform float fogDensity;
uniform float fogHeight;
uniform float fogFalloff;
uniform float fogStart;
uniform float fogFloor;
uniform float fogPower;
uniform vec3 fogInscatter;
uniform vec3 fogOpposite;
uniform vec3 fogLight;
vec4 heightFog( vec3 world ) {
	if ( fogOn < 0.5 ) return vec4( 0.0, 0.0, 0.0, 1.0 );
	vec3 fogRay = ( world - cameraPosition ).xzy;
	float fogLength = length( fogRay );
	float fogRz = abs( fogRay.z ) < 0.01 ? 0.01 : fogRay.z;
	float fogIntegral = ( 1.0 - exp2( - fogRz * fogFalloff ) ) / ( fogRz * fogFalloff );
	float fogCollapsed = fogDensity * exp2( clamp( - fogFalloff * ( cameraPosition.y - fogHeight ), -125.0, 126.0 ) );
	float fogT = max( clamp( exp2( - max( fogLength - fogStart, 0.0 ) * fogCollapsed * fogIntegral ), 0.0, 1.0 ), fogFloor );
	float fogLobe = pow( max( 0.5 - 0.499 * dot( fogLight, fogRay / max( fogLength, 1e-6 ) ), 0.0 ), fogPower );
	return vec4( ( 1.0 - fogT ) * mix( fogOpposite, fogInscatter, fogLobe ), fogT );
}`;

/** The fog put on an opaque or normally blended gl_FragColor (after three's own fog chunk): `world` the pixel's world
 *  place in the view's axes (x, up, y). */
export const fogChunk = world => `{ vec4 fogged = heightFog( ${world} ); gl_FragColor.rgb = gl_FragColor.rgb * fogged.a + fogged.rgb; }`;
