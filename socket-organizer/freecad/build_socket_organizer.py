# -*- coding: utf-8 -*-
"""
Socket organizer - parametric generator for FreeCAD.

Modular, interlinking socket holder. Exactly 5 piece types, size-agnostic:

  - template_3-8in / template_1-2in - a blank base+post template, one per
    drive (3/8in / 1/2in). The post's cross-section only depends on the
    drive square, NOT which socket size sits on it - every socket of a
    given drive shares the same square drive-hole - so one blank template
    per drive already physically fits every socket size in that drive.
    No baked text anywhere. Has a small dovetail SLOT on its sloped front
    wall for a nameplate to slide into (see below), plus the usual
    piece-to-piece dovetail tail/groove for joining templates and caps
    into a row.
  - cap_start / cap_end - unchanged row-end pieces, still blank.
  - nameplate_template - a single blank plaque with a dovetail TAIL on its
    back that slides into a template's slot. Print as many copies as you
    like and label each one with your slicer's own text tool (e.g. Bambu
    Studio) - this generator no longer bakes any size text into geometry
    at all. See nameplate_dt_neck_w/tip_w/depth/clearance below for the
    slot/tail dimensions - TUNE VIA NAMEPLATE FIT COUPON.

Pieces snap together with a vertical dovetail (press down to seat, lift
straight up to remove) so any single piece can be pulled without
disturbing its neighbours.

Running it
----------
Headless (no GUI needed)::

    freecadcmd build_socket_organizer.py

Outputs land in ./exports as STEP, STL and 3MF.

Print the fit coupons (post_coupon_3-8in.stl, post_coupon_1-2in.stl,
dovetail_coupon.stl, nameplate_coupon.stl) before committing to a full
print run.

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
    # base_w/base_d were 26.0/32.0 (aspect ratio ~0.8125), sized against an
    # assumed 19mm/3-4in socket OD that was never actually measured against
    # real hardware. Grown to 43.0/53.0 (ratio 0.8113, same aspect within
    # 0.2%) after the user measured real socket outer diameters with
    # calipers: 22mm -> ~30mm OD, 25mm -> ~35mm OD (see
    # SOCKET_OD_POINTS_MM / estimated_socket_od_mm below). Post center sits
    # at (base_w/2, base_d*0.62), so the tightest edges are left/right
    # (distance base_w/2) and back (distance base_d*0.38, since the post is
    # offset toward the front). At 43.0x53.0, a worst-case 35mm-diameter
    # socket (17.5mm radius) clears: left/right margin 4.00mm, back margin
    # 2.64mm, front margin 15.36mm (all verified live via real B-rep
    # booleans - see check_socket_od_clearance() and its docstring for the
    # measured numbers, including the 1in SAE size's slightly larger
    # estimated OD which is actually the true worst case, not 25mm metric).
    # No collision with the dovetail tail/groove (both 0.0 mm3 overlap,
    # verified live) or with the base solid itself (post sits at
    # z>=base_h, above the sloped wall entirely).
    "base_w":         43.0,   # left-right, this is the row-direction pitch
    "base_d":         53.0,   # front-to-back depth
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

    # --- piece-to-piece dovetail (vertical snap: open top, closed bottom) --
    "dt_neck_w":       4.0,   # width where the tail meets the base
    "dt_tip_w":        6.0,   # width at the tail's outer edge (wider = hooks)
    "dt_depth":        4.0,   # how far the tail protrudes / groove cuts in
    "dt_clearance":    0.15,  # per-side clearance, groove vs tail. TUNE VIA
                               # DOVETAIL FIT COUPON before trusting this.

    # --- nameplate dovetail slot/tail (light-duty wall attachment) ----------
    # New geometry, no prior fit history at all - unlike dt_clearance/
    # post_af_undersize above (which had years of this file's own git
    # history plus real prints to anchor them), these four are a first
    # engineering guess only. Scaled down from the piece-to-piece
    # dovetail's 4.0/6.0/4.0mm (neck/tip/depth) because the nameplate is a
    # light decorative/informational attachment (holds only its own small
    # mass, no load-bearing role), not a structural joint between two
    # printed pieces - roughly 3/4 scale keeps the neck wall
    # (nameplate_dt_neck_w/2 = 1.5mm) safely above the 1.2mm FDM
    # minimum-wall floor this file already uses elsewhere (see
    # check_structural), while still being visibly smaller/lighter than
    # the piece connector so it doesn't look oversized against a plaque
    # this thin (nameplate_t=2.0mm). dt_clearance's own value (0.15mm) is
    # reused as-is for the starting clearance rather than guessed fresh -
    # it's a real measured FDM-printer clearance already proven to work
    # for a vertical dovetail on this same printer/process, and the
    # nameplate slot is the same "press down to seat, lift straight up"
    # mechanism at smaller scale, not a different mechanism that would
    # need its own independent clearance derivation.
    # TUNE VIA NAMEPLATE FIT COUPON before trusting any of these four.
    "nameplate_dt_neck_w":   3.0,
    "nameplate_dt_tip_w":    4.5,
    "nameplate_dt_depth":    2.0,
    "nameplate_dt_clearance": 0.15,

    # --- nameplate plaque -----------------------------------------------------
    # One fixed size (not variable per text length - text is no longer this
    # generator's concern at all, see module docstring). Sized to comfortably
    # fit the old label zone: the embossed labels this replaces used to sit
    # on the wall in a Z band of roughly [3.3, 9.1] (see the removed
    # label_h/label_z params' git history) - nameplate_h=6.0 plus
    # nameplate_zone_z=1.0 lands the plaque's own Z span in a similar part
    # of the wall (see check_nameplate_fit's live-measured bbox for the
    # exact numbers with this geometry's actual rotation math, which is
    # more involved than the old flat label - see make_nameplate_slot_cutter's
    # docstring). nameplate_w=22.0 leaves >10mm clearance to base_w=43.0 on
    # each side - comfortably inside the base footprint with room to spare
    # for the slicer's own text at a readable size. nameplate_t=2.0mm clears
    # the 1.2mm FDM minimum-wall floor with margin while leaving real depth
    # for the slicer's engraved/embossed text to actually read.
    # TUNE VIA NAMEPLATE FIT COUPON (exact proportions, not the interlock
    # mechanism itself, are the open question here).
    "nameplate_w":           22.0,
    "nameplate_h":            6.0,
    "nameplate_t":            2.0,
    # Extra slide-in headroom above the plaque's own height so the groove
    # is genuinely "open at the top" (room to start the tail above its
    # resting position and slide it down to seat) rather than exactly
    # matching the tail's own height, which would leave no slide travel at
    # all.
    "nameplate_slot_open_h":  2.0,
    # World-Z anchor for the BOTTOM of the slot/plaque (the "closed bottom"
    # stop the tail rests against) - see make_nameplate_slot_cutter's
    # docstring for why this single anchor Z, run through the same
    # rotate-then-translate math emboss_label used to use for text, lands
    # the slot/tail flush on the sloped wall for their WHOLE height, not
    # just at this one point.
    "nameplate_zone_z":       1.0,

    # --- cap (start/end piece) ----------------------------------------------
    # Was 8.0, set when base_d was 32.0 (ratio 8/32 = 0.25 of depth - see
    # make_cap's docstring: the round cylinder only spans 2*r of base_d
    # centered on the dovetail's Y offset, so material outside that band is
    # cut flush instead of rounded, making 2*r/base_d the fraction of the
    # piece's depth that actually reads as a rounded nose rather than a
    # flat notch). Never revisited when base_d grew to 53.0 (see base_w/
    # base_d comment above) - at the stale 8.0 that ratio silently dropped
    # to 2*8/53 = 0.302 (down from 0.50 at the original 8/32), which is why
    # the cap's rounded end looked like a small isolated notch/bump instead
    # of the intended graceful rounded closure (confirmed live: a small
    # cylindrical face patch, not a nose - and matched a user screenshot).
    # Rescaled to preserve the original ratio: 8.0 / 32.0 * 53.0 = 13.25,
    # restoring 2*r/base_d back to exactly 0.50. Same "TUNE"-style trap as
    # dt_clearance/post_af_undersize above - if base_d changes again,
    # recompute this as cap_round_r/base_d = 0.25 rather than leaving the
    # absolute mm value behind.
    "cap_round_r":     13.25,  # radius of the closed rounded end

    # --- drives -----------------------------------------------------------
    "drives":          ["3-8in", "1-2in"],

    # --- printer --------------------------------------------------------------
    "bed_x": 256.0, "bed_y": 256.0,
}

LINEAR_DEFLECTION = 0.02
ANGULAR_DEFLECTION = math.radians(5.0)

# How far to push a piece that gets FUSED (not cut) onto another, so the two
# solids have genuine volumetric overlap instead of a zero-gap tangent touch.
# See make_post's docstring for why this matters - OCC's fuse silently
# produces self-intersecting/non-manifold results at exact tangency,
# invisible to isValid()/Solids-count checks. Also used for the nameplate's
# own two FUSE_EMBED-dependent joins (tail-to-plaque, plaque-to-template) -
# see make_nameplate / _nameplate_plaque_shape.
FUSE_EMBED = 0.1

# Tolerance for treating a mesh "self-intersection" as real rather than
# tessellation noise. MeshPart's tessellation of a curved surface fused/
# tangent to a flat one - specifically the post's chamfer-on-fillet top
# corners (post_top_chamfer meeting post_corner_r's tiny fillet arcs)
# fused onto the base - reliably reports sub-chord-tolerance crossing
# segments: measured live on the current templates at 0.004mm, well
# inside LINEAR_DEFLECTION itself (0.02mm), i.e. noise from the
# tessellation's own approximation error at that seam, not a real
# overlap. Confirmed by removing this tolerance entirely (report every
# self-intersection unconditionally): both templates then fail watertight
# on exactly this 0.004mm post-chamfer noise, reproducing regardless of
# what other geometry (labels, dovetail slots) exists on the piece -
# this is a real, independent artifact of the post geometry itself, not
# something parameter-tuning elsewhere can clear.
#
# IMPORTANT - what this tolerance does NOT catch: a zero-gap-tangent-fuse
# defect (FUSE_EMBED reverted to 0 on make_post/make_dovetail_tail/the
# nameplate joins) measures self-intersection distances that can fall in
# this same noise-scale range, so distance-based mesh filtering alone
# cannot reliably separate the two defect classes. That defect is instead
# caught directly, before any mesh is involved, by check_fuse_overlap()
# and check_cap_corner_solid() (see "Self-checks" below) - exact OCC
# B-rep volume/topology facts, not a downstream mesh-tessellation proxy.
# This tolerance's only job is filtering the post-chamfer tessellation
# noise described above out of watertight()'s mesh self-intersection
# check so it doesn't cry wolf on every build.
SELF_INTERSECT_TOL = 2 * LINEAR_DEFLECTION

# Two real hand-measured (calipers) socket outer-diameter data points,
# supplied by the user, anchoring the base footprint against actual socket
# hardware rather than an assumption: a 22mm socket measures ~30mm OD; a
# 25mm socket measures ~35mm OD. These are socket BODY widths, not the
# drive-square size.
#
# estimated_socket_od_mm() linearly interpolates/extrapolates between these
# two points to estimate OD for any nominal size (mm). check_socket_od_
# clearance() uses it for the one real worst-case size still relevant now
# that the piece set is size-agnostic templates rather than a per-size
# table: converting 1in SAE to its metric-equivalent bore (25.4mm) and
# running it through this line predicts an OD of ~35.67mm, slightly LARGER
# than 25mm metric's own measured 35mm point - so 1in SAE, not 25mm metric,
# is the true worst case a template's fixed footprint has to clear.
SOCKET_OD_POINTS_MM = [(22.0, 30.0), (25.0, 35.0)]

# Minimum acceptable clearance (mm) between the estimated widest socket body
# and the base footprint's own outer edge, in any of the four directions
# (left/right/front/back from the post center). See PARAMS's base_w/base_d
# comment for the live-measured numbers at base_w=43.0/base_d=53.0: the
# tightest real margin measured (via check_socket_od_clearance's own real
# B-rep booleans) was ~2.3mm (the 1in SAE size's back-edge margin - narrower
# than the 25mm metric size's 2.64mm). 1.5mm sits below that with real, if
# not huge, margin (~35%).
#
# Unlike COUNTER_WIDTH_FLOOR used to be (grounded in an independent physical
# fact - nozzle diameter), this floor has no such external anchor:
# SOCKET_OD_POINTS_MM is only two measured points, and estimated_socket_
# od_mm() is a linear guess between/near them, not a physical law. 1.5mm is
# chosen to absorb ordinary FDM dimensional tolerance (typically a few
# tenths of a mm) many times over, plus a real buffer for that OD-model
# uncertainty.
OD_CLEARANCE_FLOOR = 1.5


def estimated_socket_od_mm(nominal_mm):
    """Linear estimate of a socket's outer diameter (mm) from its nominal
    bore size (mm), anchored on the two real measured points in
    SOCKET_OD_POINTS_MM. Not a physical model - sockets aren't actually
    linear in OD-vs-bore across their whole range - but a reasonable
    estimate near the two measured points (22mm, 25mm), which is exactly
    what check_socket_od_clearance() needs it for: confirming the one real
    worst-case size (1in SAE, see that function's docstring) clears the
    base footprint.

    This is NOT a trustworthy estimate far below the anchors: extrapolated
    down to small nominal sizes, the line goes unphysical - it predicts an
    OD *smaller than the bore itself*, which is impossible. Not a concern
    for check_socket_od_clearance(), which only ever evaluates it near the
    anchor range (22-25.4mm)."""
    (x0, y0), (x1, y1) = SOCKET_OD_POINTS_MM
    slope = (y1 - y0) / (x1 - x0)
    return y0 + slope * (nominal_mm - x0)


def _script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def box(l, w, h, x, y, z):
    return Part.makeBox(l, w, h, App.Vector(x, y, z))


# --------------------------------------------------------------------------
# Geometry - base and post
# --------------------------------------------------------------------------

def wall_y_at_z(p, z):
    """Y position of the sloped front wall's surface at height z.

    Single source of truth for the wall's geometry: make_base's wedge cut
    and the nameplate slot/tail placement (make_nameplate_slot_cutter,
    make_nameplate_tail, _nameplate_plaque_shape) all derive from this same
    line so they can't silently drift apart."""
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
    with the base's top face over the post's whole footprint) - OCC's
    fuse() silently produces self-intersecting/non-manifold geometry at
    exact tangency, invisible to isValid()/Solids-count checks. The check
    that actually catches a zero-gap post/base fuse is check_fuse_
    overlap()'s direct base.common(post).Volume assertion (see
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
# Geometry - vertical piece-to-piece dovetail (open top, closed bottom)
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
    into the base's own solid before make_template/make_cap fuse this onto
    the base, so the fuse has genuine volumetric overlap rather than a
    zero-gap tangent touch at x=base_w (see make_post's docstring). As with
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
# Geometry - nameplate dovetail slot/tail (light-duty, on the sloped wall)
# --------------------------------------------------------------------------

def _nameplate_dt_profile(p, outward, clearance=0.0, root_embed=0.0):
    """2D dovetail profile in the LOCAL X-Z plane (X = width across the
    wall, unaffected by the X-axis rotation applied below; Z = protrusion
    into/out of the wall). This is the same local-frame convention the
    removed emboss_label() used to use for embossed text - local X = the
    reading/width direction (untouched by an X-axis rotation), local Z =
    the "thickness"/protrusion axis, which after rotation becomes the
    wall's own outward-facing normal.

    The caller extrudes the returned face along local Y (the "vertical,
    press-down-to-seat" slide axis, before rotation) and then applies the
    SAME rotate-then-translate as make_nameplate_slot_cutter / make_
    nameplate_tail / _nameplate_plaque_shape, so every one of those lands
    on the sloped wall consistently - see make_nameplate_slot_cutter's
    docstring for the algebra proving that rotation puts local Z=0 exactly
    on the wall's real surface for the WHOLE local-Y extent of the shape,
    not just at one anchor point (the same proof the old emboss_label
    docstring gave for text)."""
    neck = p["nameplate_dt_neck_w"] / 2.0 + clearance
    tip = p["nameplate_dt_tip_w"] / 2.0 + clearance
    depth = p["nameplate_dt_depth"]
    sign = 1 if outward else -1
    root_z = -sign * root_embed
    pts = [
        App.Vector(-neck, 0, root_z),
        App.Vector(-tip, 0, sign * depth),
        App.Vector(tip, 0, sign * depth),
        App.Vector(neck, 0, root_z),
        App.Vector(-neck, 0, root_z),
    ]
    return Part.Face(Part.makePolygon(pts))


def _place_on_wall(p, solid, z_anchor, x_offset=0.0):
    """Rotate+translate a solid built in the "local wall frame" (local Y =
    up the slope, local Z = wall outward normal, local X = world X
    unchanged) into world space, landing local Y=0 / local Z=0 at world
    Z=z_anchor on the wall surface (world Y = wall_y_at_z(p, z_anchor)),
    additionally shifted by `x_offset` in X (e.g. base_w/2 to center a
    shape built around local X=0 on the wall).

    Proof this lands local Z=0 on the real wall surface for EVERY local Y
    (not just Y=0): rotating point (x, y, 0) by angle theta=(90-slope)
    about the X axis gives world-frame (dY, dZ) = (y*sin(slope),
    y*cos(slope)) relative to the rotation center, i.e. before the
    z_anchor translate. After translating by (x_offset, wall_y_at_z(
    z_anchor), z_anchor):

        world Z = z_anchor + y*cos(slope)
        world Y = wall_y_at_z(z_anchor) + y*sin(slope)
                = z_anchor*tan(slope) + y*sin(slope)

    and wall_y_at_z(world Z) = (z_anchor + y*cos(slope)) * tan(slope)
                              = z_anchor*tan(slope) + y*sin(slope)

    which is exactly world Y above, for every y - so the whole local
    Z=0 face sits flush on the sloped wall regardless of how tall the
    shape is along local Y (x_offset is a pure X translate, untouched by
    an X-axis rotation, so it doesn't affect this proof). This is the
    same trick (and the same proof) the removed emboss_label() used to
    place embossed text flush on this wall; make_nameplate_slot_cutter /
    make_nameplate_tail / _nameplate_plaque_shape all share this one
    helper so they can't drift apart."""
    solid = solid.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0),
                          90 - p["front_slope_deg"])
    y_wall = wall_y_at_z(p, z_anchor)
    return solid.translate(App.Vector(x_offset, y_wall, z_anchor))


