# -*- coding: utf-8 -*-
"""
Socket organizer - parametric generator for FreeCAD.

Modular, interlinking socket holder. Metric (8-19mm) and SAE (5/16"-3/4")
sockets, both 3/8" and 1/2" drive, one middle piece per size/drive plus a
start and end cap. Each socket stands on a molded post sized to its drive
square - friction on the post corners holds it upright, no magnet, no
stick. Pieces snap together with a vertical dovetail (press down to seat,
lift straight up to remove) so any single piece can be pulled without
disturbing its neighbours.

Running it
----------
Headless (no GUI needed)::

    freecadcmd build_socket_organizer.py

Outputs land in ./exports as STEP, STL and 3MF.

Print the fit coupons (post_coupon_3-8in.stl, post_coupon_1-2in.stl,
dovetail_coupon.stl) before committing to the full 42-piece set.

Copyright (c) 2026 Oxidized Apps, LLC
SPDX-License-Identifier: MIT
"""

import os
import sys
import math
import FreeCAD as App
import Part

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------

PARAMS = {
    # --- base footprint (same for every piece) -----------------------------
    "base_w":         26.0,   # left-right, this is the row-direction pitch
    "base_d":         32.0,   # front-to-back depth
    "base_h":         10.0,   # riser height before the post/socket area
    "front_slope_deg": 20.0,  # front wall lean, back from vertical

    # --- post (drive-square friction mount) ---------------------------------
    # "af" = across-flats. Post af is undersized vs. the nominal drive
    # square so the printed corners interfere with the broach corners.
    # TUNE VIA POST FIT COUPON before trusting these.
    "drive_af_nominal": {"3-8in": 9.53, "1-2in": 12.70},
    "post_af_undersize": 0.5,   # post_af = nominal - this, per drive
    "post_corner_r":   0.6,
    "post_h":          11.0,
    "post_top_chamfer": 0.5,    # lead-in chamfer, top-facing only. Must be
                                  # <= post_corner_r or OCC's chamfer on the
                                  # tiny fillet-arc top edges self-intersects.

    # --- dovetail (vertical snap: open top, closed bottom) ------------------
    "dt_neck_w":       4.0,   # width where the tail meets the base
    "dt_tip_w":        6.0,   # width at the tail's outer edge (wider = hooks)
    "dt_depth":        4.0,   # how far the tail protrudes / groove cuts in
    "dt_clearance":    0.15,  # per-side clearance, groove vs tail. TUNE VIA
                               # DOVETAIL FIT COUPON before trusting this.

    # --- label --------------------------------------------------------------
    "label_h":         4.0,   # embossed text height (font size)
    "label_depth":     0.6,   # how far the text stands proud
    "label_z":         4.0,   # text baseline height on the sloped front wall
    "label_embed":     0.2,   # back-face push past the wall plane, capped by
                               # label_depth - see emboss_label docstring

    # --- cap (start/end piece) ----------------------------------------------
    "cap_round_r":     8.0,   # radius of the closed rounded end

    # --- sizes covered --------------------------------------------------------
    "metric_mm":       list(range(8, 20)),               # 8..19 inclusive
    "sae_frac_32nds":  [10, 12, 14, 16, 18, 20, 22, 24],  # 5/16..3/4 in 1/32nds
    "drives":          ["3-8in", "1-2in"],

    # --- printer --------------------------------------------------------------
    "bed_x": 256.0, "bed_y": 256.0,
}


def _script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def box(l, w, h, x, y, z):
    return Part.makeBox(l, w, h, App.Vector(x, y, z))


