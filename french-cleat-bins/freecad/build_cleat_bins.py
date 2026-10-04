# -*- coding: utf-8 -*-
"""
French-cleat bins - parametric generator for FreeCAD.

Builds one-piece wall bins that hang on a Multiboard-mounted French cleat
rail, plus the rail itself.

As shipped - five parts:
  - screw_bin       2 x 1 lb boxes of 3" deck screws (~89 x 51 x 140 mm, the
                    common 3.5" x 2" x 5.5" retail box) standing upright side
                    by side, 70 mm walls, a low divider between them, and a
                    stand-off foot so the part below the rail hangs plumb
  - shallow_basket  same width, twice the depth off the wall, 50 mm back
                    sloping down to a 30 mm front - an open tray for loose
                    parts. 50 mm is the rail's own height, so the whole back
                    rests on the rail and no foot is needed
  - shallow_basket_half  the same basket at half the width (94.6 mm)
  - cleat_rail      a 7-unit (175 mm) rail that sits hidden behind the
                    full-width bins
  - cleat_rail_half a 3-unit (75 mm) rail, hidden behind the half basket.
                    On both, the plate, bevel and octagonal mounting bosses reproduce the
                    "Multiboard French Cleat Storage Bins" rail, measured off
                    its mesh, so the same Multiboard snaps hold it and that
                    set's bins hang on it too

The hook on both bins is the one from that set's bins: a 20 deg wedge slot,
18 mm deep, whose lip drops into the gap the rail's bevel leaves between the
rail and the board. Unlike the originals (main body + glued side panel,
printed on their side) each bin is a single part, printed upright. The only
supported overhang is the underside of the hook lip - a 1.8 mm strip.

Bin coordinates: X runs along the wall (centred), Y=0 is the rear face of
the back wall where it rests on the rail's front face, +Y points away from
the wall, -Y towards the board. Z=0 is the bottom of the floor.

Running it
----------
Headless (no GUI needed)::

    freecadcmd build_cleat_bins.py

Or from the Python console inside FreeCAD::

    import sys; sys.path.insert(0, "/path/to/this/folder")
    import build_cleat_bins; print(build_cleat_bins.run())

Outputs land in ./exports as STEP, STL and 3MF.

What it checks
--------------
  * fit          - probe solids of each screw box, the rail (plate, bevel and
                   bosses) and the board face are pushed through each bin; any
                   intersection means it will not fit. The rail is also raised
                   0.3 mm to prove it bears on the lip rather than rattling.
  * structural   - lip tip, hook block above the slot, wall/floor thickness,
                   rail-to-foot clearance and swing-in clearance when hanging
                   it, or that the rail supports the back when there is no foot
  * printability - downward-facing surfaces, split into true flat bridges and
                   harmless progressive overhang (the lip underside is the one
                   expected flat bridge on a bin; the rail has none)
  * mesh health  - B-rep self-intersection, closed shell, and non-manifold
                   tessellation, because a slicer will reject those

Print the fit coupon before committing to a full part.

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

# Shared by every part: the cleat interface, printer and structural limits.
PARAMS = {
    # --- cleat hook -------------------------------------------------------
    # Measured from the Multiboard French Cleat Storage Bins meshes.
    "hook_top_t":     7.0,     # solid block above the slot apex
    "slot_depth":     18.0,    # slot apex down to lip tip
    "lip_out":        10.2,    # lip outer face, measured from Y=0
    "lip_tip_t":      1.82,    # lip thickness at its tip
    "cleat_deg":      20.0,    # wedge angle of the rail bevel / lip face
    "slot_clear":     0.0,     # widens the slot (thins the lip). The original
                               # bins use zero - the wedge self-locates - so
                               # only raise it if the coupon will not seat.
    "apex_roof":      1.5,     # peaked slot apex instead of a 1.8 mm flat
                               # ceiling: roof rise per unit half-width

    # --- rail -------------------------------------------------------------
    # 42.8 mm tall, 5.0 mm plate; top 8.74 mm bevelled 20 deg on the board
    # side down to 1.82 mm. Octagonal bosses on the board side (13.5 mm across
    # flats, 8.4 mm tall, slight taper, chamfered tip) sit on 25 mm unit
    # centres, 12.5 mm up from the rail's bottom edge, and hold the plate
    # 13.4 mm off the board.
    "unit":           25.0,
    "rail_h":         42.8,
    "rail_plate_t":   5.0,
    "rail_bevel_h":   8.74,
    "rail_standoff":  13.4,    # rail front face to board face
    "boss_af":        13.5,    # across flats at the root
    "boss_af_mid":    13.22,   # across flats where the tip chamfer starts
    "boss_af_tip":    12.2,
    "boss_straight":  1.0,     # untapered root length
    "boss_chamfer":   0.5,
    "boss_z":         12.5,    # boss centre above the rail bottom edge

    # --- common bin construction ------------------------------------------
    # Load path is hook -> back wall -> (foot against the board). Only the
    # back wall carries the hanging load, so it stays thick; front and side
    # walls only contain the contents and are thinned to save filament.
    "back_wall":      2.4,     # 6 perimeters at 0.4 mm
    "wall":           1.6,     # front + sides, 4 perimeters at 0.4 mm
    "foot_pads":      3,       # foot split into pads: both ends + middle.
    "foot_pad_w":     20.0,    # Only needs to touch the board, not run the
                               # full width - and the slicer can then reach
                               # the lip from the bed for its support.
    "weld_overlap":   1.0,     # bodies that merely touch make tangential
                               # contact, which tessellates non-manifold;
                               # adjacent bodies overlap by this much instead
    "foot_clear":     0.0,     # pull the foot off the board by this much
    "rail_foot_gap_min": 3.0,  # rail bottom edge must clear the foot top
    "no_foot_max_gap": 5.0,    # without a foot, the rail must reach within
                               # this of the bin bottom to hold it plumb

    # --- printer ----------------------------------------------------------
    "bed_x":          256.0,
    "bed_y":          256.0,
    "bed_z":          256.0,
    "printer_name":   "256mm bed",
    "density":        1.27,    # g/cm3, PETG - for the weight estimate

    # --- structural minimums ---------------------------------------------
    "min_wall":       1.6,
    "min_lip":        1.2,
    "min_hook_block": 4.0,
}

# One entry per rail length, in 25 mm Multiboard units. Each rail should be
# no wider than the bin it sits behind, so it stays hidden - checked on every
# run against the bin named in "behind".
RAILS = {
    "cleat_rail":      {"units": 7, "behind": "shallow_basket"},       # 175 mm
    "cleat_rail_half": {"units": 3, "behind": "shallow_basket_half"},  # 75 mm
}

# One entry per bin. Each is merged over PARAMS.
VARIANTS = {
    "screw_bin": {
        # 2 x 1 lb boxes of 3" deck screws, upright, side by side
        "n_boxes":     2,
        "box_w":       89.0,   # 3.5" - along the wall
        "box_d":       51.0,   # 2"   - away from the wall
        "box_h":       140.0,  # 5.5" - only used by the fit probe
        "box_clear_x": 3.0,    # side-to-side slack per box
        "box_clear_y": 3.0,    # front-to-back slack
        "floor_t":     2.0,    # prints on the bed, every edge on a wall
        "wall_h":      70.0,   # half the box height: holds it upright, lid
                               # stays free to open
        "front_h":     70.0,
        "divider":     True,   # stops the boxes sliding, stiffens the front
        "divider_h":   35.0,
        "divider_t":   2.0,
        "foot_h":      8.0,    # bin hangs 20 mm below the rail - the foot
                               # reaches back to the board to keep it plumb
    },
    "shallow_basket": {
        # Loose parts. Same outer width as the screw bin, about twice the
        # depth, low sloped front for reaching in.
        "n_boxes":     0,
        "in_w":        186.0,
        "in_d":        110.0,
        "floor_t":     2.0,
        "wall_h":      50.0,   # the lowest back that still carries the hook
                               # and rests on the full rail height
        "front_h":     30.0,
        "divider":     False,
        "foot_h":      0.0,
    },
    "shallow_basket_half": {
        # Half the outer width of shallow_basket (94.6 mm), everything else
        # the same. Two sit side by side in one full basket's footprint.
        "n_boxes":     0,
        "in_w":        91.4,   # 94.6 outer - 2 x 1.6 mm side walls
        "in_d":        110.0,
        "floor_t":     2.0,
        "wall_h":      50.0,
        "front_h":     30.0,
        "divider":     False,
        "foot_h":      0.0,
    },
}


def _script_dir():
    """Folder this file lives in, whichever way it was invoked."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.path.abspath(os.getcwd())


