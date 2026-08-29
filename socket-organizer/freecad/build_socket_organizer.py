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
    "post_top_chamfer": 1.0,    # lead-in chamfer, top-facing only

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

def make_base(p):
    """Riser block with a sloped front wall. Front is the -Y face."""
    body = box(p["base_w"], p["base_d"], p["base_h"], 0, 0, 0)
    # Slope the front wall back by cutting a wedge from the whole front face.
    # In the Y-Z plane the cut is a triangle anchored at the bottom-front
    # corner (Y=0, Z=0) - no material removed there - rising linearly to
    # (Y=slope_rise, Z=base_h) at the top, so the wall leans back the full
    # height of the piece rather than only near the top.
    slope_rise = p["base_h"] * math.tan(math.radians(p["front_slope_deg"]))
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


def make_middle_piece(p, drive):
    return make_base(p).fuse(make_post(p, drive))


def run():
    doc = App.newDocument("socket_organizer")
    piece = make_middle_piece(PARAMS, "1-2in")
    bb = piece.Shape.BoundBox if hasattr(piece, "Shape") else piece.BoundBox
    print("test piece bbox: %.2f x %.2f x %.2f, volume %.1f"
          % (bb.XLength, bb.YLength, bb.ZLength, piece.Volume))
    assert bb.ZLength > PARAMS["base_h"] + PARAMS["post_h"] - 0.5
    assert bb.XLength <= PARAMS["base_w"] + 0.01

    # Guard against a no-op (or partial) wedge cut on the base's front wall:
    # a full uncut base_w x base_d x base_h box would have a known volume,
    # and the sloped version must be measurably smaller. Also probe that a
    # point near the top-front corner has actually been carved away while a
    # point near the bottom-front (where the wall meets the floor, no slope
    # yet) is still solid.
    base = make_base(PARAMS)
    full_box_volume = PARAMS["base_w"] * PARAMS["base_d"] * PARAMS["base_h"]
    print("base volume: %.1f (uncut box would be %.1f)"
          % (base.Volume, full_box_volume))
    assert base.Volume < full_box_volume - 50.0, (
        "make_base's wedge cut looks like a no-op: cut volume %.1f is not "
        "measurably less than the uncut box volume %.1f"
        % (base.Volume, full_box_volume))

    top_front = App.Vector(PARAMS["base_w"] / 2.0, 0.5, PARAMS["base_h"] - 0.5)
    bottom_front = App.Vector(PARAMS["base_w"] / 2.0, 1.0, 0.5)
    assert not base.isInside(top_front, 1e-6, True), (
        "expected top-front probe point %s to be cut away by the front-wall "
        "slope, but it is still inside the solid" % top_front)
    assert base.isInside(bottom_front, 1e-6, True), (
        "expected bottom-front probe point %s to remain solid (no slope at "
        "the floor), but it was cut away" % bottom_front)

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