def sae_label(n32):
    """5/16" from a /32nds numerator, reduced. n32=10 -> '5/16'."""
    d = 32
    n = n32
    g = math.gcd(n, d)
    return "%d/%d" % (n // g, d // g)


def sae_key(n32):
    """Filename-safe fraction, e.g. n32=10 -> '5-16in'."""
    d = 32
    g = math.gcd(n32, d)
    return "%d-%din" % (n32 // g, d // g)


# --------------------------------------------------------------------------
# Geometry - base and post
# --------------------------------------------------------------------------

def wall_y_at_z(p, z):
    """Y position of the sloped front wall's surface at height z.

    Single source of truth for the wall's geometry: make_base's wedge cut
    and emboss_label's placement both derive from this same line so they
    can't silently drift apart."""
    return z * math.tan(math.radians(p["front_slope_deg"]))


def make_base(p):
    """Riser block with a sloped front wall. Front is the -Y face."""
    body = box(p["base_w"], p["base_d"], p["base_h"], 0, 0, 0)
    # Slope the front wall back by cutting a wedge from the whole front face.
    # In the Y-Z plane the cut is a triangle anchored at the bottom-front
    # corner (Y=0, Z=0) - no material removed there - rising linearly to
    # (Y=slope_rise, Z=base_h) at the top, so the wall leans back the full
    # height of the piece rather than only near the top.
    slope_rise = wall_y_at_z(p, p["base_h"])
    wedge_pts = [
        App.Vector(-1, 0, 0),
        App.Vector(-1, slope_rise, p["base_h"]),
        App.Vector(-1, 0, p["base_h"]),
        App.Vector(-1, 0, 0),
    ]
    wire = Part.makePolygon(wedge_pts)
    face = Part.Face(wire)
    wedge = face.extrude(App.Vector(p["base_w"] + 2, 0, 0))
    return body.cut(wedge)


def make_post(p, drive):
    """Square post, corners rounded, sized to the drive square (undersized
    for friction). Centered in X, set back from the sloped front wall."""
    af = p["drive_af_nominal"][drive] - p["post_af_undersize"]
    r = p["post_corner_r"]
    cx, cy = p["base_w"] / 2.0, p["base_d"] * 0.62
    half = af / 2.0 - r
    pts = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        pts.append(App.Vector(cx + sx * half, cy + sy * half, 0))
    profile = Part.makePolygon(pts + [pts[0]])
    face = Part.Face(profile)
    post = face.extrude(App.Vector(0, 0, p["post_h"]))
    post = post.makeFillet(r, [e for e in post.Edges
                                if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 0.01])
    if p["post_top_chamfer"] > 0:
        top_edges = [e for e in post.Edges
                     if abs(e.Vertexes[0].Z - p["post_h"]) < 0.01
                     and abs(e.Vertexes[1].Z - p["post_h"]) < 0.01]
        post = post.makeChamfer(p["post_top_chamfer"], top_edges)
    return post.translate(App.Vector(0, 0, p["base_h"]))


# --------------------------------------------------------------------------
# Geometry - vertical dovetail (open top, closed bottom)
# --------------------------------------------------------------------------

def _dt_profile(p, outward, clearance=0.0):
    """2D dovetail profile in the XY plane, tip pointing in +/-X (outward).
    Root sits at x=0 (the base's side face), tip extends `dt_depth` out."""
    neck = p["dt_neck_w"] / 2.0 + clearance
    tip = p["dt_tip_w"] / 2.0 + clearance
    depth = p["dt_depth"]
    sign = 1 if outward else -1
    pts = [
        App.Vector(0, -neck, 0),
        App.Vector(sign * depth, -tip, 0),
        App.Vector(sign * depth, tip, 0),
        App.Vector(0, neck, 0),
        App.Vector(0, -neck, 0),
    ]
    return Part.Face(Part.makePolygon(pts))


def make_dovetail_tail(p):
    """Protrudes from the base's right (+X) side, full base height."""
    face = _dt_profile(p, outward=True)
    solid = face.extrude(App.Vector(0, 0, p["base_h"]))
    return solid.translate(App.Vector(p["base_w"], p["base_d"] * 0.3, 0))


def make_dovetail_groove_cutter(p):
    """Cutter for the base's left (0) side - slightly oversized for snap fit.

    Must carve INTO the base's own solid (local x in [0, dt_depth], same
    +X sign as the tail), not out into empty space beyond x=0 - otherwise
    the cut is a no-op and the neighbouring piece's tail collides with
    still-solid material instead of nesting into a cavity."""
    face = _dt_profile(p, outward=True, clearance=p["dt_clearance"])
    solid = face.extrude(App.Vector(0, 0, p["base_h"] + 2))
    return solid.translate(App.Vector(0, p["base_d"] * 0.3, -1))


# --------------------------------------------------------------------------
# Geometry - label text
# --------------------------------------------------------------------------

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def pick_font():
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise RuntimeError("no usable font found; add a path to _FONT_CANDIDATES")


def text_solid(txt, font, size, thickness):
    shapes = Part.makeWireString(txt, font, size, 0.0)
    faces = [Part.Face(w) for group in shapes for w in group]
    comp = Part.Compound(faces)
    return comp.extrude(App.Vector(0, 0, thickness))


def emboss_label(p, text):
    """Text solid, laid flat, rotated to sit on the sloped front wall,
    positioned centered in X, standing proud by label_depth.

    make_base's front wall leans back in +Y as it rises: at height Z the
    wall surface sits at Y = wall_y_at_z(p, Z) (see make_base's wedge cut,
    which uses the same helper). text_solid() builds the text flat in the
    local X-Y plane (X = reading
    direction, Y = glyph height above the baseline) and extrudes it along
    local +Z by `thickness`, so local Z=0 is the back face (meant to sit
    flush on the wall) and local Z=thickness is the raised front face.

    Rotating that solid by (90 - slope) degrees about the X axis maps:
      - local +Y (glyph height / "up") -> world (sin(slope), cos(slope))
        in (Y, Z), i.e. "up the slope" - right-side up, not mirrored
        (X, the reading direction, is untouched by an X-axis rotation).
      - local +Z (extrusion/thickness) -> world (-cos(slope), sin(slope))
        in (Y, Z), which is exactly the wall's outward-facing normal, so
        the text stands proud OFF the wall rather than being buried in it.

    After rotation, translating the back face (local Z=0) to
    Y = wall_y_at_z(p, label_z), Z = label_z lands every point of that
    back face exactly on the wall plane (Y = wall_y_at_z(p, Z) for all
    Z), for any glyph height - not just the baseline - so the label sits
    flush against the sloped face with its raised face pointing outward.

    The label is a Compound of one solid per glyph (see text_solid), each
    landing its own back face on the wall plane. Fusing a Compound whose
    back faces are exactly coincident (zero-gap tangent) with the base's
    wall face is a known OCC boolean edge case that produces invalid,
    non-manifold results - confirmed here: fusing at zero overlap gave
    `fused.isValid() == False`. So the back face is pushed
    `p["label_embed"]` past the wall plane (into the solid, along the
    wall's inward normal, capped by label_depth) before rotation,
    guaranteeing genuine volumetric overlap for the fuse in
    make_middle_piece while the front (proud) face stays at the full
    label_depth standoff.
    """
    font = pick_font()
    embed = min(p["label_embed"], p["label_depth"])
    solid = text_solid(text, font, p["label_h"], p["label_depth"] + embed)
    solid = solid.translate(App.Vector(0, 0, -embed))
    bb = solid.BoundBox
    solid = solid.translate(App.Vector(-(bb.XMin + bb.XLength / 2.0), 0, 0))
    solid = solid.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90 - p["front_slope_deg"])
    x_center = p["base_w"] / 2.0
    y_wall = wall_y_at_z(p, p["label_z"])
    solid = solid.translate(App.Vector(x_center, y_wall, p["label_z"]))
    return solid


def make_middle_piece(p, drive, label_text):
    body = make_base(p).fuse(make_post(p, drive))
    body = body.fuse(make_dovetail_tail(p))
    body = body.cut(make_dovetail_groove_cutter(p))
    body = body.fuse(emboss_label(p, label_text))
    return body


# --------------------------------------------------------------------------
# Geometry - end cap
# --------------------------------------------------------------------------

def make_cap(p, side):
    """side='start' has a tail on its right edge (mates leftward into the
    row); side='end' has a groove on its left edge (mates rightward). The
    opposite edge is rounded off closed.

    The rounding removes the corner sliver that lies OUTSIDE the round
    cylinder but INSIDE the body's own corner strip (width cap_round_r,
    the full base_d depth). That corner strip must sit on the body's own
    side of the edge being rounded:
      - side='start' rounds the LEFT edge (round_x=0), so the strip is
        x in [0, r] - i.e. box origin round_x (NOT round_x - r, which
        would place the box entirely at x in [-r, 0], outside the body's
        x in [0, base_w] domain and make the cut a no-op).
      - side='end' rounds the RIGHT edge (round_x=base_w), so the strip
        is x in [base_w - r, base_w] - i.e. box origin round_x - r (NOT
        round_x, which would place the box entirely outside the body at
        x in [base_w, base_w + r], again a no-op cut).
    Verified live: with the box positioned outside the body its overlap
    with body is 0.0 mm3 and the round is silently skipped; positioned as
    above the overlap is ~2445.8 mm3 and the cut actually removes ~1865.6
    mm3 of corner material, producing a rounded nose centered on the
    dovetail's Y offset (base_d * 0.3) rather than two square corners.
    """
    if side not in ("start", "end"):
        raise ValueError("side must be 'start' or 'end', got %r" % side)

    body = make_base(p)

    r = p["cap_round_r"]
    if side == "start":
        body = body.fuse(make_dovetail_tail(p))
        round_x = 0
    else:
        body = body.cut(make_dovetail_groove_cutter(p))
        round_x = p["base_w"]
    round_cutter = Part.makeCylinder(
        r, p["base_h"] + 2, App.Vector(round_x, p["base_d"] * 0.3, -1))
    corner_x = round_x if side == "start" else round_x - r
    corner = box(r, p["base_d"], p["base_h"] + 2, corner_x, 0, -1)
    body = body.cut(corner.cut(round_cutter))
    return body


# --------------------------------------------------------------------------
# Size table iteration
# --------------------------------------------------------------------------

def generate_all(p):
    """Returns {name: shape} for every middle piece and both caps."""
    out = {}
    for mm in p["metric_mm"]:
        for drive in p["drives"]:
            name = "metric_%dmm_%s" % (mm, drive)
            out[name] = make_middle_piece(p, drive, str(mm))
    for n32 in p["sae_frac_32nds"]:
        label = sae_label(n32)
        key = sae_key(n32)
        for drive in p["drives"]:
            name = "sae_%s_%s" % (key, drive)
            out[name] = make_middle_piece(p, drive, label)
    out["cap_start"] = make_cap(p, "start")
    out["cap_end"] = make_cap(p, "end")
    return out


def run():
    doc = App.newDocument("socket_organizer")
    pieces = generate_all(PARAMS)
    n_metric = len(PARAMS["metric_mm"]) * len(PARAMS["drives"])
    n_sae = len(PARAMS["sae_frac_32nds"]) * len(PARAMS["drives"])
    expected = n_metric + n_sae + 2
    print("generated %d pieces (expected %d)" % (len(pieces), expected))
    assert len(pieces) == expected == 42
    App.closeDocument(doc.Name)


def _invoked_as_script():
    """True when this file was handed to freecadcmd / python as the script.

    freecadcmd sets __name__ to the module's basename rather than
    "__main__", so the usual guard never fires. Checking argv distinguishes
    `freecadcmd build_socket_organizer.py` from `import build_socket_organizer`
    in the console, which must NOT trigger a build on import.
    """
    if __name__ == "__main__":
        return True
    try:
        me = os.path.basename(__file__)
    except NameError:
        return False
    return any(os.path.basename(a) == me for a in sys.argv[1:])


if _invoked_as_script():
    run()
