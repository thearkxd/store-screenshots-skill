#!/usr/bin/env python3
"""3D devices: a real screen on a phone body turned in space.

The screen is mapped onto the device's front face with the exact perspective transform a camera applies to a
flat object (a homography), so every pixel of the UI is there: nothing is redrawn, nothing is stretched,
the screen keeps its proportions in 3D. The body is drawn around it in the same camera and lit by one light:
- black glass;
- a rounded slab with a metal band;
- side buttons;
- the island or the punch hole.

Used by scene.py ("type": "device3d", references/scene-format.md §5); Pillow only.

Conventions (degrees):
- yaw > 0 turns the face to the viewer's right;
- pitch > 0 tilts the face up;
- roll > 0 turns it clockwise in the picture.

The camera's fov is the vertical field of view that the device's height fills; smaller is flatter, like a long
lens. The light is a direction in camera space (x right, y down, z away from the viewer) pointing from the
device towards the light.
"""
import math

from PIL import Image, ImageDraw, ImageFilter

MODELS = {  # all fractions of the body width
    "island": {"radius": 0.155, "bezel": 0.03, "thickness": 0.112, "cutout": "island", "buttons": "iphone"},
    "punch": {"radius": 0.1, "bezel": 0.026, "thickness": 0.1, "cutout": "punch", "buttons": "android"},
    "slab": {"radius": 0.075, "bezel": 0.034, "thickness": 0.095, "cutout": None, "buttons": None},
}
# side buttons: (side, top, bottom) as fractions of the body height; side -1 = left, +1 = right
BUTTONS = {"iphone": [(-1, 0.178, 0.212), (-1, 0.252, 0.31), (-1, 0.33, 0.388), (1, 0.27, 0.365)],
           "android": [(1, 0.2, 0.25), (1, 0.29, 0.39)]}
LIMITS = {"yaw": 40.0, "pitch": 30.0, "roll": 25.0}
FOV = (6.0, 60.0)
CAMERA = {"fov": 22.0, "light": [-0.45, -0.75, -0.5]}
GLASS = (10, 10, 11)
FRAMES = {"titanium": "#8F8A84", "graphite": "#3A3A3C", "silver": "#D9D7D2", "black": "#1E1E20", "white": "#ECEBE7"}
READABLE = 0.72  # far side vs near side: below this the UI on the far side stops reading


class DeviceError(ValueError):
    pass


# ------------------------------------------------------------------ small linear algebra

def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mat_vec(m, v):
    return [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3)]


def mat_inv(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    co = [[e * i - f * h, -(b * i - c * h), b * f - c * e],
          [-(d * i - f * g), a * i - c * g, -(a * f - c * d)],
          [d * h - e * g, -(a * h - b * g), a * e - b * d]]
    det = a * co[0][0] + b * co[1][0] + c * co[2][0]
    if abs(det) < 1e-12:
        raise DeviceError("degenerate projection")
    return [[co[r][k] / det for k in range(3)] for r in range(3)]


def norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def rotation(yaw, pitch, roll):
    a, b, c = math.radians(-yaw), math.radians(-pitch), math.radians(roll)
    ry = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
    rx = [[1, 0, 0], [0, math.cos(b), -math.sin(b)], [0, math.sin(b), math.cos(b)]]
    rz = [[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]]
    return mat_mul(rz, mat_mul(rx, ry))


def hmap(H, x, y):
    w = H[2][0] * x + H[2][1] * y + H[2][2]
    return ((H[0][0] * x + H[0][1] * y + H[0][2]) / w, (H[1][0] * x + H[1][1] * y + H[1][2]) / w)


def hex_rgb(c):
    h = c.lstrip("#")
    return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))