def make_nameplate_slot_cutter(p):
    """Dovetail-GROOVE cutter for a template's sloped front wall - vertical
    (open at the top, i.e. the +local-Y/up-the-slope end; closed at the
    bottom, local Y=0, where nameplate_zone_z anchors the resting stop) so
    the nameplate can be pressed down along the wall's own slope to seat
    and lifted back up to remove - the same press-down mechanic as the
    piece-to-piece dovetail, just constrained to the sloped surface instead
    of true vertical, since that is what actually matches this wall's own
    geometry (see _place_on_wall's docstring).

    outward=False (tip at local Z = -nameplate_dt_depth) because local -Z
    is the direction INTO the template's own solid (local +Z maps to the
    wall's outward normal - see _nameplate_dt_profile) - the cavity must
    carve into real material, not out into the air in front of the wall.
    nameplate_dt_clearance only widens the neck/tip (lateral clearance);
    depth is unclearanced, matching the piece-to-piece dovetail's own
    dt_clearance convention (clearance is per-side lateral, not extra
    depth).

    Positioned where the old embossed label used to sit: centered on the
    wall in X (base_w/2) and anchored at nameplate_zone_z in Z (see
    PARAMS's comment on that value).

    The cutter's local-Y extent is deliberately taller than nameplate_h +
    nameplate_slot_open_h (the plaque's actual assembled span plus its
    intended slide-in allowance): if the cutter stopped exactly there, its
    own far (local Y=total_h) end-cap face would become a real exposed
    "ceiling" on the cut template - a blind-hole top, not a genuinely open
    one - with a world normal (0, -sin(slope), -cos(slope)), i.e.
    substantially DOWNWARD-facing, a true unsupported-bridge overhang.
    Confirmed live: the first version of this function (extruding exactly
    to nameplate_h + nameplate_slot_open_h) produced exactly this - an
    8.1mm2 flat overhang on both templates, caught by check_printability,
    at the cavity's own top end (zmin~7.83mm, matching that end's
    location). Overshooting the top well past where the wall's own
    material ends (base_h) removes that ceiling entirely - the excess cut
    falls outside the base block (no material there to cut, a no-op),
    exactly like the piece-to-piece groove cutter's own "+2" overshoot
    past base_h (see make_dovetail_groove_cutter). The bottom end
    (local Y=0) is NOT overshot - that is the deliberate closed-bottom
    stop the tail rests against, and must stay exactly at nameplate_zone_z
    for the mechanism to work.

    to_clear_wall's derivation (must genuinely clear base_h for ANY
    front_slope_deg, not just today's 20 - a first version of this formula
    only accounted for the up-slope/local-Y recession and silently
    reintroduced the exact ceiling defect above as slope grew past ~68deg;
    see the derivation below for why, and the live slope-sweep results
    further down for what was actually confirmed clean vs. not):

    _place_on_wall's own docstring proves world Z = z_anchor + y*cos(slope)
    for a LOCAL-Z=0 point at local-Y=y. That's the proof this function used
    to lean on - but the cutter's far end-cap is NOT confined to local Z=0:
    it spans the full profile cross-section, local Z in [-depth, 0] (depth
    = nameplate_dt_depth, the cavity's cut depth into the wall - see
    _nameplate_dt_profile's outward=False/sign=-1 convention). Extending
    _place_on_wall's rotation to a general local point (x, y, z) (rotating
    by theta=90-slope about the X axis, same rotation matrix, just with the
    z-term restored instead of dropped at z=0) gives:

        world Z = z_anchor + y*cos(slope) + z*sin(slope)

    For the end-cap at local Y=total_h, the WORST (smallest) world Z over
    the cap's own local-Z range [-depth, 0] is at z=-depth (the cavity's
    deepest point, since sin(slope) > 0 for any slope in (0, 90)):

        worst_world_Z = nameplate_zone_z + total_h*cos(slope)
                        - depth*sin(slope)

    That -depth*sin(slope) term is exactly the "additional recession...
    via the local-Z-to-world-Z term" the old formula dropped by only ever
    evaluating the proof at z=0: the cavity's own depth pulls its deepest
    corner further BACK in world Y *and* further DOWN in world Z as slope
    grows, on top of the up-slope-only recession already accounted for.
    Solving worst_world_Z >= base_h + margin for total_h (margin is a
    genuine WORLD-Z buffer past base_h, not a local-Y one):

        total_h >= (base_h - nameplate_zone_z + margin) / cos(slope)
                   + depth * tan(slope)

    which is what to_clear_wall computes below (margin=5.0mm, matching the
    prior formula's own buffer at slope=0 exactly - plug slope=0 into both
    sides above and the depth*tan(0)=0 term vanishes, reducing to the
    original (base_h - nameplate_zone_z) + 5.0 - so this is a strict
    generalization, not a different formula that happens to agree at one
    point). Verified live: at today's front_slope_deg=20/nameplate_dt_
    depth=2.0/base_h=10.0, this adds ~1mm to to_clear_wall over the old
    formula (real margin at 20deg was already ~4mm, not a live bug) and
    total_h is unchanged in every OTHER respect - same cavity cross-
    section, same closed-bottom anchor - so check_nameplate_fit's
    containment/collision/connectivity/footprint numbers are unaffected.

    What was actually live-verified, isolating the delta overhang caused
    specifically by this cutter (baseline template body vs. the same body
    with this cutter applied, same technique used to originally find the
    bug): the corrected formula introduces ZERO new flat overhangs across
    front_slope_deg in {5, 20, 45, 60} deg at base_h=10 (also re-checked at
    base_h=5 and base_h=20, front_slope_deg=20) - this is the range this
    fix is actually asserting "genuinely slope-general" for.

    IMPORTANT caveat found while verifying past that range, at base_h=10:
    starting around front_slope_deg~=62deg, a DIFFERENT, pre-existing new
    overhang appears, and it is NOT the ceiling defect this function
    exists to prevent - direct B-rep boolean checks
    (cavity.common(make_post(p, drive)).Volume) confirm the cavity itself
    now has real positive volumetric overlap with the drive post, which
    shares this cavity's own X-center (both sit at base_w/2 - see make_
    post's cx). At steep slope the local-Y overshoot this function
    performs necessarily travels a long way in world Y as well as world Z
    (see _place_on_wall's rotation - the same y*sin(slope) term that
    grows total_h's world-Z contribution also grows its world-Y one), and
    past ~62deg (this base_h/post placement) that world-Y travel reaches
    into the post's own footprint, carving a real notch out of it.

    This is NOT fixable by changing to_clear_wall's magnitude: confirmed
    live that even the bare mathematical MINIMUM total_h (margin=0, i.e.
    worst_world_Z landing exactly on base_h with no buffer at all) already
    overlaps the post at front_slope_deg=70/base_h=10 (21.3mm3) and
    front_slope_deg=80/base_h=5 (25.9mm3) - the two edge cases originally
    suspected of reproducing the ceiling bug. So while this fix does
    correctly eliminate the ceiling defect at those two slopes (the
    world-Z-buffer math is sound at any slope - see the derivation above),
    it does NOT achieve a fully clean build there, because a SEPARATE,
    orthogonal constraint (wall slope vs. post placement, not wall slope
    vs. base_h) takes over as the binding one. Fixing that would mean
    changing the cutter's SHAPE (e.g. a world-Z-aligned "chimney" for the
    overshoot instead of continuing straight along local Y) rather than
    this scalar overshoot amount, which is out of scope here - flagged as
    a separate follow-up. Note the base design itself (no nameplate
    feature at all) already produces its own unrelated flat overhangs by
    front_slope_deg=75-85deg (from the wedge-cut/post interaction), so
    those extreme slopes are already outside this design's viable
    envelope independent of this cutter.

    Bottom line: this fix's valid, live-verified range is roughly
    front_slope_deg up to ~60deg (well past today's 20deg) rather than
    "any slope whatsoever" - genuinely slope-general within that range,
    with the >~62deg regime gated by the separate post-placement
    constraint described above, not by this function's own math."""
    face = _nameplate_dt_profile(p, outward=False,
                                  clearance=p["nameplate_dt_clearance"])
    open_h = p["nameplate_h"] + p["nameplate_slot_open_h"]
    # Local-Y distance from nameplate_zone_z needed for the cutter's WORST
    # end-cap corner (local Z=-nameplate_dt_depth, the cavity's deepest
    # point, not just local Z=0) to clear base_h in world Z by a genuine
    # 5mm buffer, for any front_slope_deg - see docstring above for the
    # full derivation of why the depth*tan(slope) term is required.
    slope_rad = math.radians(p["front_slope_deg"])
    depth = p["nameplate_dt_depth"]
    margin = 5.0
    to_clear_wall = ((p["base_h"] - p["nameplate_zone_z"] + margin)
                      / math.cos(slope_rad) + depth * math.tan(slope_rad))
    total_h = max(open_h, to_clear_wall)
    solid = face.extrude(App.Vector(0, total_h, 0))
    return _place_on_wall(p, solid, p["nameplate_zone_z"],
                           x_offset=p["base_w"] / 2.0)


