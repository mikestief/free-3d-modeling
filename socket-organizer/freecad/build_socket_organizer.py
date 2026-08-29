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
import Mesh

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
# it is not something parameter-tuning the geometry can clear.
#
# IMPORTANT - what this tolerance does NOT catch: the zero-gap-tangent-fuse
# defect class (FUSE_EMBED reverted to 0 on make_post/make_dovetail_tail)
# measures only ~0.014mm worst self-intersection distance for a middle
# piece (~0.0044mm for an isolated post+base fuse alone) - inside this
# tolerance's range and overlapping the noise band above, not "at the
# scale of the feature involved (millimeters)" as an earlier version of
# this comment claimed. That claim was wrong: verified live, distance-based
# filtering cannot reliably separate that defect from ordinary tessellation
# noise, because their measured ranges overlap. 40 of 42 pieces (every
# middle piece) would silently pass watertight() with FUSE_EMBED=0; only
# the 2 caps still fail, and only via a different, tolerance-independent
# check (NON-MANIFOLD/not-solid) that happens to catch the caps' specific
# failure shape, not the middle pieces'.
#
# The zero-gap-fuse defect is instead caught directly, before any fuse or
# mesh is involved, by check_fuse_overlap() and check_cap_corner_solid()
# (see "Fuse-overlap self-checks" below) - exact OCC B-rep volume/topology
# facts, not a downstream mesh-tessellation proxy. This tolerance's only
# remaining job is filtering genuine tessellation noise (the curved-surface
# seams described above) out of the mesh self-intersection check so it
# doesn't cry wolf on every build; it is not a defense against zero-gap
# fuses of any kind.
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
    matching fix were added. NOTE: that mesh self-intersection distance is
    NOT a reliable way to catch this defect - reverting FUSE_EMBED to 0
    only pushes the measured self-intersection to ~0.0044mm (isolated
    post+base) / ~0.014mm (full middle piece), inside SELF_INTERSECT_TOL's
    noise-filtering range, so watertight() would silently pass it. The
    check that actually catches a zero-gap post/base fuse is
    check_fuse_overlap()'s direct base.common(post).Volume assertion (see
    "Fuse-overlap self-checks"), which needs no mesh at all."""
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
    that pushed the middle pieces further into self-intersection). As with
    make_post, mesh self-intersection distance alone cannot be trusted to
    catch a reverted FUSE_EMBED here - see check_fuse_overlap(), which
    asserts base.common(tail).Volume > 0 directly. The outward-facing tip
    position (what actually has to fit the neighbouring piece's groove) is
    untouched."""
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


def make_middle_piece_parts(p, drive, label_text):
    """(body_without_label, label_only) as two separate solids, in the
    exact same coordinate frame make_middle_piece fuses them in - i.e. no
    relative offset between the two. That's what makes the multi-color
    export work: a slicer that imports both files places them already
    aligned, so assigning each a different filament/color reproduces the
    single fused piece in two colors.

    This is the single source of truth for the base/post/dovetail
    construction; make_middle_piece is just this plus a fuse, so the
    fused single-color piece (used for every self-check, fit coupon, and
    the plain combined export) and the split multi-color pair can never
    drift apart."""
    body = make_base(p).fuse(make_post(p, drive))
    body = body.fuse(make_dovetail_tail(p))
    body = body.cut(make_dovetail_groove_cutter(p))
    label = emboss_label(p, label_text)
    return body, label


def make_middle_piece(p, drive, label_text):
    body, label = make_middle_piece_parts(p, drive, label_text)
    return body.fuse(label)


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

    Unlike the post/tail fuses, this defect happens to still get caught by
    watertight() at FUSE_EMBED=0 (the caps have no post/label fuses ahead
    of it to mask the resulting NON-MANIFOLD mesh) - but that is incidental
    to this cut's specific topology, not something to rely on in general;
    see SELF_INTERSECT_TOL's docstring. check_cap_corner_solid() below
    checks the same thing directly, via raw B-rep Solids count on the
    finished cap body, with no meshing involved.
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