HERE = _script_dir()
EXPORTS = os.path.join(HERE, "exports")


# --------------------------------------------------------------------------
# Derived geometry
# --------------------------------------------------------------------------

def variant_params(name):
    p = dict(PARAMS)
    p.update(VARIANTS[name])
    p["name"] = name
    return p


def derive(p):
    d = dict(p)
    n = p["n_boxes"]
    div_t = p["divider_t"] if p["divider"] else 0.0
    if n:
        d["cell_w"] = p["box_w"] + p["box_clear_x"]
        d["in_w"] = n * d["cell_w"] + (n - 1) * div_t
        d["in_d"] = p["box_d"] + p["box_clear_y"]
    else:
        d["cell_w"] = p["in_w"]
    d["out_w"] = d["in_w"] + 2 * p["wall"]
    d["out_d"] = d["in_d"] + p["back_wall"] + p["wall"]
    d["half_w"] = d["out_w"] / 2.0

    # compartment centres along X
    x0 = -d["in_w"] / 2.0
    cells = max(n, 1)
    step = d["cell_w"] + div_t
    d["cell_x"] = [x0 + d["cell_w"] / 2.0 + i * step for i in range(cells)]
    d["div_x"] = ([x0 + d["cell_w"] + i * step for i in range(cells - 1)]
                  if p["divider"] else [])

    # hook: Z of the slot apex and lip tip, Y of the lip's inner face
    t = math.tan(math.radians(p["cleat_deg"]))
    d["z_apex"] = p["wall_h"] - p["hook_top_t"]
    d["z_lip"] = d["z_apex"] - p["slot_depth"]
    c = p["slot_clear"]
    d["y_lip_in_top"] = -(p["lip_out"] - p["lip_tip_t"]
                          - p["slot_depth"] * t) - c
    d["lip_tip"] = p["lip_tip_t"] - c
    half = -d["y_lip_in_top"] / 2.0
    d["apex_peak"] = d["z_apex"] + half * p["apex_roof"]
    d["hook_block"] = p["wall_h"] - d["apex_peak"]

    # rail sits with its top edge at the apex, front face on Y=0
    d["rail_top"] = d["z_apex"]
    d["rail_bot"] = d["z_apex"] - p["rail_h"]
    d["y_board"] = -p["rail_standoff"]

    w = []
    for key in ("back_wall", "wall", "floor_t") + (("divider_t",) if p["divider"] else ()):
        if p[key] < p["min_wall"]:
            w.append("%s %.2f < %.2f" % (key, p[key], p["min_wall"]))
    if d["lip_tip"] < p["min_lip"]:
        w.append("lip tip %.2f < %.2f" % (d["lip_tip"], p["min_lip"]))
    if d["hook_block"] < p["min_hook_block"]:
        w.append("hook block %.2f < %.2f"
                 % (d["hook_block"], p["min_hook_block"]))
    if p["lip_out"] >= p["rail_standoff"]:
        w.append("lip reaches the board (lip_out %.1f >= standoff %.1f)"
                 % (p["lip_out"], p["rail_standoff"]))
    if d["z_lip"] <= d["rail_top"] - _boss_top_below_rail_top(p):
        w.append("lip tip reaches the rail bosses")
    if p["front_h"] > p["wall_h"]:
        w.append("front_h above wall_h")

    if p["foot_h"] > 0:
        if p["foot_pads"] < 1 or p["foot_pads"] * p["foot_pad_w"] > d["out_w"]:
            w.append("foot pads do not fit: %d x %.1f mm on a %.1f mm bin"
                     % (p["foot_pads"], p["foot_pad_w"], d["out_w"]))
        d["rail_foot_gap"] = d["rail_bot"] - p["foot_h"]
        if d["rail_foot_gap"] < p["rail_foot_gap_min"]:
            w.append("rail bottom only %.1f mm above foot (need %.1f) - "
                     "raise wall_h or lower foot_h"
                     % (d["rail_foot_gap"], p["rail_foot_gap_min"]))
        # Hanging it: hook over the rail with the bottom tilted out, then
        # swing the bottom in about the slot apex. The foot clears the rail
        # on that swing if its nearest corner stays outside the rail's
        # farthest corner.
        py, pz = d["y_lip_in_top"] / 2.0, d["z_apex"]
        rail_r = max(math.hypot(y - py, z - pz) for y, z in rail_profile(d))
        fy0 = d["y_board"] + p["foot_clear"]
        foot_r = min(math.hypot(y - py, z - pz)
                     for y in (fy0, 0.0) for z in (0.0, p["foot_h"]))
        d["swing_margin"] = foot_r - rail_r
        if d["swing_margin"] < 1.0:
            w.append("foot hits the rail while swinging the bin in "
                     "(margin %.1f mm)" % d["swing_margin"])
    else:
        # no foot: the rail itself has to hold the bottom of the back plumb
        if d["rail_bot"] > p["no_foot_max_gap"]:
            w.append("no foot, but the rail stops %.1f mm above the bin "
                     "bottom - the bin will hang tilted; set foot_h"
                     % d["rail_bot"])
    d["warnings"] = w
    return d


