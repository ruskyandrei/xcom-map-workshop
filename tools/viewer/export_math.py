"""Game-space transforms and the single game-to-viewer basis conversion."""
import math


def multiply(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transform(location, rotation, scale):
    pitch, yaw, roll = [v * math.tau / 65536 for v in rotation]
    cp, sp, cy, sy, cr, sr = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw), math.cos(roll), math.sin(roll)
    axes = [(cp*cy, cp*sy, sp), (sr*sp*cy-cr*sy, sr*sp*sy+cr*cy, -sr*cp),
            (-cr*sp*cy-sr*sy, cy*sr-cr*sp*sy, cr*cp)]
    return [[axes[j][i]*scale[j] if j < 3 else location[i] for j in range(4)]
            for i in range(3)] + [[0, 0, 0, 1]]


def forward(rotation):
    """The rotator's X axis in game space: where a light or actor faces."""
    return [row[0] for row in transform([0, 0, 0], rotation, [1, 1, 1])[:3]]


def view_matrix(matrix):
    order = (0, 2, 1, 3)
    return [matrix[order[i]][order[j]] for j in range(4) for i in range(4)]