def _middle_piece_specs(p):
    """Yields (name, drive, label_text) for all 40 middle pieces (not the
    2 caps, which have no label). Single source of truth for the
    name/drive/label mapping, shared by generate_all_parts and (through
    it) generate_all, so the two can't silently diverge on which pieces
    exist or what they're named."""
    for mm in p["metric_mm"]:
        for drive in p["drives"]:
            yield "metric_%dmm_%s" % (mm, drive), drive, str(mm)
    for n32 in p["sae_frac_32nds"]:
        label = sae_label(n32)
        key = sae_key(n32)
        for drive in p["drives"]:
            yield "sae_%s_%s" % (key, drive), drive, label


def generate_all_parts(p):
    """Returns {name: (body_without_label, label_only)} for the 40 middle
    pieces only - NOT the 2 caps, which never call emboss_label (see
    make_cap) and so have nothing to split. This is the basis for the
    multi-color _body/_label export pair."""
    return {name: make_middle_piece_parts(p, drive, label_text)
            for name, drive, label_text in _middle_piece_specs(p)}


def generate_all(p):
    """Returns {name: shape} for every middle piece and both caps - the
    fused single-solid pieces used for every self-check, the fit coupons,
    and the plain single-color export (all unchanged from before
    multi-color support was added).

    Built on top of generate_all_parts() rather than re-deriving each
    piece's base/post/dovetail/label geometry, so a caller that needs both
    the fused pieces and the split parts (see run()) can build the parts
    once and fuse them locally instead of constructing every piece's
    geometry twice."""
    parts = generate_all_parts(p)
    out = {name: body.fuse(label) for name, (body, label) in parts.items()}
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


# --------------------------------------------------------------------------
# Mesh/printability utilities
# --------------------------------------------------------------------------

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

    What this does NOT reliably catch: a zero-gap tangent fuse (e.g.
    FUSE_EMBED reverted to 0 on make_post/make_dovetail_tail). That defect's
    mesh self-intersection distance (~0.004-0.014mm, measured live) sits
    inside SELF_INTERSECT_TOL's tessellation-noise-filtering range for 40 of
    42 pieces (every middle piece) - only the 2 caps happen to still fail
    here, and via the tolerance-independent NON-MANIFOLD/not-solid checks,
    not the distance one. Mesh-tessellation signals are a downstream proxy
    for geometry, not a geometric fact, and this defect class sits right in
    the gap between "real crossing" and "tessellation noise" where that
    proxy can't tell the two apart. See check_fuse_overlap() and
    check_cap_corner_solid() for the direct, tessellation-independent checks
    that do catch it.
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


def check_fuse_overlap(base, part, label):
    """Direct geometric guarantee that `part` (a piece meant to fuse INTO
    `base`, relying on FUSE_EMBED for genuine overlap - e.g. make_post or
    make_dovetail_tail) actually has positive volumetric overlap with
    `base` BEFORE the fuse happens.

    This is deliberately NOT a mesh-tessellation proxy. base.common(part)
    is OCC's own exact B-rep boolean intersection - there is no meshing,
    no chord tolerance, nothing for tessellation noise to hide in or be
    confused with. A zero-gap tangent touch (FUSE_EMBED <= 0) has exactly
    zero shared volume; only a genuine embed does not. This is what
    catches the class of defect that watertight()'s SELF_INTERSECT_TOL
    cannot (see its docstring): the ~0.004-0.014mm self-intersection this
    defect produces sits inside that tolerance's noise-filtering range for
    every middle piece, so distance-based mesh filtering alone silently
    passes it."""
    overlap = base.common(part).Volume
    if overlap <= 0.0:
        return ("%s: no volumetric overlap before fuse (%.4f mm3) - "
                "zero-gap tangent fuse, not a real embed" % (label, overlap))
    return None