def convex_hull(pts):
    pts = sorted(set((round(x, 3), round(y, 3)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def rounded_outline(w, h, r, n=32):
    """Clockwise outline of a rounded rectangle centred on 0 (y down), with the outward normal at each point."""
    r = max(0.0, min(r, w / 2, h / 2))
    pts, nrm = [], []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180)):
        for i in range(n + 1):
            t = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
            nrm.append((math.cos(t), math.sin(t)))
    return pts, nrm


# ------------------------------------------------------------------ the device

class Device:
    """Geometry of one device in canvas pixels. place(ox, oy) sets where the device's centre projects, then
    render() draws it; until then bbox is relative to that centre."""

    def __init__(self, screen_size, width_px, yaw=0.0, pitch=0.0, roll=0.0, model="island", body=None, camera=None):
        for k, v in (("yaw", yaw), ("pitch", pitch), ("roll", roll)):
            if abs(v) > LIMITS[k]:
                raise DeviceError(f"{k} {v:g}° is past {LIMITS[k]:g}° - beyond that the UI stops reading; turn it less")
        if model not in MODELS:
            raise DeviceError(f"model {model!r}: {', '.join(MODELS)}")
        spec = dict(MODELS[model], **{k: v for k, v in (body or {}).items() if k in ("radius", "bezel", "thickness", "cutout", "buttons")})
        cam = dict(CAMERA, **(camera or {}))
        if not FOV[0] <= float(cam["fov"]) <= FOV[1]:
            raise DeviceError(f"camera fov {cam['fov']}: {FOV[0]:g}-{FOV[1]:g}°")
        self.spec, self.cam = spec, cam
        self.angles = (float(yaw), float(pitch), float(roll))
        self.light = norm([float(v) for v in cam["light"]])
        colour = (body or {}).get("color", "titanium")
        self.frame = hex_rgb(FRAMES.get(colour, colour))
        sw_src, sh_src = screen_size
        W = float(width_px)
        b = spec["bezel"] * W
        self.sw = W - 2 * b                      # screen width on the device, px at scale 1
        self.sh = self.sw * sh_src / sw_src
        self.W, self.Hb = W, self.sh + 2 * b
        self.T = spec["thickness"] * W
        self.R = spec["radius"] * W
        self.r_screen = max(0.0, self.R - b)
        self.src_size = (sw_src, sh_src)
        self.rot = rotation(*self.angles)
        self.D = self.Hb / (2 * math.tan(math.radians(float(cam["fov"])) / 2))
        self.ox = self.oy = 0.0
        self._geometry()

    # -- projection
    def world(self, p):
        x, y, z = mat_vec(self.rot, p)
        return [x, y, z + self.D]

    def proj(self, p):
        x, y, z = self.world(p)
        return (self.ox + self.D * x / z, self.oy + self.D * y / z)

    def H(self):
        """Homography: screen-source pixels (u, v) -> canvas pixels."""
        su, sv = self.sw / self.src_size[0], self.sh / self.src_size[1]
        z0 = -self.T / 2
        A = [[su, 0, -self.sw / 2], [0, sv, -self.sh / 2], [0, 0, z0]]
        M = mat_mul(self.rot, A)
        M[2][2] += self.D
        K = [[self.D, 0, self.ox], [0, self.D, self.oy], [0, 0, 1]]
        return mat_mul(K, M)

    def _geometry(self):
        self.outline, self.normals = rounded_outline(self.W, self.Hb, self.R)
        z0, z1 = -self.T / 2, self.T / 2
        front = [(x, y, z0) for x, y in self.outline]
        back = [(x, y, z1) for x, y in self.outline]
        pts = [self.proj(p) for p in front + back]
        for side, top, bot in BUTTONS.get(self.spec.get("buttons") or "", []):
            x = side * self.W / 2 * (1 + 2 * self.BUTTON_OUT)
            for y in (top, bot):
                pts.append(self.proj((x, -self.Hb / 2 + y * self.Hb, 0)))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.rel_bbox = (min(xs) - self.ox, min(ys) - self.oy, max(xs) - self.ox, max(ys) - self.oy)
        # how much the UI is foreshortened: local scale (canvas px per source px) over the screen
        H = self.H()
        sc = []
        for u, v in ((0.02, 0.02), (0.98, 0.02), (0.98, 0.98), (0.02, 0.98), (0.5, 0.5), (0.02, 0.5), (0.98, 0.5), (0.5, 0.02), (0.5, 0.98)):
            x, y = u * self.src_size[0], v * self.src_size[1]
            p0, px, py = hmap(H, x, y), hmap(H, x + 1, y), hmap(H, x, y + 1)
            sc.append((math.dist(p0, px), math.dist(p0, py)))
        self.scale_min = min(min(a, b) for a, b in sc)
        self.scale_max = max(max(a, b) for a, b in sc)

    def place(self, ox, oy):
        self.ox, self.oy = float(ox), float(oy)
        return self

    def bbox(self):
        b = self.rel_bbox
        return (b[0] + self.ox, b[1] + self.oy, b[2] + self.ox, b[3] + self.oy)

    def screen_quad(self):
        H = self.H()
        w, h = self.src_size
        return [hmap(H, 0, 0), hmap(H, w, 0), hmap(H, w, h), hmap(H, 0, h)]

    def facing(self, n_local, p_local):
        """True if a surface with this local normal, at this local point, faces the camera."""
        return dot(mat_vec(self.rot, n_local), self.world(p_local)) < 0

    def shade(self, rgb, n_local, p_local, ambient=0.38, diffuse=0.62, spec=0.5, shine=22):
        n = norm(mat_vec(self.rot, n_local))
        v = norm([-c for c in self.world(p_local)])
        d = max(0.0, dot(n, self.light))
        hv = norm([self.light[i] + v[i] for i in range(3)])
        s = max(0.0, dot(n, hv)) ** shine
        return tuple(max(0, min(255, int(c * (ambient + diffuse * d) + 255 * spec * s))) for c in rgb) + (255,)

    # -- drawing
    def render(self, screen, ss=3):
        """-> (RGBA image of the device, (x, y) of its top-left on the canvas). screen: the source screen image."""
        bx0, by0, bx1, by1 = self.bbox()
        X0, Y0 = math.floor(bx0) - 2, math.floor(by0) - 2
        w, h = math.ceil(bx1) + 2 - X0, math.ceil(by1) + 2 - Y0
        if w * h * ss * ss > 60_000_000:
            ss = 2
        big = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)

        def P(p):
            x, y = self.proj(p)
            return ((x - X0) * ss, (y - Y0) * ss)
        z0, z1 = -self.T / 2, self.T / 2
        outline, normals = self.outline, self.normals
        n = len(outline)
        front = [P((x, y, z0)) for x, y in outline]
        back = [P((x, y, z1)) for x, y in outline]
        buttons = self._buttons()
        for bt in buttons:  # buttons on the far side sit behind the slab
            if not self.facing(bt["n"], bt["c"]):
                self._draw_box(d, bt, P)
        # the slab: its silhouette first (no seams can open), then every side facet that faces the camera
        mid = self.shade(self.frame, (0, 0, -1), (0, 0, 0), ambient=0.5, diffuse=0.3, spec=0.0)
        d.polygon(convex_hull(front + back), fill=mid)
        facets = []
        for i in range(n):
            j = (i + 1) % n
            nx, ny = (normals[i][0] + normals[j][0]) / 2, (normals[i][1] + normals[j][1]) / 2
            nl = (nx, ny, 0.0)
            c = ((outline[i][0] + outline[j][0]) / 2, (outline[i][1] + outline[j][1]) / 2, 0.0)
            if not self.facing(nl, c):
                continue
            depth = self.world(c)[2]
            facets.append((depth, [front[i], front[j], back[j], back[i]], self.shade(self.frame, nl, c)))
        for _, quad, col in sorted(facets, key=lambda f: -f[0]):
            d.polygon(quad, fill=col, outline=col)
        for bt in buttons:
            if self.facing(bt["n"], bt["c"]):
                self._draw_box(d, bt, P)
        # the metal rim around the glass, then the glass
        rim = 0.0065 * self.W
        inner = [(x - nx * rim, y - ny * rim) for (x, y), (nx, ny) in zip(outline, normals)]
        rim_base = self.shade(self.frame, (0, 0, -1), (0, 0, z0), ambient=0.62, diffuse=0.38, spec=0.25)
        d.polygon(front, fill=rim_base)
        for i in range(n):
            j = (i + 1) % n
            nl = ((normals[i][0] + normals[j][0]) * 0.35, (normals[i][1] + normals[j][1]) * 0.35, -0.7)
            c = (outline[i][0], outline[i][1], z0)
            col = self.shade(self.frame, nl, c, ambient=0.55, diffuse=0.45, spec=0.6, shine=30)
            d.polygon([front[i], front[j], P((*inner[j], z0)), P((*inner[i], z0))], fill=col, outline=col)
        d.polygon([P((x, y, z0)) for x, y in inner], fill=GLASS + (255,))
        body = big.reduce(ss) if ss > 1 else big
        # the screen: pre-scaled with an area filter, then one perspective resample; edges from a hi-res mask
        H = self.H()
        H_local = mat_mul([[1, 0, -X0], [0, 1, -Y0], [0, 0, 1]], H)
        k = min(1.0, self.scale_max)
        src = screen.convert("RGB")
        if k < 0.999:
            src = src.resize((max(1, round(src.width * k)), max(1, round(src.height * k))), Image.LANCZOS)
        pre = [[src.width / self.src_size[0], 0, 0], [0, src.height / self.src_size[1], 0], [0, 0, 1]]
        Hs = mat_mul(H_local, mat_inv(pre))  # pre-scaled source px -> local px
        inv = mat_inv(Hs)
        coeffs = [inv[r][c] / inv[2][2] for r in range(3) for c in range(3)][:8]
        warped = src.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
        mask = Image.new("L", (w * ss, h * ss), 0)
        md = ImageDraw.Draw(mask)
        so, _ = rounded_outline(self.sw, self.sh, self.r_screen, n=40)
        md.polygon([P((x, y, z0)) for x, y in so], fill=255)
        cut = self._cutout()
        if cut:
            cm = Image.new("L", mask.size, 0)
            ImageDraw.Draw(cm).polygon([P((x, y, z0)) for x, y in cut], fill=255)
            cut_mask = cm.reduce(ss) if ss > 1 else cm
        mask = mask.reduce(ss) if ss > 1 else mask
        body.paste(warped, (0, 0), mask)
        if cut:
            body.paste(Image.new("RGBA", body.size, (0, 0, 0, 255)), (0, 0), cut_mask)
        return body, (X0, Y0)

    def _cutout(self):
        kind = self.spec.get("cutout")
        w = self.sw
        if kind == "island":  # the same proportions as the flat phone frame
            iw, ih = w * 0.305, w * 0.088
            pts, _ = rounded_outline(iw, ih, ih / 2, n=20)
            cy = -self.sh / 2 + w * 0.028 + ih / 2
            return [(x, y + cy) for x, y in pts]
        if kind == "punch":
            r = w * 0.017
            cy = -self.sh / 2 + w * 0.034
            return [(r * math.cos(t / 40 * 2 * math.pi), cy + r * math.sin(t / 40 * 2 * math.pi)) for t in range(40)]
        return None

    BUTTON_OUT = 0.0075  # how far a button stands out of the side, fraction of the body width

    def _buttons(self):
        """Side buttons as rounded (stadium) keys standing out of the side band."""
        out = []
        for side, top, bot in BUTTONS.get(self.spec.get("buttons") or "", []):
            x_in, x_out = side * self.W / 2, side * self.W / 2 * (1 + 2 * self.BUTTON_OUT)
            y0, y1 = -self.Hb / 2 + top * self.Hb, -self.Hb / 2 + bot * self.Hb
            zr = self.T * 0.26
            ring = []  # stadium in the (y, z) plane of the side: a cap at each end, joined by straight edges
            for yc, a0 in ((y0 + zr, 90), (y1 - zr, -90)):
                for i in range(13):
                    t = math.radians(a0 + 180 * i / 12)
                    ring.append((yc + zr * math.cos(t), zr * math.sin(t)))
            out.append({"side": side, "x": (x_in, x_out), "ring": ring, "n": (side, 0, 0), "c": (x_out, (y0 + y1) / 2, 0)})
        return out

    def _draw_box(self, d, bt, P):
        side = bt["side"]
        x_in, x_out = bt["x"]
        ring = bt["ring"]
        k = len(ring)
        cy = sum(p[0] for p in ring) / k
        for i in range(k):  # the short wall around the key, facing up/down/forward/back
            j = (i + 1) % k
            (ya, za), (yb, zb) = ring[i], ring[j]
            my, mz = (ya + yb) / 2, (za + zb) / 2
            ny, nz = zb - za, -(yb - ya)
            if ny * (my - cy) + nz * mz < 0:
                ny, nz = -ny, -nz
            nl = norm([0.0, ny, nz])
            c = (x_out, my, mz)
            if self.facing(nl, c):
                col = self.shade(self.frame, nl, c, spec=0.35)
                d.polygon([P((x_in, ya, za)), P((x_in, yb, zb)), P((x_out, yb, zb)), P((x_out, ya, za))], fill=col, outline=col)
        if self.facing(bt["n"], bt["c"]):  # the key's face, a touch brighter than the band it sits on
            col = self.shade(tuple(min(255, int(v * 1.06)) for v in self.frame), bt["n"], bt["c"])
            d.polygon([P((x_out, y, z)) for y, z in ring], fill=col, outline=col)


def shadow_for(rgba, spec, pad):
    """A soft shadow of the device's silhouette: (image, offset) to draw under it."""
    if not spec:
        return None
    blur, dx, dy = spec["blur"], spec.get("dx", 0), spec["dy"]
    a = rgba.getchannel("A")
    m = int(blur * 2 + pad)
    big = Image.new("L", (a.width + 2 * m, a.height + 2 * m), 0)
    big.paste(a, (m, m))
    big = big.filter(ImageFilter.GaussianBlur(max(1, blur / 2)))
    big = big.point(lambda v: int(v * spec.get("opacity", 0.3)))
    col = hex_rgb(spec.get("color", "#000000"))
    sh = Image.new("RGBA", big.size, col + (0,))
    sh.putalpha(big)
    return sh, (round(dx) - m, round(dy) - m)


if __name__ == "__main__":
    print(__doc__)
