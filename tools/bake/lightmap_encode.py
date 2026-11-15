"""EW's directional lightmap codec: direct light from static lights into `NormalizedAverageColor` and
`DirectionalMaxComponent` (baker design, section 4.7; fitted to UDK Lightmass bakes in EXP-18).

For texels with world positions and tangent frames (tangent, binormal, normal), every light adds per-colour
coefficients for the three directional channels:

  C_i = k * c * A * S(e, alpha) * max(0, l . b_i)   (the clamp softened over the light's apparent size; see lobes)

- l is the unit direction from the texel to the light (for a point or spot light, to its centre), written in the
  texel's tangent frame; e is its elevation over the surface (sin e = l . normal);
- b_i is UE3's lightmap basis in the tangent frame (azimuths 90, 210 and 330 degrees, 35.3 degrees up);
- k is the brightness and c the linear colour (the light's colour bytes / 255, to the power 2.2);
- A is the attenuation: 1 for a directional light; (1 - (d / R)^2)^F for a point light of radius R and falloff
  exponent F; that times clamp((cos theta - cos outer) / (cos inner - cos outer), 0, 1)^2 for a spot light;
- S(e, alpha) = 2 sin e (1 - 0.55 alpha^2) + (0.114 + 1.84 alpha) cos^2 e, with alpha the light's angular radius as
  Lightmass sees it: asin(LightSourceRadius / d) for point and spot lights, LightSourceAngle for a directional one.

Then `NormalizedAverageColor` = sum_i C_i normalised to its largest colour channel and `DirectionalMaxComponent`_i =
the largest colour channel of C_i, divided by the receiver's per-channel scale (the largest value of that channel);
both are stored to the power 1 / 2.2. Shadows and bounce light are not modelled.
"""
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from lights import effective_cone  # noqa: E402

R6, R2, R3 = np.sqrt(6.0), np.sqrt(2.0), np.sqrt(3.0)
BASIS = np.array([[0.0, R6 / 3, 1 / R3], [-1 / R2, -1 / R6, 1 / R3], [1 / R2, -1 / R6, 1 / R3]])
# S(e, alpha) fit over BakeCalib6 and 7 (EXP-18; evidence udk-lightmass-calibration-2026-11-06.json, pointSpotModel)
S_C0, S_C1, S_K = 0.114, 1.8361, 0.5505
# The largest angular radius the fit saw (EXP-18: 20% rms there). Beyond it the fit is extrapolation and turns
# negative at 77 degrees, as it did on URB_Bar's ceiling texels a few units from a lamp, so alpha is capped here.
ALPHA_MAX = np.radians(51.0)
# The clamped lobe max(0, l . b) averaged over a spread of directions as wide as the light looks: half-width
# LOBE_SPREAD * alpha * sqrt(1 - (l . b)^2) (fitted on BakeCalib7, all channels: 13.9% -> 9.1% rms)
LOBE_SPREAD = 1.77
GAMMA = 2.2
UDK_POINT_SOURCE_RADIUS = 100.0       # LightmassPointLightSettings default in UDK's Engine.u
UDK_DIRECTIONAL_SOURCE_ANGLE = 3.0    # LightmassDirectionalLightSettings default, degrees


def elevation_term(sin_e, alpha):
    """S(e, alpha), with alpha capped at ALPHA_MAX; zero for light from below the surface."""
    sin_e = np.asarray(sin_e, float)
    alpha = np.minimum(np.asarray(alpha, float), ALPHA_MAX)
    s = 2 * sin_e * (1 - S_K * alpha ** 2) + (S_C0 + S_C1 * alpha) * (1 - sin_e ** 2)
    return np.where(sin_e > 0, np.maximum(s, 0.0), 0.0)


def lobes(l_ts, alpha):
    """(n, 3) channel weights: max(0, l . b_i), softened near zero for a light of angular radius alpha (the mean of
    max(0, x) over x within +-LOBE_SPREAD * alpha * sqrt(1 - (l . b_i)^2) of l . b_i)."""
    mu = l_ts @ BASIS.T
    w = LOBE_SPREAD * np.asarray(alpha, float)[:, None] * np.sqrt(np.maximum(0.0, 1 - mu ** 2))
    safe = np.maximum(w, 1e-9)
    soft = (mu + safe) ** 2 / (4 * safe)
    return np.where(mu >= w, mu, np.where(mu <= -w, 0.0, soft))


def linear_colour(color):
    """A light's linear colour from its colour as 0-1 values (bytes / 255)."""
    return np.asarray(color[:3], float) ** GAMMA