def _boss_top_below_rail_top(p):
    return p["rail_h"] - p["boss_z"] - p["boss_af"] / 2.0


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def box(l, w, h, x, y, z):
    return Part.makeBox(l, w, h, App.Vector(x, y, z))


def _yz_prism(pts, x0, length):
    """Extrude a closed (y, z) polygon along +X from x0."""
    vs = [App.Vector(x0, y, z) for y, z in pts]
    vs.append(vs[0])
    face = Part.Face(Part.makePolygon(vs))
    return face.extrude(App.Vector(length, 0, 0))


def _new_doc(name):
    for existing in list(App.listDocuments().keys()):
        if existing == name:
            App.closeDocument(name)
    return App.newDocument(name)


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


# --------------------------------------------------------------------------
# Rail
# --------------------------------------------------------------------------

def rail_profile(d, dy=0.0, dz=0.0, bosses=True):
    """(y, z) outline of the rail as mounted, top edge at d["rail_top"].

    With bosses=True the bosses are included as a full-length band - the
    conservative envelope used for fit probes.
    """
    p = d
    T = d["rail_top"]
    bt = _boss_top_below_rail_top(p)
    bb = bt + p["boss_af"]
    top_t = p["rail_plate_t"] - p["rail_bevel_h"] * math.tan(
        math.radians(p["cleat_deg"]))
    pts = [(0.0, T), (-top_t, T),
           (-p["rail_plate_t"], T - p["rail_bevel_h"])]
    if bosses:
        pts += [(-p["rail_plate_t"], T - bt),
                (-p["rail_standoff"], T - bt),
                (-p["rail_standoff"], T - bb),
                (-p["rail_plate_t"], T - bb)]
    pts += [(-p["rail_plate_t"], T - p["rail_h"]), (0.0, T - p["rail_h"])]
    return [(y + dy, z + dz) for y, z in pts]