def _nameplate_tail_local(p):
    """The nameplate's dovetail tail in the native, unrotated local frame:
    X centered on 0 (width across the plaque), Y in [0, nameplate_h] (the
    plaque's own height/slide-axis extent), Z protruding from the
    plaque's back (root near Z=+FUSE_EMBED, tip at Z=-nameplate_dt_depth -
    see _nameplate_dt_profile). Single source of truth for the tail's
    shape - make_nameplate_tail (rotated onto the wall, for fit-checking
    against the template) and make_nameplate (the exported, print-
    oriented piece) both build on this exact same geometry, just placed
    differently in space.

    root_embed=FUSE_EMBED pushes the tail's root FUSE_EMBED past local
    Z=0 into where the plaque box's own solid will be (_nameplate_plaque_
    local spans local Z in [-FUSE_EMBED, nameplate_t]), for a genuine
    tail/plaque fuse overlap - the same zero-gap-tangent-fuse concern as
    everywhere else in this file. The tip (what actually has to fit
    inside the template's slot cavity) is untouched by root_embed - only
    the root moves."""
    face = _nameplate_dt_profile(p, outward=False, root_embed=FUSE_EMBED)
    return face.extrude(App.Vector(0, p["nameplate_h"], 0))


def make_nameplate_tail(p):
    """The nameplate's dovetail tail, ASSEMBLED (rotated/translated onto
    the sloped wall, matching make_nameplate_slot_cutter's own placement)
    - what check_nameplate_fit measures containment/collision for, and
    what check_fuse_overlaps fuses against _nameplate_plaque_shape(p) to
    confirm the tail/plaque join. This is NOT the orientation that gets
    exported - see make_nameplate's docstring for why the exported piece
    uses a different, print-friendly placement of this same design
    geometry (_nameplate_tail_local)."""
    return _place_on_wall(p, _nameplate_tail_local(p),
                           p["nameplate_zone_z"], x_offset=p["base_w"] / 2.0)