def check_cap_corner_solid(p, side):
    """Direct topological guarantee for make_cap's corner-rounding cut,
    which relies on FUSE_EMBED to keep the corner box strictly inside the
    round cylinder everywhere except at round_x (see make_cap's
    docstring). At FUSE_EMBED <= 0 the box's far edge sits exactly tangent
    to the cylinder at the dead-center latitude, and cutting the rounded
    corner sliver out of the cap body silently splits the whole cap into 2
    disconnected Solids there instead of raising an error - confirmed live:
    building the actual cap at FUSE_EMBED=0 gives Solids count 2 (both
    sides); at the real FUSE_EMBED=0.1 it is 1 for both.

    NOTE: corner.cut(round_cutter) alone (the intermediate rounding
    sliver) is NOT the right thing to check - it is naturally 2
    disconnected pieces (the box's near and far corners, split by the arc
    where the box is inside the cylinder) at every FUSE_EMBED value,
    including the correct 0.1, so its Solids count doesn't distinguish
    the defect. It's only once that sliver is cut out of the full,
    otherwise-connected cap body that a genuine embed keeps the body in
    one piece while a zero-gap tangent splits it - so this check builds
    the real cap and inspects its own Solids count, which is a direct
    fact from OCC's boolean kernel's own topology, no meshing, no
    distance tolerance, so there is nothing here for tessellation noise
    to be confused with."""
    cap = make_cap(p, side)
    n_solids = len(cap.Solids)
    if n_solids != 1:
        return ("cap_%s: %d disconnected solids (expected 1) - zero-gap "
                "tangent at the corner rounding cut" % (side, n_solids))
    return None


def check_fuse_overlaps(p):
    """Runs check_fuse_overlap()/check_cap_corner_solid() across every
    FUSE_EMBED-dependent boolean in the design. make_post and
    make_dovetail_tail's geometry does not depend on socket size (only
    drive, or nothing at all), so one check per drive plus one for the
    tail covers every one of the 40 middle pieces - they all build the
    same post/tail geometry that these checks exercise directly. Both caps
    are checked individually since 'start' and 'end' cut opposite edges."""
    issues = []
    base_shape = make_base(p)
    for drive in p["drives"]:
        issue = check_fuse_overlap(base_shape, make_post(p, drive),
                                    "post/base fuse (%s)" % drive)
        if issue:
            issues.append(issue)
    issue = check_fuse_overlap(base_shape, make_dovetail_tail(p),
                                "dovetail tail/base fuse")
    if issue:
        issues.append(issue)
    for side in ("start", "end"):
        issue = check_cap_corner_solid(p, side)
        if issue:
            issues.append(issue)
    return issues


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def export_all(shapes, out_dir, formats=("step", "stl", "3mf")):
    """Export every shape to the given formats (default STEP/STL/3MF),
    reusing a single scratch document for the whole batch (not one per shape
    - see the sibling whiteboard-stand/freecad/build_caddy.py's export_all,
    which avoids a temporary document per export for the same reason:
    creating/closing a FreeCAD document 45 times is needless churn and keeps
    this off the GUI thread).

    `formats` lets a caller skip formats it doesn't need (e.g. the
    _body/_label split export below only wants STEP+STL - the single-object
    3MF for a body or label alone is redundant now that
    export_multicolor_3mf() writes both as one combined multi-object 3MF).

    A failure exporting one shape (STEP write, recompute, or mesh write) is
    caught, logged, and does NOT abort the run - the loop still attempts
    every remaining shape so one bad piece can't hide the state of the other
    44. Returns the list of shape names that failed; the caller (run())
    decides whether that's fatal."""
    os.makedirs(out_dir, exist_ok=True)
    failed = []
    doc = App.newDocument("export_tmp")
    try:
        for name, shape in sorted(shapes.items()):
            try:
                obj = doc.addObject("Part::Feature", name)
                obj.Shape = shape
                doc.recompute()
                if "step" in formats:
                    Part.export([obj], os.path.join(out_dir, name + ".step"))
                if "stl" in formats or "3mf" in formats:
                    mesh = fine_mesh(shape)
                    if "stl" in formats:
                        mesh.write(os.path.join(out_dir, name + ".stl"))
                    if "3mf" in formats:
                        mesh.write(os.path.join(out_dir, name + ".3mf"))
            except Exception as exc:
                App.Console.PrintWarning(
                    "export failed for %r: %s\n" % (name, exc))
                failed.append(name)
            finally:
                if doc.getObject(name) is not None:
                    try:
                        doc.removeObject(name)
                    except Exception:
                        pass
    finally:
        App.closeDocument(doc.Name)
    return failed


