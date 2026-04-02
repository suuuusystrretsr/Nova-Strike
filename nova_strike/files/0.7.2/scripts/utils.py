from ursina import Vec3, lerp


def lerp_vec3(a: Vec3, b: Vec3, t: float) -> Vec3:
    return Vec3(
        lerp(a.x, b.x, t),
        lerp(a.y, b.y, t),
        lerp(a.z, b.z, t),
    )


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))

