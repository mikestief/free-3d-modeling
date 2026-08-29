# -*- coding: utf-8 -*-
"""
Classroom whiteboard caddy - parametric generator for FreeCAD.

Builds a desk caddy that holds small lap whiteboards, dry-erase markers and
eraser pads.

This variant of the caddy:
  - 8 x 9"x12" lap boards, leaning back 10 deg in an open channel
  - 10 x Expo chisel markers, cap-up, in a merged row of tubes
  - 24 x 50x50x8mm eraser pads, in three open-front boxes
  - no carry handle

An optional pair of swappable two-colour name plates can be switched on with
PARAMS["nameplate"]. The geometry is checked on every run but has never been
printed, so treat that path as untested.

Everything is driven by the PARAMS dict below. Change a number, re-run, and
the whole model rebuilds. The values are also written into a FreeCAD
Spreadsheet named "Params" inside the document as a record of what was used.

Running it
----------
Headless (no GUI needed)::

    freecadcmd build_caddy.py

Or from the Python console inside FreeCAD::

    import sys; sys.path.insert(0, "/path/to/this/folder")
    import build_caddy; print(build_caddy.run())

Outputs land in ./exports as STEP, STL and 3MF.

What it checks
--------------
Every run reports three things, and they are the point of the script:

  * fit         - a probe solid of each real object (markers, the board
                  stack, the eraser stacks, the tiles) is pushed through the
                  model; any intersection means it physically will not fit
  * printability - downward-facing surfaces, split into true flat bridges and
                  harmless progressive overhang
  * mesh health - B-rep self-intersection, closed shell, and non-manifold
                  tessellation, because a slicer will reject those

Print the fit coupon before committing to the full part.

Copyright (c) 2026 Oxidized Apps, LLC
SPDX-License-Identifier: MIT
"""

import os
import sys
import math
import time
import FreeCAD as App
import Part

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------

PARAMS = {
    # --- boards -----------------------------------------------------------
    "board_w":        229.0,   # 9" board width
    "board_t":        3.5,     # single board thickness
    "board_clear_x":  3.0,     # total side-to-side slack for the board
    "n_boards":       8,
    "slot_w":         5.0,     # depth allowance per board in the channel
    "board_dividers": False,   # teacher asked for a plain open channel, no
                               # slits - boards just stack against each other
    "rib_t":          1.5,     # only used when board_dividers is True
    "rib_h":          20.0,
    "rib_len":        40.0,
    "lean_deg":       10.0,    # rearward lean of the board stack

    # --- markers ----------------------------------------------------------
    "n_markers":      10,
    "tube_id":        20.0,    # Expo chisel cap ~18.5 + clearance
    "tube_wall":      2.5,
    "tube_h":         50.0,
    "tube_overlap":   2.0,     # how much neighbouring tubes merge
    "tube_web_min":   2.5,     # minimum material between adjacent bores
    "tube_edge_margin": 2.0,   # clear space beyond the outermost tube
    "tube_floor":     3.0,
    "tube_chamfer":   1.5,
    "drain_w":        3.0,
    "drain_l":        15.0,

    # --- erasers ----------------------------------------------------------
    "n_bays":         3,       # three separate eraser compartments
    "pads_per_bay":   8,       # each box holds a full stack, as originally
                               # designed - so 24 pads total
    "pad_w":          50.0,
    "pad_d":          50.0,
    "pad_t":          8.0,
    "bay_wall":       2.4,
    "bay_clear":      3.2,     # total clearance around the pad stack
    "bay_extra_h":    6.0,     # headroom above the stack
    "chute_w":        40.0,    # open-front access slot

    # --- nameplate --------------------------------------------------------
    "nameplate":      False,   # teacher does not want name plates; the whole
                               # plinth and both tiles are dropped when False
    "plinth_t":       6.0,
    "plinth_gap":     6.0,
    "plinth_h":       34.0,
    "tile_l":         85.0,
    "tile_h":         26.0,
    "tile_t":         3.0,
    "tile_clear":     0.4,
    "tile_dovetail":  5.5,
    "text_h":         0.8,
    "school_name":    "SCHOOL NAME",   # only used when nameplate is True
    "teacher_name":   "TEACHER NAME",

    # --- printer ----------------------------------------------------------
    # Used only for the "does it fit the bed" report. Defaults to a 256mm
    # class machine (Bambu X1C / P1S / A1 / X2D). Change for your printer.
    "bed_x":          256.0,
    "bed_y":          256.0,
    "bed_z":          256.0,
    "printer_name":   "256mm bed",

    # --- structure --------------------------------------------------------
    "end_wall":       6.0,
    "back_wall":      6.0,
    "slot_front_w":   6.0,
    "base_t":         5.0,
    "weld_overlap":   1.0,     # Bodies that merely touch make tangential
                               # contact - a cylinder kissing a plane - which
                               # tessellates into non-manifold edges. Adjacent
                               # bodies overlap by this much instead.
    "wall":           2.4,
    "antitip":        25.0,    # base extension behind the back wall
    "wall_h":         90.0,    # back-wall height above the base
    "fillet_r":       2.0,

}

# Directories searched for a bold sans TTF to engrave the name plates with,
# in order, across macOS / Windows / Linux. Only needed when PARAMS
# ["nameplate"] is True. Set FONT_OVERRIDE to a .ttf path to force one.
FONT_OVERRIDE = None

FONT_DIRS = [
    "/System/Library/Fonts/Supplemental",          # macOS
    "/System/Library/Fonts",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "C:\\Windows\\Fonts",                          # Windows
    "/usr/share/fonts",                            # Linux
    "/usr/share/fonts/truetype",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
]

# Preferred faces, best first. Anything bold and sans will do.
FONT_NAMES = [
    "Arial Bold.ttf", "arialbd.ttf",
    "Verdana Bold.ttf", "verdanab.ttf",
    "Tahoma Bold.ttf", "tahomabd.ttf",
    "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",
    "FreeSansBold.ttf", "NotoSans-Bold.ttf",
    "Arial Unicode.ttf", "arial.ttf", "DejaVuSans.ttf",
]