def rail_boss_units(n):
    """Unit indices that carry a boss: both end units, then every other unit
    working inwards, mirrored. Reproduces the original 3/4/5/6-unit rails
    (3: 0,2  4: 0,3  5: 0,2,4  6: 0,2,3,5)."""
    s = set()
    for i in range(0, (n + 1) // 2, 2):
        s.add(i)
        s.add(n - 1 - i)
    return sorted(s)


def _octagon(af, y0, cx, cz):
    """Regular octagon in the XZ plane at Y=y0, across flats af."""
    a = af / 2.0
    b = a * math.tan(math.radians(22.5))
    pts = [(a, b), (b, a), (-b, a), (-a, b), (-a, -b), (-b, -a), (b, -a),
           (a, -b)]
    vs = [App.Vector(cx + x, y0, cz + z) for x, z in pts]
    vs.append(vs[0])
    return Part.makePolygon(vs)


def make_boss(p, cx, cz):
    """Octagonal boss growing from the plate's board face (Y=-plate_t)
    towards the board (Y=-standoff)."""
    y0 = -p["rail_plate_t"] + p["weld_overlap"]
    y1 = -p["rail_plate_t"] - p["boss_straight"]
    y3 = -p["rail_standoff"]
    y2 = y3 + p["boss_chamfer"]
    wires = [_octagon(p["boss_af"], y0, cx, cz),
             _octagon(p["boss_af"], y1, cx, cz),
             _octagon(p["boss_af_mid"], y2, cx, cz),
             _octagon(p["boss_af_tip"], y3, cx, cz)]
    return Part.makeLoft(wires, True, True)


def make_rail(p, units):
    """Rail in mounted orientation: bottom edge at Z=0, front face on Y=0,
    centred on X."""
    L = units * p["unit"]
    d = dict(p)
    d["rail_top"] = p["rail_h"]
    solid = _yz_prism(rail_profile(d, bosses=False), -L / 2.0, L)
    for i in rail_boss_units(units):
        cx = -L / 2.0 + p["unit"] * (i + 0.5)
        solid = solid.fuse(make_boss(p, cx, p["boss_z"]))
    return solid


def rail_print_pose(shape):
    """Front face down on the bed, bosses up - same as the original rails."""
    s = shape.copy()
    s.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), -90)
    bb = s.BoundBox
    s.translate(App.Vector(-bb.XMin - bb.XLength / 2.0, -bb.YMin, -bb.ZMin))
    return s