def export_multicolor_3mf(parts, out_dir):
    """Export each middle piece's body and label as TWO OBJECTS IN ONE 3MF
    file (<name>_multicolor.3mf), so a multi-color slicer (Bambu
    Studio/OrcaSlicer/PrusaSlicer) imports a single file and shows the body
    and label as two independently-colorable objects at the same position -
    assign each a different filament/AMS slot. This supersedes the 3MF half
    of the _body/_label split export above for the multi-color use case (see
    export_all's `formats` param, used to skip .3mf there).

    Part.export()/Import.export() don't support .3mf in this FreeCAD build
    (raises "Unknown extension") - only Mesh.export() does, and it accepts a
    list of Mesh::Feature objects, writing each as its own <object>/<item>
    entry in the 3MF's 3D/3dmodel.model, at identity transform since world
    coordinates are already baked into the mesh vertices by fine_mesh().
    Verified by unzipping a sample output and inspecting the raw XML - don't
    re-verify by re-importing into FreeCAD, whose Mesh.insert() merges
    multi-object 3MF back into a single Mesh::Feature on read (a
    FreeCAD-reader-side simplification, not a sign the file is malformed).

    Reuses a single scratch document for the whole batch, same reasoning as
    export_all. A failure on one piece is caught, logged, and does not abort
    the batch. Returns the list of piece names that failed."""
    os.makedirs(out_dir, exist_ok=True)
    failed = []
    doc = App.newDocument("export_multicolor_tmp")
    try:
        for name, (body, label) in sorted(parts.items()):
            body_name = name + "_body_mc"
            label_name = name + "_label_mc"
            try:
                body_obj = doc.addObject("Mesh::Feature", body_name)
                body_obj.Mesh = fine_mesh(body)
                label_obj = doc.addObject("Mesh::Feature", label_name)
                label_obj.Mesh = fine_mesh(label)
                Mesh.export(
                    [body_obj, label_obj],
                    os.path.join(out_dir, name + "_multicolor.3mf"))
            except Exception as exc:
                App.Console.PrintWarning(
                    "multicolor export failed for %r: %s\n" % (name, exc))
                failed.append(name)
            finally:
                for obj_name in (body_name, label_name):
                    if doc.getObject(obj_name) is not None:
                        try:
                            doc.removeObject(obj_name)
                        except Exception:
                            pass
    finally:
        App.closeDocument(doc.Name)
    return failed


def check_multicolor_3mf_structure(path):
    """Opens a written `<name>_multicolor.3mf` as a zip and parses
    3D/3dmodel.model to confirm it actually contains 2 <object> resource
    entries and 2 <item> build entries - the one structural property the
    entire multi-color feature depends on (see export_multicolor_3mf's
    docstring: Mesh.export() is documented/assumed to write each
    Mesh::Feature passed to it as its own <object>/<item> pair, which is
    what makes a slicer show body and label as two independently-colorable
    objects instead of one merged mesh). That assumption was previously
    "verified by hand via zip/XML inspection" only, with no automated
    coverage - if a future FreeCAD version changed Mesh.export()'s
    multi-object behavior, every other assert in run() would still pass
    and the failure would only surface downstream in someone's slicer.
    This is the automated version of that same by-hand check, run against
    a real file on disk after export_multicolor_3mf() has written it.

    Returns (n_objects, n_items) rather than asserting itself, so the
    caller can report both counts before deciding whether to fail (same
    style as check_fuse_overlap/check_cap_corner_solid returning a
    description instead of asserting inline).

    Namespace-agnostic on purpose: 3MF's core namespace is
    "http://schemas.microsoft.com/3dmanufacturing/core/2015/02", but
    matching by local tag name (stripping any "{uri}" prefix ElementTree
    adds) is more robust than hardcoding that URI - it does not care
    whether a future writer changes the namespace URI or declares a
    default vs. prefixed namespace, only that the elements are still
    named <object> and <item> per the 3MF core spec.
    """
    import zipfile
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        with zf.open("3D/3dmodel.model") as f:
            root = ET.parse(f).getroot()

    def local_tag(el):
        tag = el.tag
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    n_objects = sum(1 for el in root.iter() if local_tag(el) == "object")
    n_items = sum(1 for el in root.iter() if local_tag(el) == "item")
    return n_objects, n_items