def _script_dir():
    """Folder this file lives in, whichever way it was invoked."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # exec'd without __file__ (some FreeCAD console paths)
        return os.path.abspath(os.getcwd())


HERE = _script_dir()
EXPORTS = os.path.join(HERE, "exports")


# --------------------------------------------------------------------------
# Derived geometry
# --------------------------------------------------------------------------

def derive(p):
    d = dict(p)
    n = p["n_boards"]
    # Open channel: boards lean against each other, no divider ribs.
    d["slot_depth"] = n * p["slot_w"]
    if p["board_dividers"]:
        d["slot_depth"] += (n - 1) * p["rib_t"]
    # overall body width driven by the board plus its side slack
    d["cav_w"] = p["board_w"] + p["board_clear_x"]
    d["body_w"] = d["cav_w"] + 2 * p["end_wall"]
    d["half_w"] = d["body_w"] / 2.0
    # tube geometry
    d["tube_od"] = p["tube_id"] + 2 * p["tube_wall"]
    d["tube_pitch"] = d["tube_od"] - p["tube_overlap"]
    # eraser bay
    d["bay_in_w"] = p["pad_w"] + p["bay_clear"]
    d["bay_in_d"] = p["pad_d"] + p["bay_clear"]
    d["bay_out_w"] = d["bay_in_w"] + 2 * p["bay_wall"]
    d["bay_out_d"] = d["bay_in_d"] + 2 * p["bay_wall"]
    d["n_erasers"] = p["n_bays"] * p["pads_per_bay"]
    d["bay_in_h"] = p["pads_per_bay"] * p["pad_t"] + p["bay_extra_h"]
    d["bays_w"] = p["n_bays"] * d["bay_out_w"]
    # bay centres, sitting side by side and centred on the body
    d["bay_x"] = [-d["bays_w"] / 2.0 + (i + 0.5) * d["bay_out_w"]
                  for i in range(p["n_bays"])]
    # ---- Y stations, measured from the rear edge of the base ----
    d["y_wall_back"] = p["antitip"]
    d["y_slot_back"] = d["y_wall_back"] + p["back_wall"]
    d["y_slot_front"] = d["y_slot_back"] + d["slot_depth"]
    d["y_module_front"] = d["y_slot_front"] + p["slot_front_w"]
    d["y_tube_back"] = d["y_module_front"]
    d["y_tube_front"] = d["y_tube_back"] + d["tube_od"]
    # nameplate plinth sits at the tube line; the eraser bay noses forward
    # through a notch in it, as in the reference photo.
    # The plinth leans back by lean_deg, so its top edge travels rearward by
    # sin(lean) * plinth_h. Stand it far enough forward that even the top of
    # a tile pocket stays clear of the marker bores behind it.
    lean_back = math.sin(math.radians(p["lean_deg"])) * p["plinth_h"]
    d["plinth_lean_back"] = lean_back
    if p["nameplate"]:
        # The plinth's top edge travels rearward by sin(lean) * height.
        # Landing it flush with the tube row's tangent plane leaves a
        # near-tangential contact and a self-intersecting mesh, so keep
        # weld_overlap of air beyond the lean-back distance.
        d["y_plinth_back"] = d["y_tube_front"] + max(
            p["plinth_gap"], lean_back + p["weld_overlap"] + 1.0)
        d["y_plinth_front"] = d["y_plinth_back"] + p["plinth_t"]
        d["base_full_d"] = d["y_plinth_front"]
    else:
        d["y_plinth_back"] = d["y_plinth_front"] = d["y_tube_front"]
        d["base_full_d"] = d["y_tube_front"]
    # Pull the bay back into the tube row. Sitting flush, the bay's rear wall
    # is exactly tangent to all ten tube cylinders, which tessellates
    # non-manifold even though the solid itself checks out as valid.
    d["y_bay_back"] = d["y_tube_front"] - p["weld_overlap"]
    d["y_bay_front"] = d["y_bay_back"] + d["bay_out_d"]
    d["base_d"] = max(d["base_full_d"], d["y_bay_front"])
    # Z stations
    d["z_base_top"] = p["base_t"]
    d["z_module_top"] = p["base_t"] + p["wall_h"]
    d["z_tube_top"] = p["base_t"] + p["tube_h"]
    d["z_bay_top"] = p["base_t"] + p["tube_floor"] + d["bay_in_h"]
    # One continuous merged row of tubes, centred on the body.
    # Pitch is floored so adjacent bores always keep a printable web between
    # them - at 8 markers this is what forces the row to be continuous rather
    # than split 4+4 around the bay.
    min_pitch = p["tube_id"] + p["tube_web_min"]
    if d["tube_pitch"] < min_pitch:
        d["tube_pitch"] = min_pitch
    n = p["n_markers"]
    # squeeze the pitch if the requested marker count would overrun the body
    avail = d["cav_w"] - 2 * p["tube_edge_margin"]
    if n > 1:
        fit_pitch = (avail - d["tube_od"]) / float(n - 1)
        if fit_pitch < d["tube_pitch"]:
            d["tube_pitch"] = fit_pitch
    span = (n - 1) * d["tube_pitch"]
    d["tube_span"] = span + d["tube_od"]
    d["tube_x"] = [-span / 2.0 + i * d["tube_pitch"] for i in range(n)]
    inner_clear = d["half_w"] - p["end_wall"] - d["tube_span"] / 2.0
    if inner_clear < 0 or d["tube_pitch"] < min_pitch:
        raise ValueError(
            "%d markers need pitch %.2f (min %.2f); row %.1fmm vs %.1fmm avail"
            % (n, d["tube_pitch"], min_pitch, d["tube_span"], avail))
    d["tube_edge_clear"] = inner_clear
    # structural sanity checks - these are the things that quietly produce a
    # part that prints fine and then snaps in a classroom.
    d["warnings"] = []
    post = (d["bay_in_w"] - p["chute_w"]) / 2.0
    d["bay_post_w"] = post
    if post < 2 * p["wall"]:
        d["warnings"].append("bay front posts only %.1fmm wide" % post)
    if d["bays_w"] > d["cav_w"]:
        d["warnings"].append("bays %.1fmm wider than body opening %.1fmm"
                             % (d["bays_w"], d["cav_w"]))
    if p["chute_w"] >= p["pad_w"]:
        d["warnings"].append("chute %.1f wider than pad %.1f - pads fall out"
                             % (p["chute_w"], p["pad_w"]))
    web = d["tube_pitch"] - p["tube_id"]
    if web < 2.0:
        d["warnings"].append("only %.1fmm between adjacent marker bores" % web)
    return d


def rot_x(shape, angle_deg, pivot):
    """Rotate a shape about the global X axis through `pivot`."""
    s = shape.copy()
    s.rotate(App.Vector(*pivot), App.Vector(1, 0, 0), angle_deg)
    return s


def box(l, w, h, x, y, z):
    return Part.makeBox(l, w, h, App.Vector(x, y, z))


# --------------------------------------------------------------------------
# Sub-assemblies
# --------------------------------------------------------------------------

def make_base(d):
    """Base plate, full footprint, with a centre tongue for the eraser bay.

    The underside is deliberately flat. Recessed pads for stick-on feet were
    tried and removed: a 30mm circular recess is a 30mm unsupported ceiling on
    the very first layer. Stick felt pads straight onto the flat bottom.
    """
    p = d
    base = box(d["body_w"], d["base_full_d"], p["base_t"], -d["half_w"], 0, 0)
    if d["base_d"] > d["base_full_d"]:
        tongue_w = d["bays_w"] + 8.0
        base = base.fuse(box(tongue_w, d["base_d"] - d["base_full_d"] + 0.1,
                             p["base_t"], -tongue_w / 2.0,
                             d["base_full_d"] - 0.05, 0))
    return base


def make_board_module(d):
    """Board slot block: outer prism, leaning cavity, ribs. No carry handle.

    Built upright in local coordinates, then rotated rearward as one piece so
    the outer faces lean with the boards (and the anti-tip foot catches it).
    """
    p = d
    y0 = d["y_wall_back"]
    y1 = d["y_module_front"]
    depth = y1 - y0
    z0 = p["base_t"]
    h = p["wall_h"]

    blk = box(d["body_w"], depth, h, -d["half_w"], y0, z0)

    # board cavity, cut clean through the top
    cav = box(d["cav_w"], d["slot_depth"], h + 20,
              -d["cav_w"] / 2.0, d["y_slot_back"], z0)
    blk = blk.cut(cav)

    # divider ribs, only if asked for - the teacher wants a plain channel
    if p["board_dividers"]:
        rib_x = d["cav_w"] / 2.0 - p["rib_len"]
        for i in range(p["n_boards"] - 1):
            ry = d["y_slot_back"] + p["slot_w"] * (i + 1) + p["rib_t"] * i
            for sx in (-d["cav_w"] / 2.0, rib_x):
                blk = blk.fuse(box(p["rib_len"], p["rib_t"], p["rib_h"],
                                   sx, ry, z0))

    # lean the whole module rearward about its front bottom edge
    blk = rot_x(blk, p["lean_deg"], (0, y1, z0))
    # trim anything that dropped below the base top
    keep = box(d["body_w"] + 40, d["base_d"] + 60, 400,
               -d["half_w"] - 20, -30, z0)
    return blk.common(keep)


def make_tubes(d):
    """8 merged marker tubes, bored, chamfered, with drain slots."""
    p = d
    cy = d["y_tube_back"] + d["tube_od"] / 2.0
    z0 = p["base_t"]
    solid = None
    for cx in d["tube_x"]:
        cyl = Part.makeCylinder(d["tube_od"] / 2.0, p["tube_h"],
                                App.Vector(cx, cy, z0))
        solid = cyl if solid is None else solid.fuse(cyl)

    cuts = []
    for cx in d["tube_x"]:
        # bore
        cuts.append(Part.makeCylinder(
            p["tube_id"] / 2.0, p["tube_h"] - p["tube_floor"] + 1,
            App.Vector(cx, cy, z0 + p["tube_floor"])))
        # lead-in chamfer at the mouth
        ch = p["tube_chamfer"]
        cuts.append(Part.makeCone(
            p["tube_id"] / 2.0, p["tube_id"] / 2.0 + ch, ch,
            App.Vector(cx, cy, z0 + p["tube_h"] - ch)))
        # drain slot, straight through the base
        cuts.append(box(p["drain_w"], p["drain_l"], p["base_t"] + p["tube_floor"] + 2,
                        cx - p["drain_w"] / 2.0, cy - p["drain_l"] / 2.0, -1))
    return solid, cuts


def make_bay(d):
    """Eraser bays: N compartments side by side, open top, open front chute."""
    p = d
    y0 = d["y_bay_back"]
    z0 = p["base_t"]
    h = d["z_bay_top"] - z0
    outer = None
    cuts = []
    for cx in d["bay_x"]:
        blk = box(d["bay_out_w"], d["bay_out_d"], h,
                  cx - d["bay_out_w"] / 2.0, y0, z0)
        outer = blk if outer is None else outer.fuse(blk)
        # inner cavity, open at the top
        cuts.append(box(d["bay_in_w"], d["bay_in_d"], h + 10,
                        cx - d["bay_in_w"] / 2.0, y0 + p["bay_wall"],
                        z0 + p["tube_floor"]))
        # front chute
        cuts.append(box(p["chute_w"], p["bay_wall"] + 6, h + 10,
                        cx - p["chute_w"] / 2.0,
                        d["y_bay_front"] - p["bay_wall"] - 3,
                        z0 + p["tube_floor"]))
    return outer, cuts


def make_plinth(d):
    """Front nameplate plinth: two dovetail tile pockets + centre chute notch.

    Built upright, pockets cut in local coordinates, then tilted rearward so
    the tile faces read from standing height instead of hiding under the tubes.
    """
    p = d
    yb = d["y_plinth_back"]
    yf = d["y_plinth_front"]
    z0 = p["base_t"]
    h = p["plinth_h"]

    pl = box(d["body_w"], p["plinth_t"], h, -d["half_w"], yb, z0)

    # centre notch: the eraser bay passes straight through the plinth
    notch_w = d["bays_w"] + 1.0
    pl = pl.cut(box(notch_w, p["plinth_t"] + 8, h + 4,
                    -notch_w / 2.0, yb - 4, z0 - 2))

    # tile pockets, one each side, open at the outboard end for slide-in
    notch_half = (d["bays_w"] + 1.0) / 2.0
    avail = d["half_w"] - notch_half - 5.0
    pocket_l = min(p["tile_l"] + p["tile_clear"], avail)
    pocket_h = p["tile_h"] + p["tile_clear"]
    pocket_t = p["tile_t"] + p["tile_clear"] / 2.0
    pz = z0 + (h - pocket_h) / 2.0
    py = yf - pocket_t
    for side in (-1, 1):
        px = -d["half_w"] if side < 0 else d["half_w"] - pocket_l
        pl = pl.cut(tile_pocket_cut(d, pocket_l, py, yf, pz, px))

    return rot_x(pl, p["lean_deg"], (0, yf, z0))


# --------------------------------------------------------------------------
# Text helper
# --------------------------------------------------------------------------

def _yz_prism(pts, x0, length):
    """Extrude a polygon given as (y, z) points along +X."""
    verts = [App.Vector(x0, y, z) for (y, z) in pts]
    verts.append(verts[0])
    return Part.Face(Part.makePolygon(verts)).extrude(
        App.Vector(length, 0, 0))


def tile_profile(d, length, y_back, z_bottom, x_left):
    """Nameplate tile: a dovetail in cross-section.

    Square retaining lips were the first attempt and are wrong for printing -
    the upper lip becomes a long unsupported ledge hanging in mid-air. Flaring
    the section instead means every surface of both the tile and its pocket
    self-supports, and the flare still captures the tile just as well.

    Widest at the back face, narrowing toward the front, so printed flat on
    its back the tile is overhang-free and the text lands on the top face.
    """
    p = d
    fl = p["tile_dovetail"]
    t = p["tile_t"]
    z_top = z_bottom + p["tile_h"]
    pts = [(y_back, z_bottom),
           (y_back + t, z_bottom + fl),
           (y_back + t, z_top - fl),
           (y_back, z_top)]
    return _yz_prism(pts, x_left, length), fl


def tile_pocket_cut(d, length, y_back, y_front, z_bottom, x_left, over=2.0):
    """Matching dovetail cavity, oversized by the fit clearances."""
    p = d
    fl = p["tile_dovetail"]
    z_top = z_bottom + p["tile_h"] + p["tile_clear"]
    pts = [(y_back, z_bottom),
           (y_front, z_bottom + fl),
           (y_front + over, z_bottom + fl),
           (y_front + over, z_top - fl),
           (y_front, z_top - fl),
           (y_back, z_top)]
    return _yz_prism(pts, x_left, length)


def pick_font():
    """First usable bold sans TTF on this machine, or None.

    Searched by name across the usual system font directories, then by
    scanning for anything bold, then FreeCAD's own bundled fonts. Returns
    None if nothing is found, in which case the plates are built without
    lettering rather than failing the whole build.
    """
    if FONT_OVERRIDE and os.path.exists(FONT_OVERRIDE):
        return FONT_OVERRIDE
    for name in FONT_NAMES:
        for folder in FONT_DIRS:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
    # nothing matched by name - walk the dirs for any bold TTF
    for folder in FONT_DIRS:
        if not os.path.isdir(folder):
            continue
        for root, _dirs, files in os.walk(folder):
            for fn in sorted(files):
                low = fn.lower()
                if low.endswith(".ttf") and "bold" in low:
                    return os.path.join(root, fn)
    # last resort: fonts shipped with FreeCAD itself
    try:
        res = os.path.join(App.getResourceDir(), "Mod", "TechDraw",
                           "Resources", "fonts")
        if os.path.isdir(res):
            for fn in sorted(os.listdir(res)):
                if fn.lower().endswith(".ttf"):
                    return os.path.join(res, fn)
    except Exception:
        pass
    return None


def text_solid(txt, font, size, thickness):
    """Extruded raised text, centred on the origin in X/Y. None on failure."""
    try:
        wires = Part.makeWireString(txt, font, size)
    except Exception as exc:
        App.Console.PrintWarning("text failed for %r: %s\n" % (txt, exc))
        return None
    solids = []
    for char in wires:
        if not char:
            continue
        try:
            face = Part.Face(char)
            solids.append(face.extrude(App.Vector(0, 0, thickness)))
        except Exception:
            # fall back: outer wire only, holes lost but shape survives
            try:
                ordered = sorted(char, key=lambda w: -Part.Face(w).Area)
                f = Part.Face(ordered[0])
                for inner in ordered[1:]:
                    f = f.cut(Part.Face(inner))
                solids.append(f.extrude(App.Vector(0, 0, thickness)))
            except Exception:
                pass
    if not solids:
        return None
    out = solids[0]
    for s in solids[1:]:
        out = out.fuse(s)
    bb = out.BoundBox
    out.translate(App.Vector(-(bb.XMin + bb.XLength / 2.0),
                             -(bb.YMin + bb.YLength / 2.0), 0))
    return out


# --------------------------------------------------------------------------
# Documents
# --------------------------------------------------------------------------

def write_spreadsheet(doc, p):
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    sheet.set("A1", "parameter")
    sheet.set("B1", "value")
    row = 2
    for k in sorted(p.keys()):
        v = p[k]
        sheet.set("A%d" % row, str(k))
        sheet.set("B%d" % row, str(v))
        try:
            if isinstance(v, (int, float)):
                sheet.setAlias("B%d" % row, str(k))
        except Exception:
            pass
        row += 1
    return sheet


def build_body():
    name = "whiteboard_caddy"
    for existing in list(App.listDocuments().keys()):
        if existing == name:
            App.closeDocument(name)
    doc = App.newDocument(name)
    d = derive(PARAMS)

    solid = make_base(d)
    solid = solid.fuse(make_board_module(d))

    tubes, tube_cuts = make_tubes(d)
    solid = solid.fuse(tubes)

    bay, bay_cuts = make_bay(d)
    solid = solid.fuse(bay)

    if PARAMS["nameplate"]:
        solid = solid.fuse(make_plinth(d))

    # removeSplitter() is deliberately NOT used. Merging the coplanar faces
    # made OCC produce six self-intersecting edge/face pairs, which Bambu
    # Studio reported as six non-manifold edges. Shape.isValid() misses this;
    # only Shape.check() catches it. The extra faces cost nothing that matters.
    for c in tube_cuts + bay_cuts:
        solid = solid.cut(c)

    # soften the outer vertical edges
    del FILLET_LOG[:]
    solid = fillet_outer(solid, d)

    obj = doc.addObject("Part::Feature", "Caddy")
    obj.Shape = solid
    write_spreadsheet(doc, PARAMS)
    doc.recompute()
    return doc, obj, d


FILLET_LOG = []
MESH_LOG = []


def _fillet_ok(shape):
    """A fillet is acceptable only if it leaves a clean, printable solid.

    Shape.check() does NOT catch this failure mode: filleting an edge that a
    pocket opens onto produces geometry that passes every B-rep check and
    still tessellates into a self-intersecting mesh, which slicers reject.
    Only the mesh test finds it.
    """
    try:
        if not shape.isValid() or not shape.isClosed():
            return False
        m = fine_mesh(shape)
        return not (m.hasSelfIntersections() or m.hasNonManifolds())
    except Exception:
        return False


def fillet_outer(solid, d):
    """Fillet vertical edges on the outer perimeter. Best effort, verified.

    Tries all candidates at once, which is fast and usually works. If that
    result fails validation, falls back to adding edges one at a time and
    keeping only those that leave the solid clean - so one bad edge costs its
    own rounding rather than all of it, or the model's validity.
    """
    r = d["fillet_r"]
    bb = solid.BoundBox
    tol = 0.4
    targets = []
    for e in solid.Edges:
        try:
            if not isinstance(e.Curve, Part.Line):
                continue
        except Exception:
            continue
        v0, v1 = e.Vertexes[0].Point, e.Vertexes[-1].Point
        if abs(v0.x - v1.x) > 1e-6 or abs(v0.y - v1.y) > 1e-6:
            continue          # not vertical
        if e.Length < r * 2.2:
            continue
        on_x = abs(v0.x - bb.XMin) < tol or abs(v0.x - bb.XMax) < tol
        on_y = abs(v0.y - bb.YMin) < tol or abs(v0.y - bb.YMax) < tol
        if on_x or on_y:
            targets.append(e)
    if not targets:
        FILLET_LOG.append("no candidate edges found")
        return solid

    bulk_err = None
    try:
        bulk = solid.makeFillet(r, targets)
    except Exception as exc:
        bulk_err = str(exc)[:60]
    else:
        if _fillet_ok(bulk):
            FILLET_LOG.append("filleted %d edges @ %.1fmm" % (len(targets), r))
            return bulk
        bulk_err = "bulk result failed validation"

    out, done, rejected = solid, 0, 0
    for e in targets:
        try:
            cand = out.makeFillet(r, [e])
        except Exception:
            rejected += 1
            continue
        if _fillet_ok(cand):
            out = cand
            done += 1
        else:
            rejected += 1
    FILLET_LOG.append("%s; filleted %d/%d edges individually, %d rejected"
                      % (bulk_err, done, len(targets), rejected))
    return out


def build_tiles():
    """Two nameplate tiles as separate objects: body + raised text.

    Body and text are distinct objects so the slicer can be told to print
    them in two colours. Both strings are rendered at one common
    cap height so the pair reads as a set rather than two odd sizes.
    """
    name = "nameplate_tiles"
    for existing in list(App.listDocuments().keys()):
        if existing == name:
            App.closeDocument(name)
    doc = App.newDocument(name)
    p = PARAMS
    d = derive(PARAMS)
    font = pick_font()

    labels = [("school", p["school_name"]), ("teacher", p["teacher_name"])]
    usable = p["tile_l"] - 8.0
    base_size = p["tile_h"] * 0.55

    # first pass: find the one scale that lets the longest string fit
    scale = 1.0
    raw = {}
    if font:
        for key, txt in labels:
            ts = text_solid(txt, font, base_size, p["text_h"])
            raw[key] = ts
            if ts is not None:
                w = ts.BoundBox.XLength
                if w > usable:
                    scale = min(scale, usable / w)

    made = []
    for idx, (key, txt) in enumerate(labels):
        y = idx * (p["tile_h"] + 10)
        prof, edge_t = tile_profile(d, p["tile_l"], 0.0, 0.0,
                                    -p["tile_l"] / 2.0)
        # +90 puts the flat back face on the bed, so the rebated edges are a
        # step *up* from the first layer rather than an unsupported overhang.
        body = prof.copy()
        body.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
        bbb = body.BoundBox
        body.translate(App.Vector(0, -bbb.YMin + y, -bbb.ZMin))
        b = doc.addObject("Part::Feature", "tile_%s" % key)
        b.Shape = body
        made.append(b)

        ts = raw.get(key)
        if ts is not None:
            if scale < 1.0:
                m = App.Matrix()
                m.scale(scale, scale, 1.0)
                ts = ts.transformGeometry(m)
            bb2 = ts.BoundBox
            ts.translate(App.Vector(
                -(bb2.XMin + bb2.XLength / 2.0),
                -(bb2.YMin + bb2.YLength / 2.0) + y + p["tile_h"] / 2.0,
                b.Shape.BoundBox.ZMax - ts.BoundBox.ZMin))
            t = doc.addObject("Part::Feature", "text_%s" % key)
            t.Shape = ts
            made.append(t)
    doc.recompute()
    return doc, made


def build_coupon():
    """Small test-fit coupon: one tube, one board slot pair, one tile pocket.

    Same parameters as the real part, so a good fit here means a good fit there.
    """
    name = "fit_coupon"
    for existing in list(App.listDocuments().keys()):
        if existing == name:
            App.closeDocument(name)
    doc = App.newDocument(name)
    p = PARAMS
    d = derive(PARAMS)

    L, W, H = 96.0, 60.0, 8.0
    solid = box(L, W, H, 0, 0, 0)

    # one marker tube
    tcx, tcy = 20.0, 30.0
    solid = solid.fuse(Part.makeCylinder(d["tube_od"] / 2.0, p["tube_h"] * 0.5,
                                         App.Vector(tcx, tcy, H)))
    solid = solid.cut(Part.makeCylinder(
        p["tube_id"] / 2.0, p["tube_h"] * 0.5 + 1,
        App.Vector(tcx, tcy, H + p["tube_floor"])))
    ch = p["tube_chamfer"]
    solid = solid.cut(Part.makeCone(
        p["tube_id"] / 2.0, p["tube_id"] / 2.0 + ch, ch,
        App.Vector(tcx, tcy, H + p["tube_h"] * 0.5 - ch)))

    # board channel gauge: a slice of the open channel at full width
    sx, sy = 42.0, 8.0
    ch_d = p["n_boards"] * p["slot_w"]
    if p["board_dividers"]:
        ch_d += (p["n_boards"] - 1) * p["rib_t"]
    ch_d = min(ch_d, 40.0)                 # keep the coupon small
    sh_h = 22.0
    solid = solid.fuse(box(20.0, ch_d + 2 * p["wall"], sh_h, sx, sy, H))
    solid = solid.cut(box(20.0 + 2, ch_d, sh_h + 2,
                          sx - 1, sy + p["wall"], H))
    if p["board_dividers"]:
        for i in range(2):
            ry = sy + p["wall"] + p["slot_w"] * (i + 1) + p["rib_t"] * i
            solid = solid.fuse(box(20.0, p["rib_t"], p["rib_h"], sx, ry, H))

    pocket_l = p["tile_l"] / 2.0
    if p["nameplate"]:
        pocket_h = p["tile_h"] + p["tile_clear"]
        pocket_t = p["tile_t"] + p["tile_clear"] / 2.0
        plz = H
        wall = box(pocket_l + 6, p["plinth_t"], pocket_h + 8,
                   L - pocket_l - 6, W - p["plinth_t"], plz)
        solid = solid.fuse(wall)
        px = L - pocket_l
        py = W - pocket_t
        pz = plz + 4
        solid = solid.cut(tile_pocket_cut(d, pocket_l + 1, py, W, pz, px))

    # one eraser-pad depth gauge: a short section of bay wall
    gx = 4.0
    solid = solid.fuse(box(p["bay_wall"], d["bay_in_d"] / 2.0, 14.0,
                           gx, 4.0, H))

    obj = doc.addObject("Part::Feature", "Coupon")
    obj.Shape = solid
    made = [obj]
    clash = 0.0
    if p["nameplate"]:
        prof, _ = tile_profile(d, pocket_l - 0.4, 0.0, 0.0, 0.0)
        prof.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90)
        pb = prof.BoundBox
        prof.translate(App.Vector(0, -pb.YMin - 40, -pb.ZMin))
        tile = doc.addObject("Part::Feature", "CouponTile")
        tile.Shape = prof
        made.append(tile)
        probe, _ = tile_profile(d, pocket_l - 0.6, py + 0.1,
                                pz + p["tile_clear"] / 2.0, px + 0.3)
        clash = solid.common(probe).Volume
    doc.recompute()
    return doc, made, clash


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

# Mesh quality for STL/3MF export. 0.02mm chord error puts the facet error on
# a 20mm marker bore at ~0.01mm - far below what the printer can resolve, and
# well below the fit clearances this design depends on.
LINEAR_DEFLECTION = 0.02
ANGULAR_DEFLECTION = math.radians(5.0)


def fine_mesh(shape, linear=None):
    import MeshPart
    return MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=LINEAR_DEFLECTION if linear is None else linear,
        AngularDeflection=ANGULAR_DEFLECTION,
        Relative=False)


def export_all(doc, objs, stem, deflection=None):
    """Write STEP (exact) plus STL and 3MF meshed at explicit fine quality.

    Mesh.export() applies its own coarse default deflection, so meshes are
    built here and written straight from a Mesh object - no temporary
    document, which also keeps this callable off the GUI thread.
    """
    if not os.path.isdir(EXPORTS):
        os.makedirs(EXPORTS)
    import Import
    import Mesh
    lin = LINEAR_DEFLECTION if deflection is None else deflection
    step = os.path.join(EXPORTS, stem + ".step")
    stl = os.path.join(EXPORTS, stem + ".stl")
    tmf = os.path.join(EXPORTS, stem + ".3mf")
    try:
        Import.export(objs, step)
    except Exception as exc:
        App.Console.PrintWarning("STEP export failed: %s\n" % exc)

    t0 = time.time()
    merged = None
    for o in objs:
        m = fine_mesh(o.Shape, lin)
        if merged is None:
            merged = m
        else:
            merged.addMesh(m)
    if merged is None:
        return step, stl
    for path in (stl, tmf):
        try:
            merged.write(path)
        except Exception as exc:
            App.Console.PrintWarning("%s export failed: %s\n" % (path, exc))
    MESH_LOG.append("%s %dk facets %.1fs"
                    % (stem, merged.CountFacets / 1000.0, time.time() - t0))
    return step, stl


def check_fits(shape, d):
    """Push a probe solid of every real object through the model.

    Each probe is the actual thing that has to go in - a capped marker, a
    board, the eraser stack, a nameplate tile. Any non-zero intersection with
    the body means that thing physically will not fit.
    """
    p = d
    issues = []
    probes = []

    cap_d = 18.5                      # widest point of an Expo chisel
    cy = d["y_tube_back"] + d["tube_od"] / 2.0
    for i, cx in enumerate(d["tube_x"]):
        probes.append(("marker %d" % i, Part.makeCylinder(
            cap_d / 2.0, p["tube_h"] - p["tube_floor"] - 0.5,
            App.Vector(cx, cy, p["base_t"] + p["tube_floor"] + 0.25))))

    # Boards. With divider ribs each board gets its own slot, so probe them
    # individually; in an open channel they stack against each other, so
    # probe the whole stack as one block.
    keep = box(400, 400, 400, -200, -100, p["base_t"] + 0.4)
    if p["board_dividers"]:
        for i in range(p["n_boards"]):
            y = d["y_slot_back"] + i * (p["slot_w"] + p["rib_t"]) \
                + (p["slot_w"] - p["board_t"]) / 2.0
            b = box(p["board_w"], p["board_t"], 220.0,
                    -p["board_w"] / 2.0, y, p["base_t"] + 0.5)
            b = rot_x(b, p["lean_deg"], (0, d["y_module_front"], p["base_t"]))
            probes.append(("board %d" % i, b.common(keep)))
    else:
        stack_t = p["n_boards"] * p["board_t"]
        b = box(p["board_w"], stack_t, 220.0,
                -p["board_w"] / 2.0, d["y_slot_back"] + 0.5,
                p["base_t"] + 0.5)
        b = rot_x(b, p["lean_deg"], (0, d["y_module_front"], p["base_t"]))
        probes.append(("board stack (%d x %.1fmm)"
                       % (p["n_boards"], p["board_t"]), b.common(keep)))

    for i, cx in enumerate(d["bay_x"]):
        probes.append(("eraser stack %d" % i, box(
            p["pad_w"], p["pad_d"], p["pads_per_bay"] * p["pad_t"],
            cx - p["pad_w"] / 2.0,
            d["y_bay_back"] + p["bay_wall"] + p["bay_clear"] / 2.0,
            p["base_t"] + p["tube_floor"] + 0.25)))

    if p["nameplate"]:
        notch_half = (d["bays_w"] + 1.0) / 2.0
        avail = d["half_w"] - notch_half - 5.0
        pocket_l = min(p["tile_l"] + p["tile_clear"], avail)
        pocket_h = p["tile_h"] + p["tile_clear"]
        pocket_t = p["tile_t"] + p["tile_clear"] / 2.0
        pz = p["base_t"] + (p["plinth_h"] - pocket_h) / 2.0
        py = d["y_plinth_front"] - pocket_t
        for side in (-1, 1):
            px = -d["half_w"] if side < 0 else d["half_w"] - pocket_l
            t, _ = tile_profile(d, pocket_l - 0.4, py + 0.1,
                                pz + p["tile_clear"] / 2.0, px + 0.2)
            t = rot_x(t, p["lean_deg"], (0, d["y_plinth_front"], p["base_t"]))
            probes.append(("tile %s" % ("L" if side < 0 else "R"), t))

    for label, probe in probes:
        try:
            v = shape.common(probe).Volume
        except Exception as exc:
            issues.append("%s: boolean failed (%s)" % (label, exc))
            continue
        if v > 1.0:
            issues.append("%s: INTERFERENCE %.1f mm3" % (label, v))
    return issues


def overhangs(shape, limit_deg=45.0, z_tol=0.05, min_area=5.0, samples=7):
    """Downward-facing surfaces, split by how much trouble they actually are.

    Returns (flat, curved).

    `flat` is planar ceilings - these are true bridges the printer must span
    unsupported, and are what you actually want to design out.

    `curved` is curved surfaces steeper than the limit somewhere on them, such
    as the top of an arch or a round hole. One sample per face wrongly condemns
    an entire arch, so curved faces are sampled on a grid and only the
    offending fraction of the area is reported. These are progressively
    supported and normally print fine.

    Faces resting on the bed are excluded. Face.normalAt already accounts for
    face orientation, so the result must NOT be flipped again - verified
    against a control solid with a deliberate floating ledge.
    """
    flat, curved = [], []
    zmin = shape.BoundBox.ZMin
    thr = -math.cos(math.radians(limit_deg))
    for f in shape.Faces:
        bb = f.BoundBox
        if abs(bb.ZMax - zmin) < z_tol or f.Area < min_area:
            continue
        try:
            us, ue, vs, ve = f.ParameterRange
        except Exception:
            continue
        if isinstance(f.Surface, Part.Plane):
            try:
                nz = f.normalAt((us + ue) / 2.0, (vs + ve) / 2.0).z
            except Exception:
                continue
            if nz < thr:
                flat.append((f.Area, bb.ZMin, bb.XLength, bb.YLength))
        else:
            bad = tot = 0
            for i in range(samples):
                for j in range(samples):
                    u = us + (ue - us) * (i + 0.5) / samples
                    v = vs + (ve - vs) * (j + 0.5) / samples
                    try:
                        nz = f.normalAt(u, v).z
                    except Exception:
                        continue
                    tot += 1
                    if nz < thr:
                        bad += 1
            if tot and bad:
                est = f.Area * bad / float(tot)
                if est >= min_area:
                    curved.append((est, bb.ZMin, bb.XLength, bb.YLength))
    flat.sort(key=lambda r: -r[0])
    curved.sort(key=lambda r: -r[0])
    return flat, curved


def watertight(shape, label):
    """Report anything that would make a slicer refuse the mesh.

    Shape.isValid() is not enough - it passes shapes whose faces
    self-intersect. Shape.check() is what catches those, and the mesh itself
    has to be tested separately because a valid solid can still tessellate
    into non-manifold edges wherever two bodies touch tangentially.
    """
    notes = []
    try:
        shape.check(True)
        brep_errs = 0
    except Exception as exc:
        brep_errs = str(exc).count("Error in")
    if brep_errs:
        notes.append("%d B-rep self-intersections" % brep_errs)
    if not shape.isClosed():
        notes.append("open shell")
    m = fine_mesh(shape)
    if m.hasNonManifolds():
        notes.append("mesh NON-MANIFOLD")
    if m.hasSelfIntersections():
        notes.append("mesh self-intersects")
    if not m.isSolid():
        notes.append("mesh not solid")
    return "%s: %s" % (label, "watertight" if not notes else "; ".join(notes))


def run():
    del MESH_LOG[:]
    report = []
    d = derive(PARAMS)

    body_doc, body_obj, d = build_body()
    body_doc.saveAs(os.path.join(HERE, "whiteboard_caddy.FCStd"))
    export_all(body_doc, [body_obj], "whiteboard_caddy")
    bb = body_obj.Shape.BoundBox
    report.append("body bbox  X=%.1f Y=%.1f Z=%.1f  vol=%.1f cm3  solid=%s"
                  % (bb.XLength, bb.YLength, bb.ZLength,
                     body_obj.Shape.Volume / 1000.0,
                     body_obj.Shape.isValid()))
    bed = (PARAMS["bed_x"], PARAMS["bed_y"], PARAMS["bed_z"])
    fits = (bb.XLength <= bed[0] and bb.YLength <= bed[1]
            and bb.ZLength <= bed[2])
    report.append("bed fit (%s %gx%gx%g): %s  margin X=%.1f Y=%.1f Z=%.1f"
                  % (PARAMS["printer_name"], bed[0], bed[1], bed[2],
                     "OK" if fits else "TOO BIG",
                     bed[0] - bb.XLength, bed[1] - bb.YLength,
                     bed[2] - bb.ZLength))
    report.append("fillets: %s" % ("; ".join(FILLET_LOG) or "none"))
    if d["warnings"]:
        report.append("WARNINGS: " + "; ".join(d["warnings"]))
    else:
        report.append("structural checks: clear (bay_post=%.1f bore_web=%.1f)"
                      % (d["bay_post_w"], d["tube_pitch"] - PARAMS["tube_id"]))
    report.append(watertight(body_obj.Shape, "body mesh"))
    flat, curved = overhangs(body_obj.Shape)
    report.append("flat ceilings (true bridges): %s"
                  % ("none" if not flat else
                     "; ".join("%.0f mm2 @ z=%.1f (%.0f x %.0f)" % r
                               for r in flat[:5])))
    report.append("curved overhang (progressive, normally fine): %s"
                  % ("none" if not curved else
                     "; ".join("~%.0f mm2 @ z=%.1f" % (r[0], r[1])
                               for r in curved[:5])))
    issues = check_fits(body_obj.Shape, d)
    report.append("fit check: %s" % ("all probes clear"
                                     if not issues else "; ".join(issues)))

    if PARAMS["nameplate"]:
        tile_doc, tile_objs = build_tiles()
        tile_doc.saveAs(os.path.join(HERE, "nameplate_tiles.FCStd"))
        export_all(tile_doc, tile_objs, "nameplate_tiles")
        for o in tile_objs:
            export_all(tile_doc, [o], o.Name,
                       deflection=0.05 if o.Name.startswith("text_") else None)
        report.append("tiles: %s" % ", ".join(o.Name for o in tile_objs))
    else:
        report.append("tiles: skipped (nameplate disabled)")

    cp_doc, cp_objs, cp_clash = build_coupon()
    cp_doc.saveAs(os.path.join(HERE, "fit_coupon.FCStd"))
    export_all(cp_doc, cp_objs, "fit_coupon")
    report.append(watertight(cp_objs[0].Shape, "coupon mesh"))
    cflat, ccurved = overhangs(cp_objs[0].Shape)
    report.append("coupon: %d flat ceilings, %d curved overhangs"
                  % (len(cflat), len(ccurved)))
    cb = cp_objs[0].Shape.BoundBox
    report.append("coupon bbox X=%.1f Y=%.1f Z=%.1f vol=%.1f cm3  "
                  "tile-in-pocket clash=%.1f mm3"
                  % (cb.XLength, cb.YLength, cb.ZLength,
                     cp_objs[0].Shape.Volume / 1000.0, cp_clash))

    report.append("meshes: " + "; ".join(MESH_LOG))
    report.append("font: %s" % pick_font())
    report.append("slot_depth=%.1f body_w=%.1f base_d=%.1f tube_x=%s"
                  % (d["slot_depth"], d["body_w"], d["base_d"],
                     ["%.1f" % v for v in d["tube_x"]]))
    return "\n".join(report)


# --------------------------------------------------------------------------
# Entry point: `freecadcmd build_caddy.py`
# --------------------------------------------------------------------------

def _main():
    report = run()
    print(report)
    sys.stdout.flush()
    return report


def _invoked_as_script():
    """True when this file was handed to freecadcmd / python as the script.

    freecadcmd sets __name__ to the module's basename rather than
    "__main__", so the usual guard never fires. Checking argv distinguishes
    `freecadcmd build_caddy.py` from `import build_caddy` in the console,
    which must NOT trigger a build on import.
    """
    if __name__ == "__main__":
        return True
    try:
        me = os.path.basename(__file__)
    except NameError:
        return False
    return any(os.path.basename(a) == me for a in sys.argv[1:])


if _invoked_as_script():
    _main()