# --------------------------------------------------------------------------
# Bin geometry
# --------------------------------------------------------------------------

def hook_profile(d):
    """(y, z) outline of the cleat hook, welded into the back wall."""
    ov = d["weld_overlap"]
    return [
        (ov, d["wall_h"]),
        (-d["lip_out"], d["wall_h"]),
        (-d["lip_out"], d["z_lip"]),
        (-d["lip_out"] + d["lip_tip"], d["z_lip"]),
        (d["y_lip_in_top"], d["z_apex"]),
        (d["y_lip_in_top"] / 2.0, d["apex_peak"]),
        (0.0, d["z_apex"]),
        (ov, d["z_apex"]),
    ]


def side_profile(d):
    """(y, z) outline of the tub seen from the side. The top runs level
    across the back wall, then slopes down to the front wall when
    front_h < wall_h."""
    D, t, tb = d["out_d"], d["wall"], d["back_wall"]
    pts = [(0.0, 0.0), (D, 0.0), (D, d["front_h"])]
    if d["front_h"] < d["wall_h"]:
        pts.append((D - t, d["front_h"]))
        pts.append((tb, d["wall_h"]))
    pts.append((0.0, d["wall_h"]))
    return pts


def make_tub(d):
    """Open-top tub: floor, four walls, optional dividers."""
    solid = _yz_prism(side_profile(d), -d["half_w"], d["out_w"])
    cavity = box(d["in_w"], d["in_d"], d["wall_h"] + 1,
                 -d["in_w"] / 2.0, d["back_wall"], d["floor_t"])
    solid = solid.cut(cavity)
    for x in d["div_x"]:
        solid = solid.fuse(box(
            d["divider_t"], d["in_d"] + 2 * d["weld_overlap"],
            d["divider_h"] - d["floor_t"] + d["weld_overlap"],
            x, d["back_wall"] - d["weld_overlap"],
            d["floor_t"] - d["weld_overlap"]))
    return solid


def make_hook(d, length=None, x0=None):
    length = d["out_w"] if length is None else length
    x0 = -d["half_w"] if x0 is None else x0
    return _yz_prism(hook_profile(d), x0, length)


def foot_pad_x(d):
    """Left edge of each foot pad, spread evenly from end to end."""
    n, w = d["foot_pads"], d["foot_pad_w"]
    if n <= 1:
        return [-w / 2.0]
    span = d["out_w"] - w
    return [-d["half_w"] + i * span / (n - 1) for i in range(n)]


def make_foot(d):
    y0 = d["y_board"] + d["foot_clear"]
    solid = None
    for x in foot_pad_x(d):
        pad = box(d["foot_pad_w"], -y0 + d["weld_overlap"], d["foot_h"],
                  x, y0, 0)
        solid = pad if solid is None else solid.fuse(pad)
    return solid


