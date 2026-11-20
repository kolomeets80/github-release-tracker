"""Developer tool: regenerates icon.ico and the embedded icon data of github_release_tracker.py.

Needs Pillow (pip install pillow). Normal users and build.bat do NOT need this:
icon.ico and the embedded data are already committed.

    python tools/make_icons.py

Writes ../icon.ico and replaces the block between the BEGIN/END GENERATED markers
in ../github_release_tracker.py.
"""
import base64
import io
import math
import os
import re
import zlib

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SS = 16  # supersampling for the toolbar masks


# ---------------- app icon: release tag + amber "update" dot ----------------
def tag_icon(size):
    big = 1024
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    P = lambda x, y: (x * big, y * big)
    bg = "#0E7490"
    d.rounded_rectangle([0, 0, big - 1, big - 1], radius=int(big * 0.22), fill=bg)
    d.polygon([P(.18, .40), P(.56, .40), P(.80, .60), P(.56, .80), P(.18, .80)], fill="white")
    d.ellipse([.27 * big, .55 * big, .37 * big, .65 * big], fill=bg)
    cx, cy = P(.74, .27)
    d.ellipse([cx - .17 * big, cy - .17 * big, cx + .17 * big, cy + .17 * big], fill=bg)
    d.ellipse([cx - .125 * big, cy - .125 * big, cx + .125 * big, cy + .125 * big], fill="#F59E0B")
    return img.resize((size, size), Image.LANCZOS)


# ---------------- toolbar icons: one alpha mask each ----------------
def mask(fn, size):
    n = size * SS
    im = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(im)
    P = lambda x, y: (x * n, y * n)
    W = lambda w: max(1, int(w * n))
    fn(d, n, P, W)
    return im.resize((size, size), Image.LANCZOS)


def i_refresh(d, N, P, W):
    cx = cy = .5 * N
    r = .31 * N
    d.arc([cx - r, cy - r, cx + r, cy + r], start=25, end=300, fill=255, width=W(.12))
    a = math.radians(300)
    px, py = cx + r * math.cos(a), cy + r * math.sin(a)
    tx, ty = -math.sin(a), math.cos(a)
    nx, ny = math.cos(a), math.sin(a)
    h, w = .20 * N, .17 * N
    d.polygon([(px + tx * h, py + ty * h), (px + nx * w, py + ny * w), (px - nx * w, py - ny * w)], fill=255)


def i_check(d, N, P, W):
    """A checkbox with a tick (Mark as seen)."""
    d.rounded_rectangle([.1 * N, .1 * N, .9 * N, .9 * N], radius=.14 * N, outline=255, width=W(.1))
    d.line([P(.28, .52), P(.44, .68), P(.72, .34)], fill=255, width=W(.11), joint="curve")


def i_ext(d, N, P, W):
    d.line([P(.22, .78), P(.68, .32)], fill=255, width=W(.12))
    d.polygon([P(.86, .14), P(.44, .16), P(.84, .56)], fill=255)


def i_trash(d, N, P, W):
    d.rectangle([.14 * N, .2 * N, .86 * N, .29 * N], fill=255)
    d.rectangle([.38 * N, .1 * N, .62 * N, .21 * N], fill=255)
    d.polygon([P(.24, .36), P(.76, .36), P(.7, .9), P(.3, .9)], outline=255, width=W(.09))
    d.line([P(.42, .46), P(.43, .8)], fill=255, width=W(.07))
    d.line([P(.58, .46), P(.57, .8)], fill=255, width=W(.07))


def i_gear(d, N, P, W):
    c = .5 * N
    for k in range(8):
        a = math.radians(k * 45)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        r0, r1, hw = .26 * N, .45 * N, .085 * N
        d.polygon([(c + ux * r0 + nx * hw, c + uy * r0 + ny * hw), (c + ux * r1 + nx * hw, c + uy * r1 + ny * hw),
                   (c + ux * r1 - nx * hw, c + uy * r1 - ny * hw), (c + ux * r0 - nx * hw, c + uy * r0 - ny * hw)], fill=255)
    d.ellipse([c - .33 * N, c - .33 * N, c + .33 * N, c + .33 * N], fill=255)
    d.ellipse([c - .15 * N, c - .15 * N, c + .15 * N, c + .15 * N], fill=0)