def run():
    doc = App.newDocument("socket_organizer")
    # Build the 40 middle pieces' (body, label) parts once, then derive the
    # fused single-solid pieces from them locally (same as generate_all(p)
    # does internally) instead of also calling generate_all_parts(p) again
    # later for the multi-color export - that would rebuild every middle
    # piece's base/post/dovetail/label geometry from scratch a second time.
    parts = generate_all_parts(PARAMS)
    pieces = {name: body.fuse(label) for name, (body, label) in parts.items()}
    pieces["cap_start"] = make_cap(PARAMS, "start")
    pieces["cap_end"] = make_cap(PARAMS, "end")
    n_metric = len(PARAMS["metric_mm"]) * len(PARAMS["drives"])
    n_sae = len(PARAMS["sae_frac_32nds"]) * len(PARAMS["drives"])
    expected = n_metric + n_sae + 2
    print("generated %d pieces (expected %d)" % (len(pieces), expected))
    assert len(pieces) == expected == 42

    print("\n--- multi-color part-reconstruction spot-check ---")
    # Confirms body_without_label U label_only reconstructs exactly the
    # same fused solid used for every self-check/coupon/export above -
    # i.e. splitting the piece into two files for multi-color printing
    # doesn't silently change the geometry that gets printed. Also reports
    # the intentional body/label embed overlap (see emboss_label's
    # docstring) so it's visible this is the expected small embed, not an
    # unbounded overlap.
    for name in ("metric_12mm_1-2in", "sae_5-16in_3-8in"):
        body, label = parts[name]
        reconstructed_vol = body.fuse(label).Volume
        fused_vol = pieces[name].Volume
        embed_overlap = body.common(label).Volume
        print("%s: fused=%.4f mm3, body+label refused=%.4f mm3 "
              "(diff %.6f), body/label embed overlap=%.4f mm3"
              % (name, fused_vol, reconstructed_vol,
                 abs(fused_vol - reconstructed_vol), embed_overlap))
        assert abs(fused_vol - reconstructed_vol) < 1e-6, (
            "%s: body/label split does not reconstruct the fused piece"
            % name)
        assert embed_overlap > 0.0, (
            "%s: body/label have no overlap - label would not attach"
            % name)

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

    print("\n--- fuse-overlap self-checks (direct B-rep, no meshing) ---")
    fuse_issues = check_fuse_overlaps(PARAMS)
    if fuse_issues:
        for issue in fuse_issues:
            print("FUSE-OVERLAP: %s" % issue)
    else:
        print("all FUSE_EMBED-dependent fuses have genuine volumetric "
              "overlap (post/base x%d drives, dovetail tail/base, "
              "cap corner cuts x2)" % len(PARAMS["drives"]))

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
    for drive, sample_name in (("1-2in", "metric_12mm_1-2in"),
                                ("3-8in", "metric_12mm_3-8in")):
        overlap = check_post_fit(pieces[sample_name], PARAMS, drive)
        print("post fit probe overlap (%s, drive %s): %.2f mm3"
              % (sample_name, drive, overlap))
        assert overlap > 0.5, (
            "%s post shows no interference with nominal drive square (%s) "
            "- too loose" % (sample_name, drive))

    assert not struct_issues, "structural check failed, see report above"
    assert not fuse_issues, "fuse-overlap check failed, see report above"
    assert not printability_issues, "printability check failed, see report above"
    assert not mesh_issues, "mesh/watertight check failed, see report above"

    out_dir = os.path.join(_script_dir(), "exports")
    export_failures = list(export_all(pieces, out_dir))

    # Multi-color export, STEP+STL half: body and label as separate files
    # per middle piece, IN ADDITION to the combined <name>.step/.stl/.3mf
    # above (not a replacement - single-color printers still use the
    # combined file). Both halves share the exact coordinate frame they
    # were fused in (see make_middle_piece_parts). .3mf is deliberately
    # excluded here (formats=("step", "stl")) - a single-object 3MF for
    # just the body or just the label is redundant now that
    # export_multicolor_3mf() below writes both as one combined
    # multi-object 3MF, which is what Bambu Studio's multi-color workflow
    # actually wants (one file, two objects at the same position) rather
    # than two separate files to import side by side.
    split_shapes = {}
    for name, (body, label) in parts.items():
        split_shapes[name + "_body"] = body
        split_shapes[name + "_label"] = label
    export_failures.extend(
        export_all(split_shapes, out_dir, formats=("step", "stl")))

    # Multi-color export, combined 3MF: body + label as two objects in one
    # <name>_multicolor.3mf per middle piece - see export_multicolor_3mf's
    # docstring for why this needs Mesh.export() rather than Part.export().
    multicolor_failures = export_multicolor_3mf(parts, out_dir)
    export_failures.extend(multicolor_failures)

    print("\n--- multi-color 3MF structure spot-check "
          "(2 objects / 2 items expected) ---")
    # Reuses the same two representative piece names as the
    # part-reconstruction spot-check above, rather than the full 40, for the
    # same reason check_post_fit only probes a couple of representative
    # pieces instead of all 42: the geometry that determines object/item
    # count here (Mesh.export() being handed a 2-element list) does not vary
    # by piece, only the file being real and on disk does. Skips a name if
    # its multicolor export already failed above - there is no file to open.
    multicolor_structure_issues = []
    for name in ("metric_12mm_1-2in", "sae_5-16in_3-8in"):
        if name in multicolor_failures:
            continue
        mc_path = os.path.join(out_dir, name + "_multicolor.3mf")
        n_objects, n_items = check_multicolor_3mf_structure(mc_path)
        print("%s_multicolor.3mf: %d object(s), %d item(s)"
              % (name, n_objects, n_items))
        if n_objects != 2 or n_items != 2:
            multicolor_structure_issues.append(
                "%s_multicolor.3mf: expected 2 objects/2 items, got "
                "%d objects/%d items" % (name, n_objects, n_items))
    # Folded into export_failures (asserted at the end, below, alongside
    # every other export outcome) rather than asserted here immediately -
    # same "let every shape be attempted first" reasoning as the rest of
    # this function's export handling.
    export_failures.extend(multicolor_structure_issues)

    coupons = {
        "post_coupon_3-8in": build_post_coupon(PARAMS, "3-8in"),
        "post_coupon_1-2in": build_post_coupon(PARAMS, "1-2in"),
        "dovetail_coupon": build_dovetail_coupon(PARAMS),
    }
    export_failures.extend(export_all(coupons, out_dir))

    print("\nExported %d pieces + %d body/label part-pairs + %d multicolor "
          "3MFs + %d coupons to %s"
          % (len(pieces), len(split_shapes) // 2, len(parts) - len(multicolor_failures),
             len(coupons), out_dir))

    # A partial export set must never silently look like success - but let
    # every shape in both batches be attempted first (export_all already
    # ran the full loop and collected every failure, not just the first)
    # before failing loudly here.
    assert not export_failures, (
        "export failed for %d shape(s): %s"
        % (len(export_failures), ", ".join(export_failures)))

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