def build_bin(name):
    doc = _new_doc(name)
    p = variant_params(name)
    d = derive(p)
    solid = make_tub(d).fuse(make_hook(d))
    if d["foot_h"] > 0:
        solid = solid.fuse(make_foot(d))
    # removeSplitter() deliberately not used - see whiteboard-stand's
    # build_caddy.py: merging coplanar faces has produced self-intersecting
    # edges that only Shape.check() catches.
    obj = doc.addObject("Part::Feature", "Bin")
    obj.Shape = solid
    write_spreadsheet(doc, p)
    doc.recompute()
    return doc, obj, d


def build_rail(name):
    doc = _new_doc(name)
    obj = doc.addObject("Part::Feature", "Rail")
    obj.Shape = rail_print_pose(make_rail(PARAMS, RAILS[name]["units"]))
    p = dict(PARAMS)
    p["rail_units"] = RAILS[name]["units"]
    write_spreadsheet(doc, p)
    doc.recompute()
    return doc, obj


def build_coupon():
    """Three quick test pieces, exported together.

    CouponRail - one unit (25 mm) of rail with one boss. Push a Multiboard
    snap onto the boss and hang it on your board.

    CouponHook - a 25 mm slice of the bin hook (identical on every bin),
    printed on its side so it needs no support. It should drop onto the
    rail coupon, or onto a full rail, and sit flat without rocking.

    CouponFrame - a 10 mm ring whose inside is one screw-bin compartment.
    Slide it over one of your screw boxes: it should drop freely without
    being sloppy.
    """
    doc = _new_doc("fit_coupon")
    d = derive(variant_params("screw_bin"))
    L = 25.0
    z_cut = d["z_apex"] - 30.0
    hook = box(L, d["back_wall"], d["wall_h"] - z_cut, 0, 0, z_cut)
    hook = hook.fuse(make_hook(d, L, 0.0))
    hook.rotate(App.Vector(0, 0, 0), App.Vector(0, 1, 0), -90)
    bb = hook.BoundBox
    hook.translate(App.Vector(-bb.XMin, -bb.YMin, -bb.ZMin))

    fw, fd, fh, ft = d["cell_w"], d["in_d"], 10.0, 1.6
    frame = box(fw + 2 * ft, fd + 2 * ft, fh, 0, 0, 0)
    frame = frame.cut(box(fw, fd, fh + 2, ft, ft, -1))
    frame.translate(App.Vector(hook.BoundBox.XMax + 8.0, 0, 0))

    rail = rail_print_pose(make_rail(PARAMS, 1))
    rb = rail.BoundBox
    rail.translate(App.Vector(-rb.XMin, fd + 2 * ft + 8.0 - rb.YMin, 0))

    made = []
    for name, shp in (("CouponRail", rail), ("CouponHook", hook),
                      ("CouponFrame", frame)):
        o = doc.addObject("Part::Feature", name)
        o.Shape = shp
        made.append(o)
    write_spreadsheet(doc, PARAMS)
    doc.recompute()
    return doc, made


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

LINEAR_DEFLECTION = 0.02
ANGULAR_DEFLECTION = math.radians(5.0)
MESH_LOG = []


def fine_mesh(shape, linear=None):
    import MeshPart
    return MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=LINEAR_DEFLECTION if linear is None else linear,
        AngularDeflection=ANGULAR_DEFLECTION,
        Relative=False)