def i_plus(d, N, P, W):
    d.rectangle([.42 * N, .14 * N, .58 * N, .86 * N], fill=255)
    d.rectangle([.14 * N, .42 * N, .86 * N, .58 * N], fill=255)


def i_moon(d, N, P, W):
    d.ellipse([.12 * N, .1 * N, .88 * N, .86 * N], fill=255)
    d.ellipse([.38 * N, .0 * N, 1.1 * N, .72 * N], fill=0)


def i_sun(d, N, P, W):
    c, r = .5 * N, .19 * N
    d.ellipse([c - r, c - r, c + r, c + r], fill=255)
    for k in range(8):
        a = math.radians(k * 45)
        d.line([(c + math.cos(a) * .3 * N, c + math.sin(a) * .3 * N),
                (c + math.cos(a) * .44 * N, c + math.sin(a) * .44 * N)], fill=255, width=W(.08))


def _tray(d, P, W):
    d.line([P(.14, .6), P(.14, .86), P(.86, .86), P(.86, .6)], fill=255, width=W(.09), joint="curve")


def i_import(d, N, P, W):
    _tray(d, P, W)
    d.line([P(.5, .1), P(.5, .52)], fill=255, width=W(.11))
    d.polygon([P(.27, .4), P(.73, .4), P(.5, .68)], fill=255)


def i_export(d, N, P, W):
    _tray(d, P, W)
    d.line([P(.5, .24), P(.5, .66)], fill=255, width=W(.11))
    d.polygon([P(.27, .36), P(.73, .36), P(.5, .08)], fill=255)


def i_pencil(d, N, P, W):
    d.polygon([P(.24, .62), P(.4, .78), P(.86, .32), P(.7, .16)], fill=255)       # body
    d.polygon([P(.2, .66), P(.34, .8), P(.1, .9)], fill=255)                        # tip


ICONS = {"refresh": i_refresh, "check": i_check, "ext": i_ext, "trash": i_trash, "gear": i_gear, "plus": i_plus,
         "moon": i_moon, "sun": i_sun, "import": i_import, "export": i_export, "pencil": i_pencil}
SIZES = (16, 24)


def b64z(raw):
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def wrap(s, width=100, indent="    "):
    return "\n".join('%s"%s"' % (indent, s[i:i + width]) for i in range(0, len(s), width)) or indent + '""'


def build_block():
    out = ["# --- BEGIN GENERATED ICON DATA (tools/make_icons.py) ---",
           "# Toolbar icons: zlib-compressed 8-bit alpha masks, base64. Window icon: 64 px PNG, base64.",
           "ICON_MASKS = {"]
    for name, fn in ICONS.items():
        out.append('    "%s": {' % name)
        for s in SIZES:
            out.append("        %d: (\n%s\n        )," % (s, wrap(b64z(mask(fn, s).tobytes()), 96, "            ")))
        out.append("    },")
    out.append("}")
    buf = io.BytesIO()
    tag_icon(64).save(buf, "PNG", optimize=True)
    out.append("APP_ICON_PNG = (\n%s\n)" % wrap(base64.b64encode(buf.getvalue()).decode("ascii"), 96, "    "))
    out.append("# --- END GENERATED ICON DATA ---")
    return "\n".join(out)


def main():
    tag_icon(256).save(os.path.join(ROOT, "icon.ico"), format="ICO",
                       sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote icon.ico")
    src_path = os.path.join(ROOT, "github_release_tracker.py")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    pat = re.compile(r"# --- BEGIN GENERATED ICON DATA.*?# --- END GENERATED ICON DATA ---", re.S)
    if not pat.search(src):
        raise SystemExit("markers not found in github_release_tracker.py")
    with open(src_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(pat.sub(lambda _m: build_block(), src))
    print("updated the embedded icon data")


if __name__ == "__main__":
    main()
