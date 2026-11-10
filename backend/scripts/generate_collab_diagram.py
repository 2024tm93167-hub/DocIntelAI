"""Generate the Real-Time Collaboration architecture diagram (Figure 4.3).

Run from the backend directory:
    venv/bin/python scripts/generate_collab_diagram.py

Output: ../docs/figures/realtime-collaboration.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / "docs" / "figures" / "realtime-collaboration.png"

S = 2  # supersample for anti-aliasing; final image is 2000x1300
W, H = 2000 * S, 1300 * S

FONT = "/System/Library/Fonts/Times.ttc"


def font(size, bold=False):
    # Times.ttc: index 0 = Roman, 1 = Bold, 2 = Italic (typical ordering)
    return ImageFont.truetype(FONT, size * S, index=1 if bold else 0)


F_TITLE = font(26, bold=True)
F_BOX = font(17, bold=True)
F_SUB = font(15)
F_LBL = font(15)
F_SMALL = font(13)
F_NUM = font(16, bold=True)

img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)


def sc(v):
    return v * S


def box(x0, y0, x1, y1, title, subtitle=None, fill="#FFFFFF", title_font=F_BOX):
    d.rounded_rectangle([sc(x0), sc(y0), sc(x1), sc(y1)], radius=sc(10),
                        fill=fill, outline="black", width=sc(3))
    tw = d.textlength(title, font=title_font)
    cx = sc((x0 + x1) // 2)
    if subtitle:
        d.text((cx - tw // 2, sc(y0) + sc(14)), title, font=title_font, fill="black")
        sw = d.textlength(subtitle, font=F_SUB)
        d.text((cx - sw // 2, sc(y0) + sc(48)), subtitle, font=F_SUB, fill="black")
    else:
        d.text((cx - tw // 2, sc(y0) + sc(16)), title, font=title_font, fill="black")


def container(x0, y0, x1, y1, title):
    d.rounded_rectangle([sc(x0), sc(y0), sc(x1), sc(y1)], radius=sc(14),
                        fill="#F4F4F4", outline="black", width=sc(3))
    tw = d.textlength(title, font=F_TITLE)
    d.text((sc((x0 + x1) // 2) - tw // 2, sc(y0) + sc(12)), title,
           font=F_TITLE, fill="black")


def dashed_line(p0, p1, dash=12, gap=8, width=3):
    x0, y0 = sc(p0[0]), sc(p0[1])
    x1, y1 = sc(p1[0]), sc(p1[1])
    import math
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist == 0:
        return
    dx, dy = (x1 - x0) / dist, (y1 - y0) / dist
    t = 0
    while t < dist:
        t2 = min(t + sc(dash), dist)
        d.line([x0 + dx * t, y0 + dy * t, x0 + dx * t2, y0 + dy * t2],
               fill="black", width=sc(width))
        t += sc(dash + gap)


def arrow(p0, p1, dashed=False, width=3):
    if dashed:
        dashed_line(p0, p1, width=width)
    else:
        d.line([sc(p0[0]), sc(p0[1]), sc(p1[0]), sc(p1[1])],
               fill="black", width=sc(width))
    # arrowhead at p1
    import math
    x0, y0 = p0
    x1, y1 = p1
    ang = math.atan2(y1 - y0, x1 - x0)
    L = sc(12)
    a1, a2 = ang + math.radians(155), ang - math.radians(155)
    tip = (sc(x1), sc(y1))
    pA = (tip[0] + L * math.cos(a1), tip[1] + L * math.sin(a1))
    pB = (tip[0] + L * math.cos(a2), tip[1] + L * math.sin(a2))
    d.polygon([tip, pA, pB], fill="black")


def elbow(points, dashed=False, width=3):
    """Draw a polyline with arrowhead at the end."""
    for a, b in zip(points, points[1:]):
        if dashed:
            dashed_line(a, b, width=width)
        else:
            d.line([sc(a[0]), sc(a[1]), sc(b[0]), sc(b[1])],
                   fill="black", width=sc(width))
    arrow(points[-2], points[-1], dashed=False, width=1)  # head only


def label(x, y, text, f=F_LBL, bg=True):
    tw = d.textlength(text, font=f)
    bbox = [sc(x) - tw // 2 - sc(5), sc(y) - sc(4), sc(x) + tw // 2 + sc(5),
            sc(y) + sc(21)]
    if bg:
        d.rectangle(bbox, fill="white")
    d.text((sc(x) - tw // 2, sc(y)), text, font=f, fill="black")


def num_badge(x, y, n):
    r = sc(14)
    d.ellipse([sc(x) - r, sc(y) - r, sc(x) + r, sc(y) + r],
              fill="black", outline="black")
    tw = d.textlength(str(n), font=F_NUM)
    asc, desc = F_NUM.getmetrics()
    d.text((sc(x) - tw // 2, sc(y) - (asc + desc) // 2 + sc(1)), str(n),
           font=F_NUM, fill="white")


# =====================================================================
# layout (base coords, x2 when drawing)
# =====================================================================

# ---- containers ----
container(60, 150, 620, 920, "Angular Frontend - User A (Editor)")
container(700, 150, 1300, 920, "FastAPI Backend")
container(1380, 150, 1940, 920, "Angular Frontend - User B (Editor)")
container(700, 960, 1300, 1210, "Cloud Firestore")

# ---- backend inner boxes (x 790..1250) ----
box(790, 200, 1250, 290, "WebSocket Router",
    "/ws/documents/{id}  (token auth + viewer ACL)")
box(790, 330, 1250, 420, "ConnectionManager",
    "in-memory fan-out per document")
box(790, 460, 1250, 550, "Permissions Service",
    "owner / editor / viewer role checks")
box(790, 590, 1250, 680, "Documents / Versions Routers",
    "PATCH update, POST version, POST restore")
box(790, 730, 1250, 820, "Repositories",
    "Firestore transactions (CAS revision)")

# ---- frontend A inner boxes ----
box(90, 200, 570, 290, "DocumentWsService",
    "connect, sendCursor, presence signals")
box(90, 330, 570, 420, "TipTap Editor + RemoteCursors",
    "renders remote carets & selections")
box(90, 590, 570, 680, "DocumentService + Autosave",
    "PATCH with base_revision")

# ---- frontend B inner boxes (mirror) ----
box(1430, 200, 1910, 290, "DocumentWsService",
    "connect, sendCursor, presence signals")
box(1430, 330, 1910, 420, "TipTap Editor + RemoteCursors",
    "renders remote carets & selections")
box(1430, 590, 1910, 680, "DocumentService + Autosave",
    "PATCH with base_revision")

# ---- firestore collections ----
for i, name in enumerate(["documents", "versions", "documentCollaborators", "users"]):
    bx0 = 720 + i * 145 if i < 3 else 720 + 3 * 145
chip_x = [(720, 870), (880, 1040), (1050, 1210), (1220, 1290)]
for (bx0, bx1), name in zip(chip_x, ["documents", "versions",
                                     "document\nCollaborators", "users"]):
    d.rounded_rectangle([sc(bx0), sc(1040), sc(bx1), sc(1130)],
                        radius=sc(8), fill="white", outline="black",
                        width=sc(2))
    lines = name.split("\n")
    for j, ln in enumerate(lines):
        tw = d.textlength(ln, font=F_SMALL)
        d.text((sc((bx0 + bx1) // 2) - tw // 2,
                sc(1052) + sc(24) * j), ln, font=F_SMALL, fill="black")

# =====================================================================
# arrows - external
# =====================================================================

# 1. A connects WS (dashed)
arrow((570, 245), (790, 245), dashed=True)
label(680, 218, "1. connect ?token +")
label(680, 240, "cursor {from,to}")

# broadcasts back to A (dashed)
arrow((790, 390), (570, 390), dashed=True)
label(680, 362, "4. presence / cursor /")
label(680, 384, "document_updated")

# 2. A saves via REST (solid)
arrow((570, 635), (790, 635), dashed=False)
label(680, 608, "2. PATCH /documents/{id}")
label(680, 630, "base_revision + Bearer")

# B mirrors (dashed ws connect + inbound broadcasts)
arrow((1430, 245), (1250, 245), dashed=True)
label(1330, 218, "1. connect ?token +")
label(1330, 240, "cursor {from,to}")

arrow((1250, 390), (1430, 390), dashed=True)
label(1330, 362, "4. presence / cursor /")
label(1330, 384, "document_updated")

arrow((1430, 635), (1250, 635), dashed=False)
label(1330, 608, "2. PATCH /documents/{id}")
label(1330, 630, "base_revision + Bearer")

# =====================================================================
# arrows - backend internal
# =====================================================================

# WS router -> ConnectionManager (register/relay)
arrow((1020, 290), (1020, 330), dashed=False)
label(1145, 300, "register / relay")

# WS router -> Permissions (left elbow for ACL on connect)
elbow([(790, 265), (755, 265), (755, 505), (790, 505)])
label(765, 380, "ACL", f=F_SMALL)

# Routers -> ConnectionManager broadcast (right elbow)
elbow([(1250, 635), (1282, 635), (1282, 355), (1250, 355)])
label(1284, 490, "broadcast()", f=F_SMALL)

# Permissions -> Repositories? keep simple: routers -> repositories
arrow((1020, 680), (1020, 730), dashed=False)
label(1120, 700, "read / write")

# Repositories -> Firestore
arrow((1020, 820), (1020, 960), dashed=False)
label(1145, 880, "3. transaction:")
label(1145, 902, "CAS + checkpoint")

# =====================================================================
# legend + numbered-flow caption
# =====================================================================
d.line([sc(80), sc(985), sc(160), sc(985)], fill="black", width=sc(3))
arrow((160, 985), (170, 985), width=1)
label(240, 975, "HTTP (REST + Bearer token)", f=F_SMALL)

dashed_line((80, 1025), (160, 1025), width=3)
arrow((160, 1025), (170, 1025), width=1)
label(240, 1015, "WebSocket (realtime events)", f=F_SMALL)

label(340, 1100, "Flow: 1. WS connect + cursor share   2. REST save with "
                 "base_revision   3. Firestore CAS commit   4. broadcast to "
                 "collaborators", f=F_SMALL)

OUT.parent.mkdir(parents=True, exist_ok=True)
img = img.resize((2000, 1300), Image.LANCZOS)
img.save(OUT)
print(f"Written: {OUT}")