def light_contribution(light, world, frames):
    """(n, 3 basis, 3 colour) coefficients of one light at n texels.

    light: dict with kind ('directional', 'point', 'spot'), brightness, color (0-1), and
      directional: toLight (unit vector towards the light), lightSourceAngle (degrees, optional);
      point/spot: location, radius, falloffExponent, lightSourceRadius (optional);
      spot: direction (unit axis), innerConeAngle, outerConeAngle (degrees, stored: lights.effective_cone clamps them).
    world: (n, 3) texel positions; frames: (n, 3, 3) rows tangent, binormal, normal (unit)."""
    kind = light['kind']
    n = len(world)
    if kind == 'directional':
        l = np.broadcast_to(np.asarray(light['toLight'], float), (n, 3))
        att = np.ones(n)
        alpha = np.full(n, np.radians(light.get('lightSourceAngle', UDK_DIRECTIONAL_SOURCE_ANGLE)))
    elif kind in ('point', 'spot'):
        L = np.asarray(light['location'], float) - world
        d = np.linalg.norm(L, axis=1)
        d = np.maximum(d, 1e-6)
        l = L / d[:, None]
        R, F = float(light['radius']), float(light['falloffExponent'])
        base = np.maximum(0.0, 1 - (d / R) ** 2)
        att = base ** F if F > 0 else (d < R).astype(float)
        if kind == 'spot':
            # the effective cone (lights.effective_cone): stored angles above 89 degrees bake as UE3 clamps them
            inner, outer = effective_cone(light['innerConeAngle'], light['outerConeAngle'])
            cos_o, cos_i = np.cos(outer), np.cos(inner)
            s = (-l) @ np.asarray(light['direction'], float)
            att = att * np.clip((s - cos_o) / max(cos_i - cos_o, 1e-6), 0, 1) ** 2
        rho = float(light.get('lightSourceRadius', UDK_POINT_SOURCE_RADIUS))
        alpha = np.minimum(np.arcsin(np.minimum(1.0, rho / d)), ALPHA_MAX)
    else:
        raise ValueError(f'unsupported light kind {kind}')
    l_ts = np.einsum('nij,nj->ni', frames, l)
    weight = float(light.get('brightness', 1.0)) * att * elevation_term(l_ts[:, 2], alpha)
    return (weight[:, None] * lobes(l_ts, alpha))[:, :, None] * linear_colour(light['color'])[None, None, :]


def coefficients(lights, world, frames, visibility=None):
    """Summed (n, 3 basis, 3 colour) coefficients. `visibility(light, lit)`, when given, returns the fraction of the
    light seen from each texel where `lit` (a boolean mask of the texels the light reaches) is true (shadows.py)."""
    world = np.asarray(world, float)
    frames = np.asarray(frames, float)
    total = np.zeros((len(world), 3, 3))
    for light in lights:
        c = light_contribution(light, world, frames)
        if visibility is not None:
            lit = c.reshape(len(world), -1).max(1) > 0
            if lit.any():
                c[lit] *= np.asarray(visibility(light, lit), float)[:, None, None]
        total += c
    return total


def encode(coef):
    """Texel values (0-1, as stored) and the slot scales for (n, 3 basis, 3 colour) coefficients.

    Returns dict(nac=(n, 3), dmc=(n, 3), dmcScale=[3 floats], nacLinear, dmcLinear). Unlit texels store 0.
    Negative coefficients (light cannot be negative; only rounding or a bad model makes them) count as 0, so the
    stored values stay finite."""
    coef = np.maximum(np.nan_to_num(np.asarray(coef, float)), 0.0)
    total = coef.sum(1)                                           # (n, 3 colour)
    peak = total.max(1)
    nac_linear = np.where(peak[:, None] > 0, total / np.where(peak > 0, peak, 1)[:, None], 0.0)
    dmc_linear = coef.max(2)                                      # (n, 3 basis)
    scale = dmc_linear.max(0)
    scale = np.where(scale > 0, scale, 1.0)
    return dict(nac=nac_linear ** (1 / GAMMA), dmc=(dmc_linear / scale) ** (1 / GAMMA),
                dmcScale=[float(v) for v in scale], nacLinear=nac_linear, dmcLinear=dmc_linear)


def decode(nac, dmc, dmc_scale):
    """The game's reading of stored texels (EXP-17): colour and the three directional values, linear."""
    return np.asarray(nac, float) ** GAMMA, np.asarray(dmc, float) ** GAMMA * np.asarray(dmc_scale, float)