def _nameplate_plaque_local(p):
    """The flat blank plaque box (no tail) in the native, unrotated local
    frame - see _nameplate_tail_local's docstring for the shared X/Y/Z
    convention. Spans local Z in [-FUSE_EMBED, nameplate_t] rather than
    [0, nameplate_t] - the same FUSE_EMBED push local Z=0 gets everywhere
    else in this file (see make_post's docstring) - so the plaque's own
    back face has genuine volumetric overlap with the template's solid
    wall material OUTSIDE the narrow dovetail cavity (the cavity only
    removes a few mm2 in the middle of the plaque's much larger footprint
    - see make_nameplate_slot_cutter) when a nameplate is fused onto a
    slot-cut template in build_nameplate_coupon."""
    w, h, t = p["nameplate_w"], p["nameplate_h"], p["nameplate_t"]
    return box(w, h, t + FUSE_EMBED, -w / 2.0, 0, -FUSE_EMBED)


def _nameplate_plaque_shape(p):
    """The plaque box, ASSEMBLED (rotated/translated onto the sloped
    wall) - what make_nameplate_tail(p) fuses against for the plaque/tail
    fuse self-check (check_fuse_overlaps), and what a template's own
    solid gets fused against (via _nameplate_assembled) in build_
    nameplate_coupon. NOT the exported orientation - see make_nameplate."""
    return _place_on_wall(p, _nameplate_plaque_local(p),
                           p["nameplate_zone_z"], x_offset=p["base_w"] / 2.0)


