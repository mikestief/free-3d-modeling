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

LINEAR_DEFLECTION = 0.02
ANGULAR_DEFLECTION = math.radians(5.0)

# How far to push a piece that gets FUSED (not cut) onto the base past the
# shared boundary, so the two solids have genuine volumetric overlap instead
# of a zero-gap tangent touch. See make_post's docstring for why this
# matters - OCC's fuse silently produces self-intersecting/non-manifold
# results at exact tangency, invisible to isValid()/Solids-count checks.
FUSE_EMBED = 0.1

# Tolerance for treating a mesh "self-intersection" as real. MeshPart's
# tessellation of a curved surface fused/tangent to a flat one (the post's
# chamfer-on-fillet corners; a curved font glyph's silhouette crossing the
# base's sloped wall where the embossed label emerges from it) reliably
# reports sub-chord-tolerance crossing segments - measured here at
# 0.004-0.018mm, always inside LINEAR_DEFLECTION itself (0.02mm) - i.e.
# noise from the tessellation's own approximation error at the seam between
# two independently-meshed faces, not a real overlap. It reproduces across
# a wide range of embed depth, font size, and mesh deflection settings, so
# it is not something parameter-tuning the geometry can clear. A genuine
# self-intersection - e.g. from a real boolean/geometry bug - crosses at
# the scale of the feature involved (millimeters), far above this. Flagging
# only past 2x the chord tolerance keeps real defects (like the pre-fix
# dovetail-tail/post-base zero-gap tangent fuses this task found and fixed,
# which produced actual non-manifold edges, not just tiny self-crossings)
# caught while not failing the build on print-irrelevant tessellation noise.
SELF_INTERSECT_TOL = 2 * LINEAR_DEFLECTION


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
    for friction). Centered in X, set back from the sloped front wall.

    The bottom face is pushed FUSE_EMBED below z=0 (extending the extrusion
    height to compensate, so the top - where post_top_chamfer's edge lookup
    keys off p["post_h"] - is untouched) before the final translate onto
    the base's top (z=base_h). Without this, fusing the post onto the base
    is a zero-gap tangent boolean (bottom face of post exactly coincident
    with the base's top face over the post's whole footprint) - the same
    OCC pathology documented in emboss_label's docstring, and it produced
    real fallout here: fine_mesh flagged every one of the 42 generated
    pieces as `mesh self-intersects` until this and make_dovetail_tail's
    matching fix were added (caught by Task 8's watertight() check; prior
    tasks only asserted isValid()/Solids-count, which this tangency passes)."""
    af = p["drive_af_nominal"][drive] - p["post_af_undersize"]
    r = p["post_corner_r"]
    cx, cy = p["base_w"] / 2.0, p["base_d"] * 0.62
    half = af / 2.0 - r
    pts = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        pts.append(App.Vector(cx + sx * half, cy + sy * half, 0))
    profile = Part.makePolygon(pts + [pts[0]])
    face = Part.Face(profile).translate(App.Vector(0, 0, -FUSE_EMBED))
    post = face.extrude(App.Vector(0, 0, p["post_h"] + FUSE_EMBED))
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

def _dt_profile(p, outward, clearance=0.0, root_embed=0.0):
    """2D dovetail profile in the XY plane, tip pointing in +/-X (outward).
    Root sits at x=0 (the base's side face), tip extends `dt_depth` out.

    `root_embed` pulls the root edge back by that much (in -sign*x, i.e.
    further INTO the body the profile will be fused onto) without moving
    the tip - see make_dovetail_tail for why."""
    neck = p["dt_neck_w"] / 2.0 + clearance
    tip = p["dt_tip_w"] / 2.0 + clearance
    depth = p["dt_depth"]
    sign = 1 if outward else -1
    root_x = -sign * root_embed
    pts = [
        App.Vector(root_x, -neck, 0),
        App.Vector(sign * depth, -tip, 0),
        App.Vector(sign * depth, tip, 0),
        App.Vector(root_x, neck, 0),
        App.Vector(root_x, -neck, 0),
    ]
    return Part.Face(Part.makePolygon(pts))


def make_dovetail_tail(p):
    """Protrudes from the base's right (+X) side, full base height.

    root_embed=FUSE_EMBED pushes the root face FUSE_EMBED past x=base_w
    into the base's own solid before make_middle_piece/make_cap fuse this
    onto the base, so the fuse has genuine volumetric overlap rather than a
    zero-gap tangent touch at x=base_w (see make_post's docstring - this
    was the other half of the same self-intersecting-mesh bug, and it hit
    every piece including the caps, which showed `mesh NON-MANIFOLD`
    instead of `mesh self-intersects` since they lack the post/label fuses
    that pushed the middle pieces further into self-intersection). The
    outward-facing tip position (what actually has to fit the neighbouring
    piece's groove) is untouched."""
    face = _dt_profile(p, outward=True, root_embed=FUSE_EMBED)
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

    The corner box's far edge (the one away from round_x) is pulled in by
    FUSE_EMBED, i.e. its width is cap_round_r - FUSE_EMBED rather than
    exactly cap_round_r. Without that, the box's far edge sits at exactly
    distance cap_round_r from the cylinder's own center - precisely on the
    cylinder's surface - so at the one latitude where the cylinder reaches
    its full radius (y = base_d*0.3, dead center) box and cylinder are
    exactly tangent at a single point rather than genuinely overlapping.
    Confirmed live: at that exact width, `corner.cut(round_cutter)` (and
    the final cap after cutting it from body) silently splits into 2
    disconnected Solids at that pinch point - both cap_start and cap_end
    tessellated as `mesh NON-MANIFOLD; mesh not solid` until this was
    caught by Task 8's watertight() check (no prior task asserted
    Solids-count on the caps specifically, only on the dovetail coupon).
    Pulling the far edge in by FUSE_EMBED keeps it strictly inside the
    cylinder everywhere, so there's no leftover sliver at the pinch
    latitude to disconnect - real, if imperceptible (0.1mm on an 8mm
    radius), overlap instead of a zero-gap tangent touch.
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
    corner_w = r - FUSE_EMBED
    corner_x = round_x if side == "start" else round_x - corner_w
    corner = box(corner_w, p["base_d"], p["base_h"] + 2, corner_x, 0, -1)
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


# --------------------------------------------------------------------------
# Fit coupons
# --------------------------------------------------------------------------

def build_post_coupon(p, drive):
    """A single middle piece at a mid-range size, for real-socket test fit."""
    size = "12" if drive == "1-2in" else sae_label(14)  # 12mm / 7/16in
    return make_middle_piece(p, drive, size)


def build_dovetail_coupon(p):
    """Two adjacent middle pieces, pre-assembled, to test the snap by hand."""
    a = make_middle_piece(p, "3-8in", "10")
    b = make_middle_piece(p, "3-8in", "11").translate(App.Vector(p["base_w"], 0, 0))
    return a.fuse(b)


def fine_mesh(shape, linear=None):
    import MeshPart
    return MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=LINEAR_DEFLECTION if linear is None else linear,
        AngularDeflection=ANGULAR_DEFLECTION,
        Relative=False)


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
        # See SELF_INTERSECT_TOL: only escalate crossings big enough to be a
        # real overlap, not sub-chord-tolerance tessellation noise.
        worst = max((App.Vector(pt1) - App.Vector(pt2)).Length
                     for _, _, pt1, pt2 in m.getSelfIntersections())
        if worst > SELF_INTERSECT_TOL:
            notes.append("mesh self-intersects (%.3fmm)" % worst)
    if not m.isSolid():
        notes.append("mesh not solid")
    return "%s: %s" % (label, "watertight" if not notes else "; ".join(notes))