def export_all(doc, objs, stem, deflection=None):
    """Write STEP (exact) plus STL and 3MF meshed at explicit fine quality."""
    if not os.path.isdir(EXPORTS):
        os.makedirs(EXPORTS)
    import Import
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
    for path in (stl, tmf):
        try:
            merged.write(path)
        except Exception as exc:
            App.Console.PrintWarning("%s export failed: %s\n" % (path, exc))
    MESH_LOG.append("%s %.1fk facets %.1fs"
                    % (stem, merged.CountFacets / 1000.0, time.time() - t0))
    return step, stl


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_fits(shape, d):
    """Push a probe solid of every real object through a bin.

    The rail probe is dropped 0.3 mm and pulled 0.05 mm off the back wall so
    the intended wedge contact does not register as interference; anything
    beyond that is a real clash.
    """
    issues = []
    probes = []
    for i, cx in enumerate(d["cell_x"] if d["n_boxes"] else []):
        probes.append(("screw box %d" % (i + 1), box(
            d["box_w"], d["box_d"], d["box_h"],
            cx - d["box_w"] / 2.0,
            d["back_wall"] + d["box_clear_y"] / 2.0,
            d["floor_t"] + 0.1)))
    probes.append(("cleat rail", _yz_prism(
        rail_profile(d, dy=-0.05, dz=-0.3), -d["half_w"] - 5,
        d["out_w"] + 10)))
    probes.append(("board face", box(
        d["out_w"] + 20, 50.0, d["wall_h"] + 20,
        -d["half_w"] - 10, d["y_board"] - 50.0 - 0.05, -10)))
    for label, probe in probes:
        try:
            v = shape.common(probe).Volume
        except Exception as exc:
            issues.append("%s: boolean failed (%s)" % (label, exc))
            continue
        if v > 1.0:
            issues.append("%s: INTERFERENCE %.1f mm3" % (label, v))

    # The rail must actually bear on the lip, not float in a loose slot:
    # raised 0.3 mm it should dig into the lip. Clipped below the apex so
    # the raised top edge poking into the apex roof does not count.
    snug = _yz_prism(rail_profile(d, dz=0.3), -d["half_w"], d["out_w"])
    snug = snug.common(box(d["out_w"], 30.0, d["z_apex"] - 1.0,
                           -d["half_w"], -25.0, 0))
    if shape.common(snug).Volume < 1.0:
        issues.append("cleat rail: slot is loose - rail raised 0.3 mm still "
                      "does not touch the lip")
    return issues


def check_rail_matches(units):
    """The printed rail must be the same envelope the bins were checked
    against: its plate + boss band cross-section equals rail_profile."""
    d = dict(PARAMS)
    d["rail_top"] = PARAMS["rail_h"]
    env = _yz_prism(rail_profile(d, bosses=True), -500, 1000)
    mounted = make_rail(PARAMS, units)
    outside = mounted.cut(env).Volume
    return outside


def overhangs(shape, limit_deg=45.0, z_tol=0.05, min_area=5.0, samples=7):
    """Downward-facing surfaces: (flat bridges, curved overhang). See
    whiteboard-stand's build_caddy.py for the reasoning behind the split."""
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
    """B-rep check() plus mesh manifold/self-intersection/solid tests."""
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


def _is_lip_underside(r, d):
    area, zmin, xl, yl = r
    return abs(zmin - d["z_lip"]) < 0.05 and abs(yl - d["lip_tip"]) < 0.05