def _nameplate_assembled(p):
    """The complete nameplate (plaque + tail), ASSEMBLED at its real
    mounted position/orientation against a template's front wall - used
    by build_nameplate_coupon and check_nameplate_fit's connectivity/
    footprint checks. This is NOT what gets exported as nameplate_
    template - see make_nameplate's docstring for why the export uses a
    different, print-friendly orientation of this exact same design
    geometry."""
    return _nameplate_plaque_shape(p).fuse(make_nameplate_tail(p))


def make_nameplate(p):
    """Blank plaque, front face genuinely flat/blank - the user adds their
    own text with their slicer's text tool after importing (see module
    docstring). Has a dovetail TAIL on its back matching make_nameplate_
    slot_cutter's groove - built from the exact same local tail/plaque
    geometry as the ASSEMBLED nameplate used for fit-checking (see
    _nameplate_assembled), just placed differently here.

    Unlike every OTHER piece/coupon in this file (which export in their
    real assembled orientation - templates stand upright as printed,
    build_dovetail_coupon exports two upright fused pieces, not laid
    down), the nameplate's real assembled orientation is tilted ~70
    degrees off vertical (matching the wall's 20-degree-off-vertical
    slope) with a thin (nameplate_t=2mm) cross-section - a genuinely bad
    print orientation: the thin dimension ends up spread mostly across
    world Y rather than stacked in Z, and the plaque's own flat back is
    suspended in mid-air above the bed except where the tail happens to
    touch it. Confirmed live: exporting the assembled orientation
    directly produced a real ~45mm2 unplanned flat overhang (genuine
    unsupported bridging), caught by check_printability on the first
    attempt at this geometry.

    So the EXPORTED piece instead uses the native, unrotated local frame
    (_nameplate_tail_local / _nameplate_plaque_local), then flips 180
    degrees about X so the plaque's flat back rests on the bed (the
    piece's own global Z minimum) with the tail pointing straight up as a
    short raised nub - an ordinary, well-supported FDM shape at this
    scale. This only changes the piece's placement/orientation in space;
    the design geometry itself (tail/plaque dimensions and their
    relationship to each other) is identical to what check_nameplate_fit
    and build_nameplate_coupon verify against the template."""
    design = _nameplate_plaque_local(p).fuse(_nameplate_tail_local(p))
    flipped = design.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 180)
    bb = flipped.BoundBox
    return flipped.translate(App.Vector(0, -bb.YMin, -bb.ZMin))