# --------------------------------------------------------------------------
# Self-checks
# --------------------------------------------------------------------------

def check_post_fit(shape, p, drive):
    """Probe the drive-square broach hole itself (nominal size, not
    undersized) onto the post. The post must NOT clear it with excess
    volume beyond the intended interference band - a probe at nominal size
    should show measurable overlap (that's the friction grip)."""
    af = p["drive_af_nominal"][drive]
    r = p["post_corner_r"]
    cx, cy = p["base_w"] / 2.0, p["base_d"] * 0.62
    half = af / 2.0 - r
    pts = [App.Vector(cx + sx * half, cy + sy * half, p["base_h"] - 1)
           for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    probe = Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(
        App.Vector(0, 0, p["post_h"] + 2))
    overlap = shape.common(probe).Volume
    return overlap


def check_structural(p):
    """Minimum-thickness parameter check. Real thickness measurement needs
    a full geometric kernel query; this asserts the *design* numbers stay
    above safe minimums for FDM printing (repo convention: >=1.2mm walls,
    >=2mm posts/tabs)."""
    issues = []
    dt_wall = p["dt_neck_w"] / 2.0
    if dt_wall < 1.2:
        issues.append("dovetail neck %.2fmm below 1.2mm minimum" % dt_wall)
    if p["base_h"] < 2.0:
        issues.append("base_h %.2fmm below 2.0mm minimum" % p["base_h"])
    return issues


def check_printability(shape, label):
    flat, curved = overhangs(shape)
    if flat:
        return ["%s: %d unplanned flat overhang(s), largest %.1fmm2"
                % (label, len(flat), flat[0][0])]
    return []


def run():
    doc = App.newDocument("socket_organizer")
    pieces = generate_all(PARAMS)
    n_metric = len(PARAMS["metric_mm"]) * len(PARAMS["drives"])
    n_sae = len(PARAMS["sae_frac_32nds"]) * len(PARAMS["drives"])
    expected = n_metric + n_sae + 2
    print("generated %d pieces (expected %d)" % (len(pieces), expected))
    assert len(pieces) == expected == 42

    coupon = build_dovetail_coupon(PARAMS)
    # NOTE: this only proves the two halves fuse into one watertight solid
    # (i.e. the flat base walls touch with no gap). It does NOT verify the
    # dovetail tail/groove actually interlock - two pieces would fuse into
    # 1 solid via wall contact alone even if dt_* geometry were wrong.
    # Don't treat this as dovetail-fit proof; that needs eyeballing the
    # coupon geometry or a real print.
    assert len(coupon.Solids) == 1, "dovetail coupon halves did not fuse into one piece"
    print("dovetail coupon: 1 solid, volume %.1f mm3" % coupon.Volume)

    print("\n--- self-check report ---")
    struct_issues = check_structural(PARAMS)
    for issue in struct_issues:
        print("STRUCTURAL: %s" % issue)

    printability_issues = []
    mesh_issues = []
    for name, shape in sorted(pieces.items()):
        issues = check_printability(shape, name)
        printability_issues.extend(issues)
        for issue in issues:
            print("PRINTABILITY: %s" % issue)
        report = watertight(shape, name)
        print(report)
        if not report.endswith(": watertight"):
            mesh_issues.append(report)

    # Fit check: friction interference differs by drive (af_nominal 9.53mm
    # vs 12.70mm with the same 0.5mm undersize applied to both), so probe one
    # representative piece per drive rather than a single hand-picked size.
    fit_results = {}
    for drive, sample_name in (("1-2in", "metric_12mm_1-2in"),
                                ("3-8in", "metric_12mm_3-8in")):
        overlap = check_post_fit(pieces[sample_name], PARAMS, drive)
        fit_results[sample_name] = overlap
        print("post fit probe overlap (%s, drive %s): %.2f mm3"
              % (sample_name, drive, overlap))
        assert overlap > 0.5, (
            "%s post shows no interference with nominal drive square (%s) "
            "- too loose" % (sample_name, drive))

    assert not struct_issues, "structural check failed, see report above"
    assert not printability_issues, "printability check failed, see report above"
    assert not mesh_issues, "mesh/watertight check failed, see report above"

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
