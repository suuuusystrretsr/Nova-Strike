from ursina import color


def install_color_compat() -> None:
    """Make color.rgb/rgba accept both 0..1 and 0..255 arguments safely."""
    if getattr(color, "_nova_strike_color_compat", False):
        return

    original_rgb = color.rgb
    original_rgba = color.rgba

    def _clamp_byte(v):
        return max(0, min(255, int(v)))

    def rgb_compat(r, g, b):
        if max(r, g, b) > 1:
            return color.rgb32(_clamp_byte(r), _clamp_byte(g), _clamp_byte(b))
        return original_rgb(r, g, b)

    def rgba_compat(r, g, b, a):
        if max(r, g, b, a) > 1:
            return color.rgba32(_clamp_byte(r), _clamp_byte(g), _clamp_byte(b), _clamp_byte(a))
        return original_rgba(r, g, b, a)

    color.rgb = rgb_compat
    color.rgba = rgba_compat
    color._nova_strike_color_compat = True