def make_template(p, drive):
    """Blank template piece: base + drive-specific post + the unchanged
    piece-to-piece dovetail tail/groove (for joining templates and caps
    into a row) + a small dovetail GROOVE cut into the front wall where
    the old embossed label used to sit, for a nameplate to slide into.

    NO baked text anywhere. `drive` is the only thing that varies between
    the two templates - the post's cross-section (see PARAMS's comment on
    drive_af_nominal), not the socket size, which no longer has any effect
    on this piece's geometry at all (see module docstring)."""
    body = make_base(p).fuse(make_post(p, drive))
    body = body.fuse(make_dovetail_tail(p))
    body = body.cut(make_dovetail_groove_cutter(p))
    body = body.cut(make_nameplate_slot_cutter(p))
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
    caught by watertight(). Pulling the far edge in by FUSE_EMBED keeps it
    strictly inside the cylinder everywhere, so there's no leftover sliver
    at the pinch latitude to disconnect - real, if imperceptible (0.1mm on
    an 8mm radius), overlap instead of a zero-gap tangent touch.

    Unlike the post/tail fuses, this defect happens to still get caught by
    watertight() at FUSE_EMBED=0 (the caps have no post fuse ahead of it
    to mask the resulting NON-MANIFOLD mesh) - but that is incidental to
    this cut's specific topology, not something to rely on in general.
    check_cap_corner_solid() below checks the same thing directly, via raw
    B-rep Solids count on the finished cap body, with no meshing involved.
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
# Piece set
# --------------------------------------------------------------------------

def generate_all(p):
    """Returns {name: shape} for exactly the 5 piece types this generator
    produces: template_3-8in, template_1-2in, cap_start, cap_end,
    nameplate_template. Single source of truth for the piece set - run()
    derives its expected-count assertion from len() of this dict rather
    than a hardcoded number."""
    out = {}
    for drive in p["drives"]:
        out["template_%s" % drive] = make_template(p, drive)
    out["cap_start"] = make_cap(p, "start")
    out["cap_end"] = make_cap(p, "end")
    out["nameplate_template"] = make_nameplate(p)
    return out


# --------------------------------------------------------------------------
# Fit coupons
# --------------------------------------------------------------------------

def build_post_coupon(p, drive):
    """A single template, for real-socket test fit. Size no longer matters
    (every socket of a given drive shares the same post - see module
    docstring) - only drive does, so this is just make_template unchanged,
    unlike the old per-size middle piece it used to build."""
    return make_template(p, drive)


def build_dovetail_coupon(p):
    """Two adjacent templates, pre-assembled, to test the piece-to-piece
    snap by hand. Drive doesn't matter for this - the piece-to-piece
    dovetail geometry is identical regardless of drive - so this uses
    3-8in arbitrarily."""
    a = make_template(p, "3-8in")
    b = make_template(p, "3-8in").translate(App.Vector(p["base_w"], 0, 0))
    return a.fuse(b)


def build_nameplate_coupon(p):
    """One template + one nameplate, pre-assembled and fused into a single
    printable test object, so the new slot/tail interlock can be
    physically verified before committing to printing full templates -
    same "print small coupons first" convention as build_post_coupon /
    build_dovetail_coupon. Drive doesn't matter (the slot geometry is
    identical regardless of drive), so this uses 3-8in arbitrarily.

    NOTE, same caveat as build_dovetail_coupon: this fuse succeeds via the
    plaque's own flat back face touching the template's wall with a
    genuine FUSE_EMBED overlap OUTSIDE the narrow dovetail cavity (see
    _nameplate_plaque_shape's docstring), not because the dovetail tail/
    cavity themselves are forced into contact - by design they have
    nameplate_dt_clearance of real air gap on the neck/tip sides so the
    two pieces can actually slide apart by hand. Real interlock fit is
    verified separately and rigorously by check_nameplate_fit()'s direct
    B-rep containment/collision checks, not by this fuse succeeding.

    Uses _nameplate_assembled(p) (the wall-mounted orientation), NOT
    make_nameplate(p) (the print-friendly export orientation) - the two
    are the same design geometry, just placed differently in space (see
    make_nameplate's docstring); only the assembled placement actually
    sits against the template's slot."""
    template = make_template(p, "3-8in")
    nameplate = _nameplate_assembled(p)
    return template.fuse(nameplate)


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
    FUSE_EMBED reverted to 0 on make_post/make_dovetail_tail). Mesh-
    tessellation signals are a downstream proxy for geometry, not a
    geometric fact, and that defect class can sit right at the edge of
    what a mesh self-intersection distance can distinguish from ordinary
    tessellation noise (see SELF_INTERSECT_TOL). See check_fuse_overlap()
    and check_cap_corner_solid() for the direct, tessellation-independent
    checks that do catch it regardless."""
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
        # See SELF_INTERSECT_TOL: only escalate crossings big enough to be
        # a real overlap, not sub-chord-tolerance tessellation noise from
        # the post's own chamfer-on-fillet corners.
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
    >=2mm posts/tabs). Covers both dovetail scales now - the piece-to-piece
    connector and the new, lighter-duty nameplate connector - plus the
    nameplate plaque's own thickness."""
    issues = []
    dt_wall = p["dt_neck_w"] / 2.0
    if dt_wall < 1.2:
        issues.append("dovetail neck %.2fmm below 1.2mm minimum" % dt_wall)
    nameplate_dt_wall = p["nameplate_dt_neck_w"] / 2.0
    if nameplate_dt_wall < 1.2:
        issues.append("nameplate dovetail neck %.2fmm below 1.2mm minimum"
                       % nameplate_dt_wall)
    if p["nameplate_t"] < 1.2:
        issues.append("nameplate thickness %.2fmm below 1.2mm minimum"
                       % p["nameplate_t"])
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
    `base`, relying on FUSE_EMBED for genuine overlap) actually has
    positive volumetric overlap with `base` BEFORE the fuse happens.

    This is deliberately NOT a mesh-tessellation proxy. base.common(part)
    is OCC's own exact B-rep boolean intersection - there is no meshing,
    no chord tolerance, nothing for tessellation noise to hide in or be
    confused with. A zero-gap tangent touch (FUSE_EMBED <= 0) has exactly
    zero shared volume; only a genuine embed does not."""
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
    sides); at the real FUSE_EMBED=0.1 it is 1 for both."""
    cap = make_cap(p, side)
    n_solids = len(cap.Solids)
    if n_solids != 1:
        return ("cap_%s: %d disconnected solids (expected 1) - zero-gap "
                "tangent at the corner rounding cut" % (side, n_solids))
    return None