def _size_report(label, s, p):
    bb = s.BoundBox
    fits = (bb.XLength <= p["bed_x"] and bb.YLength <= p["bed_y"]
            and bb.ZLength <= p["bed_z"])
    return ("%s bbox X=%.1f Y=%.1f Z=%.1f  vol=%.1f cm3 (~%.0f g)  "
            "solid=%s  bed (%s): %s"
            % (label, bb.XLength, bb.YLength, bb.ZLength, s.Volume / 1000.0,
               s.Volume / 1000.0 * p["density"], s.isValid(),
               p["printer_name"], "OK" if fits else "TOO BIG"))


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def report_bin(name, report):
    doc, obj, d = build_bin(name)
    doc.saveAs(os.path.join(HERE, name + ".FCStd"))
    export_all(doc, [obj], name)
    s = obj.Shape
    report.append("== %s" % name)
    report.append("  " + _size_report("body", s, d))
    if d["warnings"]:
        report.append("  STRUCTURAL WARNINGS: " + "; ".join(d["warnings"]))
    else:
        extra = ("rail-to-foot gap=%.1f swing-in margin=%.1f"
                 % (d["rail_foot_gap"], d["swing_margin"])
                 if d["foot_h"] > 0 else
                 "no foot, rail reaches %.1f mm off the bottom" % d["rail_bot"])
        report.append("  structural checks: clear (lip tip=%.2f hook "
                      "block=%.1f back wall=%.1f walls=%.1f floor=%.1f %s)"
                      % (d["lip_tip"], d["hook_block"], d["back_wall"],
                         d["wall"],
                         d["floor_t"], extra))
    report.append("  " + watertight(s, "mesh"))
    flat, curved = overhangs(s)
    expected = [r for r in flat if _is_lip_underside(r, d)]
    other = [r for r in flat if not _is_lip_underside(r, d)]
    report.append("  flat ceilings: expected lip underside %s; other %s"
                  % ("%.0f mm2 @ z=%.1f" % expected[0][:2] if expected
                     else "none",
                     "none" if not other else
                     "; ".join("%.0f mm2 @ z=%.1f (%.0f x %.0f)" % r
                               for r in other[:5])))
    report.append("  curved overhang: %s"
                  % ("none" if not curved else
                     "; ".join("~%.0f mm2 @ z=%.1f" % r[:2]
                               for r in curved[:5])))
    issues = check_fits(s, d)
    report.append("  fit check: %s" % ("all probes clear, rail seats on lip"
                                       if not issues else "; ".join(issues)))
    report.append("  inside %.1f x %.1f, outside %.1f x %.1f, back %.0f / "
                  "front %.0f mm, lip tip z=%.1f, rail z=%.1f..%.1f"
                  % (d["in_w"], d["in_d"], d["out_w"], d["out_d"],
                     d["wall_h"], d["front_h"], d["z_lip"], d["rail_bot"],
                     d["rail_top"]))


def report_rail(name, spec, report):
    units = spec["units"]
    doc, obj = build_rail(name)
    doc.saveAs(os.path.join(HERE, name + ".FCStd"))
    export_all(doc, [obj], name)
    s = obj.Shape
    report.append("== %s (%d units, bosses on units %s)"
                  % (name, units, rail_boss_units(units)))
    report.append("  " + _size_report("body", s, PARAMS))
    report.append("  " + watertight(s, "mesh"))
    flat, curved = overhangs(s)
    report.append("  flat ceilings: %d, curved overhang: %d"
                  % (len(flat), len(curved)))
    outside = check_rail_matches(units)
    report.append("  matches the envelope the bins were fit-checked "
                  "against: %s" % ("yes" if outside < 1.0 else
                                   "NO - %.1f mm3 outside" % outside))
    bin_w = derive(variant_params(spec["behind"]))["out_w"]
    rail_w = units * PARAMS["unit"]
    report.append("  hidden behind %s (%.1f mm): %s"
                  % (spec["behind"], bin_w,
                     "yes, %.1f mm spare each side" % ((bin_w - rail_w) / 2.0)
                     if rail_w <= bin_w else
                     "NO - rail sticks out %.1f mm each side"
                     % ((rail_w - bin_w) / 2.0)))


def run():
    del MESH_LOG[:]
    report = []
    for name in VARIANTS:
        report_bin(name, report)

    for name, spec in RAILS.items():
        report_rail(name, spec, report)

    cp_doc, cp_objs = build_coupon()
    cp_doc.saveAs(os.path.join(HERE, "fit_coupon.FCStd"))
    export_all(cp_doc, cp_objs, "fit_coupon")
    report.append("== fit_coupon")
    for o in cp_objs:
        cf, cc = overhangs(o.Shape)
        report.append("  %s; %d flat ceilings, %d curved overhangs"
                      % (watertight(o.Shape, o.Name), len(cf), len(cc)))

    report.append("meshes: " + "; ".join(MESH_LOG))
    return "\n".join(report)


# --------------------------------------------------------------------------
# Entry point: `freecadcmd build_cleat_bins.py`
# --------------------------------------------------------------------------

def _main():
    report = run()
    print(report)
    sys.stdout.flush()
    return report


def _invoked_as_script():
    """True when handed to freecadcmd / python as the script (freecadcmd sets
    __name__ to the basename, so the usual guard never fires)."""
    if __name__ == "__main__":
        return True
    try:
        me = os.path.basename(__file__)
    except NameError:
        return False
    return any(os.path.basename(a) == me for a in sys.argv[1:])


if _invoked_as_script():
    _main()