def check_fuse_overlaps(p):
    """Runs check_fuse_overlap()/check_cap_corner_solid() across every
    FUSE_EMBED-dependent boolean in the design: post/base (x2 drives),
    piece-to-piece dovetail tail/base, both cap corner cuts, and the two
    nameplate joins (tail-to-plaque, plaque-to-template)."""
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

    issue = check_fuse_overlap(_nameplate_plaque_shape(p),
                                make_nameplate_tail(p),
                                "nameplate tail/plaque fuse")
    if issue:
        issues.append(issue)
    issue = check_fuse_overlap(make_template(p, "3-8in"), make_nameplate(p),
                                "nameplate/template fuse")
    if issue:
        issues.append(issue)
    return issues


def check_socket_od_clearance(p):
    """Permanent regression guard for the base footprint (see PARAMS's
    base_w/base_d comment) against the one real worst-case socket size,
    now that the piece set is size-agnostic templates rather than a
    per-size table to sweep: 1in SAE (nominal_mm=25.4), whose estimated OD
    (~35.67mm via estimated_socket_od_mm) is slightly larger than 25mm
    metric's own measured 35mm point - see SOCKET_OD_POINTS_MM's comment.
    The base footprint doesn't depend on drive either, so one check covers
    both templates.

    Builds a real Part.makeCylinder probe of the estimated OD, centered at
    the post's own (cx, cy) - the same formula make_post uses - spanning
    the full post height plus headroom, and:

      1. Confirms the probe does not extend past the base's own footprint
         (cyl.cut(footprint_box).Volume == 0) - a true geometric fact, not
         an inference from BoundBox math.
      2. Confirms the probe has zero volumetric overlap with the dovetail
         tail (protrudes outward past +X) and the dovetail groove cutter
         (cuts into -X) - common(...).Volume == 0 for both.
      3. Computes the real clearance margin in all four directions from
         the probe's own BoundBox against the footprint edges, and asserts
         it clears OD_CLEARANCE_FLOOR.
    """
    issues = []
    cx, cy = p["base_w"] / 2.0, p["base_d"] * 0.62
    footprint = Part.makeBox(p["base_w"], p["base_d"], 500,
                              App.Vector(0, 0, -10))
    tail = make_dovetail_tail(p)
    groove = make_dovetail_groove_cutter(p)

    nominal_mm = 25.4  # 1in SAE - the true worst case, see module comment
    od = estimated_socket_od_mm(nominal_mm)
    r = od / 2.0
    probe = Part.makeCylinder(r, p["post_h"] + 20,
                               App.Vector(cx, cy, p["base_h"]))
    outside = probe.cut(footprint).Volume
    if outside > 1e-6:
        issues.append(
            "1in SAE (est OD %.2fmm): probe extends %.2f mm3 past the base "
            "footprint" % (od, outside))
    tail_overlap = probe.common(tail).Volume
    if tail_overlap > 1e-6:
        issues.append(
            "1in SAE (est OD %.2fmm): probe overlaps dovetail tail by "
            "%.4f mm3" % (od, tail_overlap))
    groove_overlap = probe.common(groove).Volume
    if groove_overlap > 1e-6:
        issues.append(
            "1in SAE (est OD %.2fmm): probe overlaps dovetail groove cutter "
            "by %.4f mm3" % (od, groove_overlap))
    left = cx - r
    right = p["base_w"] - cx - r
    front = cy - r
    back = p["base_d"] - cy - r
    margin = min(left, right, front, back)
    print("  1in SAE: est OD %.2fmm -> clearance margin %.2fmm "
          "(left=%.2f right=%.2f front=%.2f back=%.2f)"
          % (od, margin, left, right, front, back))
    if margin <= OD_CLEARANCE_FLOOR:
        issues.append(
            "1in SAE: OD clearance margin %.2fmm at or below the %.2fmm "
            "floor - base footprint too tight for this socket's estimated "
            "outer diameter" % (margin, OD_CLEARANCE_FLOOR))
    return issues


def check_nameplate_fit(p):
    """Direct B-rep verification that the nameplate's tail and a
    template's slot actually interlock when a nameplate is placed at its
    real assembled position against a template - both built via the exact
    same rotate/translate math (_place_on_wall), so no extra positioning
    is needed here beyond building both against the same p. Uses make_
    nameplate_tail/_nameplate_assembled (the wall-mounted orientation),
    NOT make_nameplate (the print-friendly export orientation) - see
    make_nameplate's docstring. Drive doesn't affect any of this
    geometry, so this checks against one template (3-8in) only, same as
    build_dovetail_coupon/build_nameplate_coupon.

    All checks are real OCC B-rep booleans, no meshing involved - the same
    "build real geometry, verify with real booleans" discipline as check_
    fuse_overlap/check_cap_corner_solid:

      1. CONTAINMENT - the tail (built with no clearance) should sit
         almost entirely inside the groove cavity (built with
         nameplate_dt_clearance added to neck/tip) once both are placed at
         their real assembled positions. Not exactly 100% - verified live
         that the ~4% gap is the tail's own FUSE_EMBED root overlap (the
         same intentional push-past-the-wall-plane every other fuse in
         this file uses, matching make_dovetail_tail/make_post), not
         clearance and not misalignment - but a low fraction would still
         mean the two are actually misaligned, worth catching.
      2. COLLISION - the tail must not collide with the post or either
         half of the piece-to-piece dovetail (both 0.0 mm3 overlap
         expected - they sit far apart in Y, but this checks the real
         geometry rather than assuming from separation by eye).
      3. CONNECTIVITY - the assembled coupon (template with slot cut, plus
         a nameplate fused on) is one single connected solid, not two
         solids merely touching in the same file.
      4. FOOTPRINT - the plaque's own X extent stays within the template's
         base_w, so a future PARAMS change that widens nameplate_w can't
         silently run the plaque off the edge of the piece without this
         check catching it (nameplate_h/nameplate_zone_z's Z placement is
         checked implicitly by (3)'s connectivity requirement and by
         watertight()/check_structural, since a Z position off the wall
         entirely would break the flat-back-to-wall contact the fuse in
         (3) depends on).
    """
    issues = []
    template = make_template(p, "3-8in")
    tail = make_nameplate_tail(p)
    cavity = make_nameplate_slot_cutter(p)
    nameplate = _nameplate_assembled(p)

    tail_vol = tail.Volume
    contained_vol = tail.common(cavity).Volume
    frac = contained_vol / tail_vol if tail_vol > 0 else 0.0
    print("  nameplate tail/slot containment: %.4f of %.4f mm3 tail volume "
          "(%.1f%%)" % (contained_vol, tail_vol, frac * 100))
    if frac < 0.90:
        issues.append(
            "nameplate tail only %.1f%% contained in the template's slot "
            "cavity (expected >=90%% given nameplate_dt_clearance=%.2fmm "
            "per side) - tail/slot geometry likely misaligned"
            % (frac * 100, p["nameplate_dt_clearance"]))

    post = make_post(p, "3-8in")
    post_overlap = tail.common(post).Volume
    if post_overlap > 1e-6:
        issues.append("nameplate tail overlaps the post by %.4f mm3"
                       % post_overlap)
    pd_tail_overlap = tail.common(make_dovetail_tail(p)).Volume
    if pd_tail_overlap > 1e-6:
        issues.append(
            "nameplate tail overlaps the piece-to-piece dovetail tail by "
            "%.4f mm3" % pd_tail_overlap)
    pd_groove_overlap = tail.common(make_dovetail_groove_cutter(p)).Volume
    if pd_groove_overlap > 1e-6:
        issues.append(
            "nameplate tail overlaps the piece-to-piece dovetail groove "
            "cutter by %.4f mm3" % pd_groove_overlap)

    coupon = template.fuse(nameplate)
    n_solids = len(coupon.Solids)
    print("  nameplate+template coupon: %d solid(s), volume %.1f mm3"
          % (n_solids, coupon.Volume))
    if n_solids != 1:
        issues.append(
            "nameplate+template coupon: %d disconnected solids (expected "
            "1) - plaque is not making genuine contact with the template's "
            "wall" % n_solids)

    bb = nameplate.BoundBox
    if bb.XMin < -1e-6 or bb.XMax > p["base_w"] + 1e-6:
        issues.append(
            "nameplate footprint X[%.3f,%.3f] outside base width [0,%.3f]"
            % (bb.XMin, bb.XMax, p["base_w"]))

    return issues


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def export_all(shapes, out_dir, formats=("step", "stl", "3mf")):
    """Export every shape to the given formats (default STEP/STL/3MF),
    reusing a single scratch document for the whole batch (not one per
    shape - creating/closing a FreeCAD document per export is needless
    churn and keeps this off the GUI thread).

    A failure exporting one shape (STEP write, recompute, or mesh write) is
    caught, logged, and does NOT abort the run - the loop still attempts
    every remaining shape so one bad piece can't hide the state of the
    others. Returns the list of shape names that failed; the caller (run())
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


def run():
    doc = App.newDocument("socket_organizer")
    pieces = generate_all(PARAMS)
    print("generated %d pieces (expected 5)" % len(pieces))
    assert len(pieces) == 5
    assert set(pieces) == {"template_3-8in", "template_1-2in",
                            "cap_start", "cap_end", "nameplate_template"}

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
              "cap corner cuts x2, nameplate tail/plaque, "
              "nameplate/template)" % len(PARAMS["drives"]))

    print("\n--- nameplate slot/tail fit self-check "
          "(real B-rep containment/collision/connectivity) ---")
    nameplate_fit_issues = check_nameplate_fit(PARAMS)
    if nameplate_fit_issues:
        for issue in nameplate_fit_issues:
            print("NAMEPLATE-FIT: %s" % issue)
    else:
        print("nameplate tail is substantially contained in the template's "
              "slot cavity, collides with neither the post nor the "
              "piece-to-piece dovetail, the assembled coupon is one "
              "connected solid, and the plaque footprint stays within the "
              "template's width")

    print("\n--- socket OD clearance self-check "
          "(real cylinder probe, 1in SAE worst case) ---")
    od_clearance_issues = check_socket_od_clearance(PARAMS)
    if od_clearance_issues:
        for issue in od_clearance_issues:
            print("OD-CLEARANCE: %s" % issue)
    else:
        print("the worst-case (1in SAE) estimated socket OD clears the "
              "base footprint (and stays clear of the dovetail tail/"
              "groove) by more than the %.2fmm floor" % OD_CLEARANCE_FLOOR)

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
    # vs 12.70mm with the same 0.5mm undersize applied to both).
    for drive in PARAMS["drives"]:
        name = "template_%s" % drive
        overlap = check_post_fit(pieces[name], PARAMS, drive)
        print("post fit probe overlap (%s, drive %s): %.2f mm3"
              % (name, drive, overlap))
        assert overlap > 0.5, (
            "%s post shows no interference with nominal drive square - "
            "too loose" % name)

    assert not struct_issues, "structural check failed, see report above"
    assert not fuse_issues, "fuse-overlap check failed, see report above"
    assert not nameplate_fit_issues, (
        "nameplate slot/tail fit check failed, see report above")
    assert not od_clearance_issues, (
        "socket OD clearance check failed, see report above")
    assert not printability_issues, "printability check failed, see report above"
    assert not mesh_issues, "mesh/watertight check failed, see report above"

    coupon = build_dovetail_coupon(PARAMS)
    # NOTE: this only proves the two halves fuse into one watertight solid
    # (i.e. the flat base walls touch with no gap). It does NOT verify the
    # dovetail tail/groove actually interlock; don't treat this as
    # dovetail-fit proof, that needs eyeballing the coupon geometry or a
    # real print.
    assert len(coupon.Solids) == 1, "dovetail coupon halves did not fuse into one piece"
    print("dovetail coupon: 1 solid, volume %.1f mm3" % coupon.Volume)

    out_dir = os.path.join(_script_dir(), "exports")
    export_failures = list(export_all(pieces, out_dir))

    coupons = {
        "post_coupon_3-8in": build_post_coupon(PARAMS, "3-8in"),
        "post_coupon_1-2in": build_post_coupon(PARAMS, "1-2in"),
        "dovetail_coupon": coupon,
        "nameplate_coupon": build_nameplate_coupon(PARAMS),
    }
    export_failures.extend(export_all(coupons, out_dir))

    print("\nExported %d pieces + %d coupons to %s"
          % (len(pieces), len(coupons), out_dir))

    # A partial export set must never silently look like success - but let
    # every shape be attempted first (export_all already ran the full loop
    # and collected every failure, not just the first) before failing
    # loudly here.
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
