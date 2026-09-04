# -*- coding: utf-8 -*-
"""
Socket organizer - parametric generator for FreeCAD.

Modular, interlinking socket holder. Exactly 5 piece types, size-agnostic:

  - template_3-8in / template_1-2in - a blank base+post template, one per
    drive (3/8in / 1/2in). The post's cross-section only depends on the
    drive square, NOT which socket size sits on it - every socket of a
    given drive shares the same square drive-hole - so one blank template
    per drive already physically fits every socket size in that drive.
    No baked text anywhere. Has a plain rectangular pocket inset straight
    down into the TOP of the riser, in front of the post, for a nameplate
    to press into (see below), plus the usual piece-to-piece dovetail
    tail/groove for joining templates and caps into a row.
  - cap_start / cap_end - unchanged row-end pieces, still blank.
  - nameplate_template - a single blank rectangular block that presses
    straight down into a template's top pocket, snug/friction fit, sitting
    flush with the riser's top surface once seated. Print as many copies
    as you like and label each one with your slicer's own text tool (e.g.
    Bambu Studio) - this generator no longer bakes any size text into
    geometry at all. See nameplate_w/h/t/clearance below for the
    block/pocket dimensions - TUNE VIA NAMEPLATE FIT COUPON.

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
    # base_w/base_d were 43.0/53.0 (see git history) with a sloped front
    # wall and a wall-mounted dovetail-slot nameplate. That mechanism
    # didn't print cleanly, so the nameplate moved to a plain top-of-base
    # inset pocket instead (see make_nameplate_pocket_cutter) - which also
    # removes the sloped wall entirely (it only ever existed to angle the
    # wall-mounted label for visibility, see make_base). With no more
    # front-wall label zone to reserve room for, the post recentered from
    # (base_w/2, base_d*0.62) to (base_w/2, base_d/2) (see make_post), and
    # the footprint shrank to base_w=40.0/base_d=45.0. base_h grew from
    # 10.0 to 15.0 to leave real floor material (base_h - nameplate_t)
    # under the new pocket - see check_nameplate_fit's floor-thickness
    # check and check_structural. post_h (11.0) is unaffected by any of
    # this - it's purely about drive-square engagement depth.
    #
    # That cy=base_d/2 centering was then found to be a real design flaw,
    # live: the worst-case socket (worst_case_socket_od_mm()=36.0mm OD,
    # r=18.0mm) sitting on a post centered at cy=22.5mm has a circular
    # footprint reaching forward to Y=4.5mm - INSIDE the nameplate pocket's
    # own Y-span at the time (~Y=[4.38,12.38]) - so a large socket resting
    # on the post would sit on top of / over the nameplate, making the
    # label unreadable. Fixed by back-biasing the post: cy is now derived
    # by _post_cy(p) (NOT a fixed base_d/2 or other constant - it's solved
    # from worst_case_socket_od_mm(), nameplate_h/nameplate_clearance, and
    # NAMEPLATE_MARGIN_MM so it can't silently drift out of sync with any
    # of those), which works out to cy=30.75mm at the current PARAMS.
    # base_d grew from 45.0 to 51.0 (base_w stays 40.0 - it's sized off
    # the socket OD in X, which this change doesn't touch, re-verified
    # live via check_socket_od_clearance's left/right margins, unchanged
    # at 2.0mm each) so the back-biased worst-case-OD probe still clears
    # the back wall by NAMEPLATE_MARGIN_MM (2.25mm) of real margin:
    # base_d = cy + r + NAMEPLATE_MARGIN_MM = 30.75 + 18.0 + 2.25 = 51.0.
    # See NAMEPLATE_MARGIN_MM's own comment and _post_cy's docstring for
    # the full derivation, and check_socket_nameplate_clearance() for the
    # live B-rep proof that the pocket and the worst-case socket probe now
    # have exactly zero overlap.
    #
    # base_d's own back-wall clearance (the "+2.25" in the formula above)
    # is NOT re-derived/enforced from NAMEPLATE_MARGIN_MM at runtime - it's
    # a hand-computed literal baked into this number. What actually gets
    # asserted is check_socket_od_clearance's generic back-margin check
    # against the looser OD_CLEARANCE_FLOOR (1.5mm), not this 2.25mm value
    # specifically. So a future change to NAMEPLATE_MARGIN_MM/nameplate_h/
    # the worst-case OD will correctly move cy and fail loudly if base_d
    # wasn't updated to match (same as it did once already for cap_round_r,
    # see d57e511) - but base_d itself still needs a human to recompute it
    # from the formula above, this isn't closed-loop/self-adjusting.
    #
    # Both the socket-OD clearance (check_socket_od_clearance) and the
    # pocket/post placement (check_nameplate_fit) are verified live against
    # these dimensions via real B-rep booleans, not assumed from this
    # comment - see those functions' own docstrings/prints for the actual
    # measured numbers.
    "base_w":         40.0,   # left-right, this is the row-direction pitch
    "base_d":         51.0,   # front-to-back depth
    "base_h":         15.0,   # riser height before the post/socket area

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

    # --- nameplate pocket/block (top-of-base inset, straight press fit) ----
    # Replaces the old wall-mounted dovetail slot/tail entirely (see git
    # history) - the nameplate is now a plain rectangular block that
    # presses straight down into a plain rectangular pocket cut into the
    # riser's top face, in front of the post. No dovetail mechanism, no
    # sloped-wall placement math, needed for this any more.
    #
    # nameplate_w/h grew from the old dovetail nameplate's 22x6mm to
    # 24x8mm (more usable label area now that it isn't constrained to a
    # narrow wall-slope band) and nameplate_t doubled from 2.0mm to 4.0mm
    # (a top-pocket press fit wants real vertical engagement depth to
    # actually grip, unlike the old wall slot which only needed to be
    # thick enough for the slicer's embossed/engraved text to read).
    #
    # nameplate_clearance (per side, both pocket footprint dimensions) is
    # a first engineering guess, same "TUNE VIA COUPON" status as
    # dt_clearance/post_af_undersize were before their own print history -
    # a plain press fit (not a sliding dovetail) wants a tighter,
    # friction-grip gap than dt_clearance's 0.15mm sliding-fit value, so
    # 0.125mm/side (a ~17% reduction from dt_clearance's 0.15mm) is chosen
    # as a reasonable FDM starting point, not reused wholesale from a
    # different mechanism. TUNE VIA NAMEPLATE FIT COUPON before trusting
    # this.
    #
    # Pocket X/Y position is NOT a fixed PARAM - it's derived in
    # _nameplate_pocket_xy from the template's real, live-measured
    # geometry (base_w/2 in X; centered with real margin between the front
    # wall and the closest drive's actual post footprint in Y), so it
    # can't silently drift out of sync if any of those params change - see
    # that function's docstring for the derivation and check_nameplate_
    # fit's printed numbers for the actual live measurement.
    "nameplate_w":           24.0,
    "nameplate_h":            8.0,
    "nameplate_t":            4.0,
    "nameplate_clearance":   0.125,  # TUNE VIA NAMEPLATE FIT COUPON

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
# invisible to isValid()/Solids-count checks. Also used by build_nameplate_
# coupon's block-into-pocket-floor fuse (see _nameplate_block_in_pocket) -
# the top-pocket mechanism's one FUSE_EMBED-dependent join.
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
# what other geometry (pockets, dovetail grooves) exists on the piece -
# this is a real, independent artifact of the post geometry itself, not
# something parameter-tuning elsewhere can clear.
#
# IMPORTANT - what this tolerance does NOT catch: a zero-gap-tangent-fuse
# defect (FUSE_EMBED reverted to 0 on make_post/make_dovetail_tail) measures
# self-intersection distances that can fall in this same noise-scale range,
# so distance-based mesh filtering alone cannot reliably separate the two
# defect classes. That defect is instead caught directly, before any mesh
# is involved, by check_fuse_overlap()'s direct base.common(part).Volume
# assertion (see "Fuse-overlap self-checks"), which needs no mesh at all.
# This tolerance's only job is filtering the post-chamfer tessellation
# noise described above out of watertight()'s mesh self-intersection
# check so it doesn't cry wolf on every build.
SELF_INTERSECT_TOL = 2 * LINEAR_DEFLECTION

# Two real hand-measured (calipers) socket outer-diameter data points,
# supplied by the user, anchoring the base footprint against actual socket
# hardware rather than an assumption: a 22mm socket measures ~30mm OD; a
# 25mm socket measures ~35mm OD. These are socket BODY widths, not the
# drive-square size. Kept for historical/documentation reference and as a
# live cross-check in check_socket_od_clearance - see SOCKET_OD_WORST_
# CASE_MM below for the actual number that check asserts against.
#
# estimated_socket_od_mm() linearly interpolates/extrapolates between these
# two points to estimate OD for any nominal size (mm). Converting 1in SAE
# to its metric-equivalent bore (25.4mm) and running it through this line
# predicts an OD of ~35.67mm, slightly LARGER than 25mm metric's own
# measured 35mm point - so 1in SAE, not 25mm metric, is the worst case this
# two-point model itself predicts.
SOCKET_OD_POINTS_MM = [(22.0, 30.0), (25.0, 35.0)]

# Authoritative worst-case socket outer diameter (mm) for the clearance
# check below - the user's own stated figure for the largest 25mm/1in
# socket, slightly more conservative than estimated_socket_od_mm(25.4)'s
# own two-point linear extrapolation (~35.67mm, see SOCKET_OD_POINTS_MM's
# comment above). check_socket_od_clearance() checks against
# max(SOCKET_OD_WORST_CASE_MM, estimated_socket_od_mm(25.4)) - whichever is
# actually larger (more conservative) - so the extrapolation still acts as
# a live cross-check rather than being silently discarded, but this 36.0mm
# figure is the number that governs in practice.
SOCKET_OD_WORST_CASE_MM = 36.0

# Minimum acceptable clearance (mm) between the worst-case socket body and
# the base footprint's own outer edge, in any of the four directions
# (left/right/front/back from the post center). See check_socket_od_
# clearance()'s own printed numbers for the actual live-measured margins at
# the current base_w/base_d/post-center dimensions.
#
# Unlike COUNTER_WIDTH_FLOOR used to be (grounded in an independent physical
# fact - nozzle diameter), this floor has no such external anchor:
# SOCKET_OD_POINTS_MM is only two measured points, and estimated_socket_
# od_mm() is a linear guess between/near them, not a physical law. 1.5mm is
# chosen to absorb ordinary FDM dimensional tolerance (typically a few
# tenths of a mm) many times over, plus a real buffer for that OD-model
# uncertainty.
OD_CLEARANCE_FLOOR = 1.5

# Minimum headroom (mm) between the piece-to-piece dovetail's own Y-extent
# (_dovetail_y_offset's result, plus the tail/groove profile's own
# half-width) and the base's own base_d depth. Unlike OD_CLEARANCE_FLOOR
# (which reasons about the socket body vs. the footprint), this floor has
# nothing to do with sockets at all - it's the dovetail geometry itself
# potentially exceeding the piece's own footprint in Y, a hard containment
# failure (see _dovetail_y_offset's own assert). 1.0mm is enough to absorb
# ordinary FDM dimensional tolerance without being so loose it would let a
# real derivation bug (e.g. dt_tip_w growing unchecked) slip through as
# "close enough".
DOVETAIL_Y_OFFSET_HEADROOM_MM = 1.0

# Real, guaranteed-non-tangent margin (mm) used to back-bias the post away
# from the nameplate pocket. Discovered live: with the post centered at
# cy=base_d/2 (22.5mm at the old base_d=45.0), the worst-case-OD socket
# probe's own circular footprint (r=worst_case_socket_od_mm()/2=18.0mm,
# centered on the post) reached all the way to Y=cy-r=4.5mm - INSIDE the
# nameplate pocket's own Y-span (pocket sat at roughly Y=[4.38,12.38] under
# the old post-relative placement, see _nameplate_pocket_xy's prior
# docstring in git history) - so a real worst-case socket resting on the
# post would sit on top of / over the nameplate, making the label
# unreadable while that socket is stored. The fix isn't a tighter
# clearance number on the same layout - it's a real reserved Y-band, sized
# by this margin, that the pocket and the socket's circular footprint
# never share.
#
# Used three times (see _post_cy and _nameplate_pocket_xy), each a
# distinct real-world gap: (a) nameplate pocket cavity's front edge to the
# front wall (Y=0), (b) pocket cavity's back edge to the worst-case
# socket's frontmost reach (cy-r) - this is the one that actually
# guarantees the fix, see _post_cy's docstring - and (c) the socket's
# backmost reach (cy+r) to the back wall (Y=base_d). Same "few tenths of
# FDM tolerance, times several, plus real model uncertainty" reasoning as
# OD_CLEARANCE_FLOOR (1.5mm), but picked a bit above OD_CLEARANCE_FLOOR's
# own value and specifically above check_nameplate_fit's own hardcoded
# 2.0mm footprint-margin floor (see that function) so margin (a) alone
# doesn't sit exactly ON that check's boundary - 2.25mm keeps real slack
# above it rather than an exact tie that would be one float rounding away
# from a spurious failure.
NAMEPLATE_MARGIN_MM = 2.25


def estimated_socket_od_mm(nominal_mm):
    """Linear estimate of a socket's outer diameter (mm) from its nominal
    bore size (mm), anchored on the two real measured points in
    SOCKET_OD_POINTS_MM. Not a physical model - sockets aren't actually
    linear in OD-vs-bore across their whole range - but a reasonable
    estimate near the two measured points (22mm, 25mm), which is exactly
    what check_socket_od_clearance() needs it for: cross-checking against
    the authoritative SOCKET_OD_WORST_CASE_MM figure.

    This is NOT a trustworthy estimate far below the anchors: extrapolated
    down to small nominal sizes, the line goes unphysical - it predicts an
    OD *smaller than the bore itself*, which is impossible. Not a concern
    for check_socket_od_clearance(), which only ever evaluates it near the
    anchor range (22-25.4mm)."""
    (x0, y0), (x1, y1) = SOCKET_OD_POINTS_MM
    slope = (y1 - y0) / (x1 - x0)
    return y0 + slope * (nominal_mm - x0)


def worst_case_socket_od_mm():
    """The OD (mm) actually used by every worst-case-socket check/placement
    in this file: whichever is larger (more conservative) of the
    authoritative SOCKET_OD_WORST_CASE_MM figure and the two-point linear
    estimate for 1in SAE (estimated_socket_od_mm(25.4)) - see SOCKET_OD_
    WORST_CASE_MM's own comment for why both are considered rather than
    just trusting one. A single source of truth so check_socket_od_
    clearance and _dovetail_y_offset (which both need to reason about the
    same worst-case probe) can't silently drift apart."""
    return max(SOCKET_OD_WORST_CASE_MM, estimated_socket_od_mm(25.4))


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

def make_base(p):
    """Riser block: a plain rectangular box (base_w x base_d x base_h), no
    wedge cut, no sloped wall. The front wall used to lean back
    (front_slope_deg, now removed) specifically to angle a wall-mounted
    nameplate for visibility; now that the nameplate lives in a top-of-base
    inset pocket instead (see make_nameplate_pocket_cutter), there's no
    reason for the slope any more. Front is still the -Y face, for
    consistency with every other piece/coupon's convention (the post and
    the new pocket both sit toward +Y from it)."""
    return box(p["base_w"], p["base_d"], p["base_h"], 0, 0, 0)


def _post_cy(p):
    """Minimum Y for the post's centerline that GUARANTEES the worst-case
    socket's own circular footprint (r=worst_case_socket_od_mm()/2.0,
    centered on the post - the same probe check_socket_od_clearance and
    the nameplate-clearance check below both build for real) never shares
    any Y with the nameplate pocket's cavity, with real margin on both
    sides of the boundary - not the old cy=base_d/2 centering, which was
    proven live to let a worst-case socket's footprint reach all the way
    into the pocket (see NAMEPLATE_MARGIN_MM's docstring for the discovery
    and the actual old numbers).

    Derivation, front to back:

      1. The pocket cavity (nameplate_w/h plus nameplate_clearance per
         side - the real cut geometry, not the raw nameplate_h PARAM) sits
         with its front edge NAMEPLATE_MARGIN_MM behind the front wall
         (Y=0) - see _nameplate_pocket_xy, which places the pocket using
         this exact same margin so the two stay consistent by
         construction.
      2. The pocket cavity's back edge is therefore at
         NAMEPLATE_MARGIN_MM + cavity_h.
      3. The socket probe's frontmost reach (cy - r) must sit at least
         another NAMEPLATE_MARGIN_MM behind THAT, so the gap between the
         pocket and the probe is a real, measured margin - not a
         zero-gap tangent touch that would technically read as "no
         overlap" but leave no actual room for FDM tolerance or model
         uncertainty.

    So: cy = (NAMEPLATE_MARGIN_MM + cavity_h) + NAMEPLATE_MARGIN_MM + r.

    This is the MINIMUM cy satisfying the guarantee - used directly (not
    padded further) as PARAMS["base_d"] is sized, in turn, to leave
    NAMEPLATE_MARGIN_MM of its own real clearance behind the resulting
    probe (see PARAMS's base_d comment), so growing cy past this minimum
    would just eat into that back-wall margin for no benefit.

    Verified live by check_socket_nameplate_clearance() and check_
    nameplate_fit() - both build the real pocket cutter and/or probe
    geometry and assert a real B-rep boolean overlap of exactly 0, not
    inferred from this arithmetic alone."""
    r = worst_case_socket_od_mm() / 2.0
    cavity_h = p["nameplate_h"] + 2 * p["nameplate_clearance"]
    pocket_y1 = NAMEPLATE_MARGIN_MM + cavity_h
    return pocket_y1 + NAMEPLATE_MARGIN_MM + r


def _post_center(p):
    """(cx, cy) for the post's centerline on the riser's top footprint -
    single source of truth used by every function that places or probes
    the post, the piece-to-piece dovetail's Y-offset, and the nameplate
    pocket, so none of them can silently drift apart. cx stays a simple
    base_w/2 centering (the post's X placement has nothing to do with the
    nameplate - only base_w, which is sized off the socket OD in X, drives
    it); cy is back-biased away from the nameplate pocket, see
    _post_cy."""
    return p["base_w"] / 2.0, _post_cy(p)


def make_post(p, drive):
    """Square post, corners rounded, sized to the drive square (undersized
    for friction). Centered in X on the riser's top footprint, back-biased
    in Y (see _post_center/_post_cy) so the worst-case socket's own
    circular footprint clears the nameplate pocket with real margin,
    rather than the old cy=base_d/2 centering (proven live to let a
    worst-case socket's footprint reach into the pocket - see
    NAMEPLATE_MARGIN_MM's docstring).

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
    cx, cy = _post_center(p)
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


def _dovetail_y_offset(p):
    """Y-offset (translate) for the piece-to-piece dovetail tail/groove.

    Used to be a fixed simple fraction of base_d (base_d*0.3 = 13.5mm at
    base_d=45.0) - unrelated to the nameplate mechanism, so that fraction
    itself was expected to still be fine after the nameplate redesign.
    Verified LIVE rather than assumed, though (per this file's own
    discipline), and it was NOT fine: check_socket_od_clearance's
    worst-case-OD probe (centered on the now-recentered post, cy=base_d/2
    instead of the old back-biased base_d*0.62) genuinely overlapped the
    groove cutter at that offset (confirmed live: ~1.19 mm3, at the
    groove's deepest point x=dt_depth, where the worst-case-OD circle's
    Y-reach is largest) - a real geometric side-effect of recentering the
    post that the old back-biased placement never had to contend with,
    since the post used to sit much farther from the dovetail's Y-band.

    So the offset is now derived from real geometry instead of a fixed
    fraction: biased toward the BACK of the piece (away from the
    nameplate pocket's own front-of-post zone - see make_nameplate_
    pocket_cutter - even though the two never actually share an X range,
    the groove/tail sit at x in [0, dt_depth] / [base_w-dt_depth, base_w]
    while the pocket sits well inboard of both, so this is about keeping
    the layout intent sensible, not a hard requirement), placed just far
    enough that the worst-case-OD probe's circular arc at the groove's
    deepest point (x=dt_depth) clears the groove's own near edge by a
    real `margin`, plus enough headroom to stay inside base_d.

    Only the LEFT-side groove cutter (x in [0, dt_depth]) is ever within
    reach of the worst-case-OD circle in X (circle spans cx-r..cx+r,
    which stays short of the right-side tail's root at x=base_w for every
    dimension this file has used) - see check_socket_od_clearance, which
    already checks both independently and only ever caught the groove
    side live.

    PRECONDITION (asserted below, not just assumed): dt_depth < base_w/2 -
    FUSE_EMBED. This is what makes the groove side, not the tail side, the
    binding constraint in the first place - the groove's near edge (x=
    dt_depth) sits closer to the post center (cx=base_w/2) than the tail's
    embedded root (x=base_w-FUSE_EMBED) does, precisely because dt_depth is
    kept smaller than that half-width-minus-embed figure. If a future
    PARAMS change ever grew dt_depth past this bound, the tail side could
    become the tighter constraint instead and this function's
    groove-only reasoning would silently stop covering the actual
    worst case - so this is stated as an explicit, checked fact rather
    than the implicit assumption it used to be.

    RESULT BOUND (also asserted below): offset + tip must stay within
    base_d, with DOVETAIL_Y_OFFSET_HEADROOM_MM of real headroom - the
    dovetail tail/groove's own Y-extent has to physically fit inside the
    piece it's carved into/protrudes from. Nothing else in this file
    checks this directly: check_socket_od_clearance only probes the
    OD-vs-groove relationship this function derives FROM (it never learns
    the resulting offset), and check_nameplate_fit/check_structural have
    no visibility into this computation at all. Confirmed live: growing
    dt_tip_w from 6.0 to 12.0mm (only +2mm) pushes offset+tip to ~46.05mm
    against base_d=45.0mm - a template that would silently split into 2
    disconnected solids in make_template() (see check_template_solid),
    previously only ever caught by accident, via check_cap_solid tripping
    over the exact same defect in cap_end's shared groove-cutter code.

    NOTE on cy: this now calls _post_center(p) (back-biased, see _post_cy -
    the nameplate-overlap fix) rather than the base_d/2 centering described
    above. dx (=cx-dt_depth) and dy (the probe's Y half-reach at the
    groove's deepest point) are UNCHANGED by that - both depend only on
    cx/r, not cy - but the resulting `offset` grows since it's
    cy + dy + tip + margin. Verified live via this function's own RESULT
    BOUND assert below (not just assumed to still hold), and independently
    via check_template_solid."""
    r = worst_case_socket_od_mm() / 2.0
    cx, cy = _post_center(p)
    assert p["dt_depth"] < p["base_w"] / 2.0 - FUSE_EMBED, (
        "dt_depth %.2fmm not < base_w/2 - FUSE_EMBED (%.2fmm) - the groove "
        "side is no longer guaranteed to be the binding constraint over "
        "the tail side, invalidating this function's groove-only "
        "reasoning (see docstring PRECONDITION)"
        % (p["dt_depth"], p["base_w"] / 2.0 - FUSE_EMBED))
    dx = cx - p["dt_depth"]
    dy = math.sqrt(max(r * r - dx * dx, 0.0))
    tip = p["dt_tip_w"] / 2.0 + p["dt_clearance"]
    # margin: buffer between the worst-case-OD probe's arc (at the
    # groove's deepest point, x=dt_depth) and the groove cutter's own near
    # Y-edge, on top of the probe-clearance geometry already computed
    # above via dx/dy. Plays the same role OD_CLEARANCE_FLOOR does for
    # check_socket_od_clearance (absorbing FDM tolerance plus this OD
    # model's own uncertainty) but sized larger - 3.0mm rather than
    # OD_CLEARANCE_FLOOR's 1.5mm - because it's buffering a multi-step
    # derived computation (probe radius -> dx -> dy -> offset) rather than
    # a single measured clearance, and because the RESULT BOUND assert
    # below is the last line of defense if this margin ever proves
    # insufficient for some future PARAMS combination; 3.0mm keeps that
    # assert from firing for every dimension this file has used to date
    # while still being a deliberate, sized number rather than an
    # arbitrary one.
    margin = 3.0
    offset = cy + dy + tip + margin
    assert offset + tip <= p["base_d"] - DOVETAIL_Y_OFFSET_HEADROOM_MM, (
        "dovetail Y-offset %.2fmm + tip %.2fmm = %.2fmm exceeds base_d "
        "%.2fmm (with %.2fmm headroom) - the piece-to-piece dovetail's own "
        "Y-extent no longer fits inside the base's depth; make_template() "
        "would produce 2 disconnected solids instead of 1 (see "
        "check_template_solid)"
        % (offset, tip, offset + tip, p["base_d"],
           DOVETAIL_Y_OFFSET_HEADROOM_MM))
    return offset


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
    untouched.

    Y-offset is computed by _dovetail_y_offset - see its docstring for why
    this is no longer a fixed fraction of base_d."""
    face = _dt_profile(p, outward=True, root_embed=FUSE_EMBED)
    solid = face.extrude(App.Vector(0, 0, p["base_h"]))
    return solid.translate(App.Vector(p["base_w"], _dovetail_y_offset(p), 0))


def make_dovetail_groove_cutter(p):
    """Cutter for the base's left (0) side - slightly oversized for snap fit.

    Must carve INTO the base's own solid (local x in [0, dt_depth], same
    +X sign as the tail), not out into empty space beyond x=0 - otherwise
    the cut is a no-op and the neighbouring piece's tail collides with
    still-solid material instead of nesting into a cavity."""
    face = _dt_profile(p, outward=True, clearance=p["dt_clearance"])
    solid = face.extrude(App.Vector(0, 0, p["base_h"] + 2))
    return solid.translate(App.Vector(0, _dovetail_y_offset(p), -1))


# --------------------------------------------------------------------------
# Geometry - nameplate pocket/block (top-of-base inset, straight press fit)
# --------------------------------------------------------------------------

def _nameplate_pocket_xy(p):
    """World XY origin (min-X, min-Y corner) of the nameplate pocket
    CAVITY footprint (nameplate_w/h plus nameplate_clearance on every
    side) - centered in X on the template (base_w/2, the same X-center the
    post itself uses).

    Y placement used to be centered in the gap between the front wall and
    the POST's own (small) front edge (_post_front_edge_y, since removed -
    see git history). That was proven live to be the wrong thing to clear:
    the post's own footprint is tiny (a few mm across), but the actual
    worst-case SOCKET sitting on that post has a ~36mm-diameter circular
    footprint, and that circle's own frontmost reach extended well past
    the post's front edge - straight into the pocket. Clearing the post
    was never the requirement; clearing the socket is.

    So this now places the pocket in the front band bounded by the front
    wall (Y=0) and the worst-case socket circle's own frontmost reach
    (cy - r, from _post_cy/_post_center) - the same two boundaries _post_
    cy solved cy against in the first place, using the identical
    NAMEPLATE_MARGIN_MM on both sides, so the pocket lands snug against
    both boundaries with real margin by construction: front edge at
    NAMEPLATE_MARGIN_MM from the wall, back edge at NAMEPLATE_MARGIN_MM
    (again) short of the socket circle's front reach. See check_socket_
    nameplate_clearance() for the live B-rep proof that the resulting
    pocket and the worst-case socket probe genuinely never overlap."""
    w = p["nameplate_w"] + 2 * p["nameplate_clearance"]
    x0 = p["base_w"] / 2.0 - w / 2.0
    y0 = NAMEPLATE_MARGIN_MM
    return x0, y0


def make_nameplate_pocket_cutter(p):
    """Plain rectangular cutter for the nameplate pocket: nameplate_w/h
    plus nameplate_clearance per side (a snug press-fit gap, not a sliding
    dovetail clearance - TUNE VIA NAMEPLATE FIT COUPON), cut straight down
    (world Z, no rotation at all - the front wall is vertical now and this
    pocket sits on the flat top face, so none of the old sloped-wall
    rotate/translate machinery applies here) exactly nameplate_t deep, so
    the nameplate block sits flush with the riser's top surface once
    seated, not proud.

    The cutter's floor sits at EXACTLY z=base_h-nameplate_t, with no
    overshoot there - that plane is a hard structural/fit requirement (the
    floor thickness left below it, checked in check_nameplate_fit, and the
    flush-with-top seating depth). Unlike the piece-to-piece groove
    cutter's own overshoot (make_dovetail_groove_cutter), which is a
    genuine pass-through cut where both ends need clearing through the
    base's full height, this pocket is a BLIND cut - only its open (top)
    end needs the same defensive overshoot pattern this file uses
    elsewhere for cutters landing exactly on a boundary plane: the cutter
    extends 1mm above z=base_h, a no-op past the riser's real top face
    (nothing there to cut), guarding against the exact-same-plane
    tangency ambiguity this file has hit before with cutters, without
    touching the floor plane at all."""
    w = p["nameplate_w"] + 2 * p["nameplate_clearance"]
    h = p["nameplate_h"] + 2 * p["nameplate_clearance"]
    t = p["nameplate_t"]
    x0, y0 = _nameplate_pocket_xy(p)
    overshoot = 1.0
    return box(w, h, t + overshoot, x0, y0, p["base_h"] - t)


def make_nameplate(p):
    """The nameplate itself: a plain rectangular block, nameplate_w x
    nameplate_h x nameplate_t, flat top and bottom, no dovetail tail or any
    other feature at all - just a snug press-fit block. Sits at local
    origin (footprint corner at (0,0), resting on the bed from z=0 to
    nameplate_t) - this IS the exported, print-ready orientation. Unlike
    the old wall-mounted dovetail nameplate, there's no sloped-wall
    geometry to reconcile with a good print orientation any more, so no
    rotation/placement trickery is needed. Blank on every face - the user
    adds their own text with their slicer's own text tool after importing
    (see module docstring)."""
    return box(p["nameplate_w"], p["nameplate_h"], p["nameplate_t"], 0, 0, 0)


def _nameplate_block_in_pocket(p, embed=0.0):
    """The ACTUAL nameplate block (real nameplate_w/h/t dimensions, no
    clearance added - the physical object that has to fit inside the
    pocket, not the oversized cutter) positioned at its real seated
    position: centered inside the pocket cavity's own footprint (so the
    clearance gap splits evenly on every side) and resting on the pocket's
    floor, flush with the riser's top surface (z=base_h) at the top.

    `embed` extends the block's BOTTOM face `embed` further down, past the
    floor plane, into the solid riser material below the pocket, while
    keeping the top face flush at z=base_h - used only by build_
    nameplate_coupon/check_fuse_overlaps for a genuine FUSE_EMBED
    volumetric overlap when fusing the block onto the template for a
    single-print coupon (see make_post's docstring for why a flush,
    zero-gap tangent touch across the whole pocket floor would be a real
    fuse defect here otherwise). check_nameplate_fit's containment check
    uses embed=0 - the real, unmodified seated position - since that check
    is a pure containment test against the cavity, not a fuse."""
    cav_x0, cav_y0 = _nameplate_pocket_xy(p)
    cav_w = p["nameplate_w"] + 2 * p["nameplate_clearance"]
    cav_h = p["nameplate_h"] + 2 * p["nameplate_clearance"]
    x0 = cav_x0 + (cav_w - p["nameplate_w"]) / 2.0
    y0 = cav_y0 + (cav_h - p["nameplate_h"]) / 2.0
    z0 = p["base_h"] - p["nameplate_t"] - embed
    height = p["nameplate_t"] + embed
    return box(p["nameplate_w"], p["nameplate_h"], height, x0, y0, z0)


def make_template(p, drive):
    """Blank template piece: base + drive-specific post (recentered, see
    make_post) + the unchanged piece-to-piece dovetail tail/groove (for
    joining templates and caps into a row) + a plain rectangular pocket cut
    straight down into the riser's top surface, in front of the post, for
    a nameplate to press into.

    NO baked text anywhere. `drive` is the only thing that varies between
    the two templates - the post's cross-section (see PARAMS's comment on
    drive_af_nominal), not the socket size, which no longer has any effect
    on this piece's geometry at all (see module docstring)."""
    body = make_base(p).fuse(make_post(p, drive))
    body = body.fuse(make_dovetail_tail(p))
    body = body.cut(make_dovetail_groove_cutter(p))
    body = body.cut(make_nameplate_pocket_cutter(p))
    return body


# --------------------------------------------------------------------------
# Geometry - end cap
# --------------------------------------------------------------------------

def make_cap(p, side):
    """side='start' has a tail on its right edge (mates leftward into the
    row); side='end' has a groove on its left edge (mates rightward). The
    opposite edge is left as make_base's own flat, square end - no cut
    there at all."""
    if side not in ("start", "end"):
        raise ValueError("side must be 'start' or 'end', got %r" % side)

    body = make_base(p)
    if side == "start":
        body = body.fuse(make_dovetail_tail(p))
    else:
        body = body.cut(make_dovetail_groove_cutter(p))
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
    printable test object, so the new pocket/block press fit can be
    physically verified before committing to printing full templates -
    same "print small coupons first" convention as build_post_coupon /
    build_dovetail_coupon. Drive doesn't matter (the pocket geometry is
    identical regardless of drive), so this uses 3-8in arbitrarily.

    Uses _nameplate_block_in_pocket(p, embed=FUSE_EMBED) - the real
    nameplate_w/h/t dimensions (no clearance reduction), positioned at its
    real seated position but with the bottom pushed FUSE_EMBED into the
    pocket floor's solid material for a genuine fuse overlap (see that
    function's docstring) - so the coupon demonstrates realistic
    proportions, not the oversized cutter. The clearance gap around the
    block's sides (nameplate_clearance) stays real air, same as build_
    dovetail_coupon's own dt_clearance gap - real interlock/fit is
    verified separately and rigorously by check_nameplate_fit()'s direct
    B-rep containment/collision checks, not by this fuse succeeding."""
    template = make_template(p, "3-8in")
    nameplate = _nameplate_block_in_pocket(p, embed=FUSE_EMBED)
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
    for the direct, tessellation-independent check that does catch it
    regardless."""
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
    cx, cy = _post_center(p)
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
    >=2mm posts/tabs). Covers the piece-to-piece dovetail connector and the
    nameplate block's own thickness. The nameplate pocket's own floor-
    thickness minimum (base_h - nameplate_t) is checked in check_
    nameplate_fit instead, alongside that pocket's other live-geometry
    checks."""
    issues = []
    dt_wall = p["dt_neck_w"] / 2.0
    if dt_wall < 1.2:
        issues.append("dovetail neck %.2fmm below 1.2mm minimum" % dt_wall)
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


def check_cap_solid(p, side):
    """Sanity check that make_cap(p, side) produces a single, valid solid.

    make_cap no longer has a corner-rounding cut (removed - the caps'
    non-dovetail end is now just make_base's own flat box end), so the
    zero-gap-tangent failure mode this check used to guard against
    (check_cap_corner_solid, see git history) can't happen any more: there
    is no cylinder/box cut near that end to potentially split the cap into
    disconnected Solids.

    Kept anyway, simplified, as cheap insurance on the one boolean op left
    in make_cap that isn't already covered elsewhere: side='end's cut of
    make_dovetail_groove_cutter(). (side='start's fuse of
    make_dovetail_tail() onto make_base() is the exact same operation
    check_fuse_overlap() already runs as "dovetail tail/base fuse" in
    check_fuse_overlaps() below, so that half doesn't need a second
    check.)"""
    cap = make_cap(p, side)
    n_solids = len(cap.Solids)
    if n_solids != 1 or not cap.isValid():
        return ("cap_%s: %d disconnected solids (expected 1), isValid=%s"
                % (side, n_solids, cap.isValid()))
    return None


def check_template_solid(p, drive):
    """Sanity check that make_template(p, drive) produces a single, valid
    solid - mirrors check_cap_solid's pattern (Solids count == 1 and
    isValid()), but applied directly to the template's own built output
    instead of relying on the caps happening to share the same
    groove-cutter code path (see check_cap_solid's docstring).

    This closes the same gap check_cap_solid closes for caps, but for
    templates specifically, and independently of whether
    _dovetail_y_offset's own RESULT BOUND assert (see its docstring)
    already catches the underlying defect first - belt and suspenders,
    matching this file's existing redundant-verification philosophy (e.g.
    check_fuse_overlap and watertight() both independently guard against
    overlapping failure classes elsewhere). A template's groove cut
    (make_dovetail_groove_cutter) and nameplate pocket cut are exactly the
    kind of boolean that can silently split a solid into disconnected
    pieces if the cutter's geometry drifts far enough - e.g. an
    unbounded _dovetail_y_offset pushing the groove band far enough
    toward the back wall to sever the base."""
    template = make_template(p, drive)
    n_solids = len(template.Solids)
    if n_solids != 1 or not template.isValid():
        return ("template_%s: %d disconnected solids (expected 1), "
                "isValid=%s" % (drive, n_solids, template.isValid()))
    return None


def check_fuse_overlaps(p):
    """Runs check_fuse_overlap()/check_cap_solid()/check_template_solid()
    across every FUSE_EMBED-dependent boolean in the design: post/base
    (x2 drives), piece-to-piece dovetail tail/base, both caps, each
    drive's template (direct single-solid/validity check on the actual
    make_template() output), and the nameplate block's own pocket-floor
    join (used by build_nameplate_coupon)."""
    issues = []
    base_shape = make_base(p)
    for drive in p["drives"]:
        issue = check_fuse_overlap(base_shape, make_post(p, drive),
                                    "post/base fuse (%s)" % drive)
        if issue:
            issues.append(issue)
        issue = check_template_solid(p, drive)
        if issue:
            issues.append(issue)
    issue = check_fuse_overlap(base_shape, make_dovetail_tail(p),
                                "dovetail tail/base fuse")
    if issue:
        issues.append(issue)
    for side in ("start", "end"):
        issue = check_cap_solid(p, side)
        if issue:
            issues.append(issue)

    template = make_template(p, "3-8in")
    embedded_block = _nameplate_block_in_pocket(p, embed=FUSE_EMBED)
    issue = check_fuse_overlap(template, embedded_block,
                                "nameplate block/pocket-floor fuse")
    if issue:
        issues.append(issue)
    return issues


def check_socket_od_clearance(p):
    """Permanent regression guard for the base footprint (see PARAMS's
    base_w/base_d comment) against the worst-case socket size,
    SOCKET_OD_WORST_CASE_MM (36.0mm, the user's own stated figure for the
    largest 25mm/1in socket - see that constant's comment for why it's
    checked instead of, but cross-checked against, the two-point linear
    estimate). The base footprint doesn't depend on drive either, so one
    check covers both templates.

    Builds a real Part.makeCylinder probe of the worst-case OD, centered at
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
    cx, cy = _post_center(p)
    footprint = Part.makeBox(p["base_w"], p["base_d"], 500,
                              App.Vector(0, 0, -10))
    tail = make_dovetail_tail(p)
    groove = make_dovetail_groove_cutter(p)

    estimated = estimated_socket_od_mm(25.4)  # 1in SAE, cross-check only
    od = worst_case_socket_od_mm()
    r = od / 2.0
    probe = Part.makeCylinder(r, p["post_h"] + 20,
                               App.Vector(cx, cy, p["base_h"]))
    outside = probe.cut(footprint).Volume
    if outside > 1e-6:
        issues.append(
            "worst-case OD %.2fmm: probe extends %.2f mm3 past the base "
            "footprint" % (od, outside))
    tail_overlap = probe.common(tail).Volume
    if tail_overlap > 1e-6:
        issues.append(
            "worst-case OD %.2fmm: probe overlaps dovetail tail by "
            "%.4f mm3" % (od, tail_overlap))
    groove_overlap = probe.common(groove).Volume
    if groove_overlap > 1e-6:
        issues.append(
            "worst-case OD %.2fmm: probe overlaps dovetail groove cutter "
            "by %.4f mm3" % (od, groove_overlap))
    left = cx - r
    right = p["base_w"] - cx - r
    front = cy - r
    back = p["base_d"] - cy - r
    margin = min(left, right, front, back)
    print("  worst-case socket: OD %.2fmm (authoritative %.2fmm, 1in SAE "
          "estimate %.2fmm) -> clearance margin %.2fmm "
          "(left=%.2f right=%.2f front=%.2f back=%.2f)"
          % (od, SOCKET_OD_WORST_CASE_MM, estimated, margin,
             left, right, front, back))
    if margin <= OD_CLEARANCE_FLOOR:
        issues.append(
            "worst-case OD: clearance margin %.2fmm at or below the "
            "%.2fmm floor - base footprint too tight for this socket's "
            "outer diameter" % (margin, OD_CLEARANCE_FLOOR))
    return issues


def check_socket_nameplate_clearance(p):
    """Permanent regression guard for the actual design flaw this file's
    post/nameplate repositioning fixed: a real worst-case socket sitting on
    the post visually/physically overlapping the nameplate pocket, making
    the label unreadable while that socket is stored.

    Builds the same worst-case-OD probe cylinder check_socket_od_clearance
    builds (centered on the post's real _post_center(p), radius
    worst_case_socket_od_mm()/2.0, spanning the post's full height plus
    headroom above the riser top) and the real nameplate pocket cavity
    cutter (make_nameplate_pocket_cutter - the actual cut geometry,
    already inflated by nameplate_clearance, not the smaller raw
    nameplate_w/h footprint), and asserts their real B-rep intersection
    (probe.common(cavity).Volume) is exactly 0.0 - not merely small.

    This is the direct proof the fix works: previously (post centered at
    cy=base_d/2=22.5mm), this exact same kind of probe-vs-pocket overlap
    was nonzero (the pocket's Y-span sat inside the probe's own Y-reach -
    see NAMEPLATE_MARGIN_MM's docstring for the discovered numbers). Any
    future PARAMS change that reintroduces that overlap (e.g. shrinking
    NAMEPLATE_MARGIN_MM, growing the nameplate, or hand-editing cy back to
    a fixed centering) trips this check immediately."""
    issues = []
    cx, cy = _post_center(p)
    r = worst_case_socket_od_mm() / 2.0
    probe = Part.makeCylinder(r, p["post_h"] + 20,
                               App.Vector(cx, cy, p["base_h"]))
    cavity = make_nameplate_pocket_cutter(p)
    overlap = probe.common(cavity).Volume
    print("  worst-case socket probe (OD %.2fmm) vs nameplate pocket "
          "cavity: overlap = %.6f mm3 (must be ~0)" % (r * 2, overlap))
    # >1e-6, not >0.0 - matches every other "must not overlap" check in this
    # file (check_socket_od_clearance, check_nameplate_fit): a near-tangent
    # OCC boolean can return a tiny spurious nonzero volume even when two
    # solids don't really overlap, so a bare >0.0 risks a flaky failure if
    # this gap is ever narrowed. Today's real gap is 2.25mm (NAMEPLATE_
    # MARGIN_MM), nowhere near this floor - verified live, not tangency.
    if overlap > 1e-6:
        issues.append(
            "worst-case socket probe overlaps the nameplate pocket cavity "
            "by %.6f mm3 - a large socket resting on the post would sit "
            "on top of the nameplate" % overlap)
    return issues


def check_nameplate_fit(p):
    """Direct B-rep verification of the top-of-base pocket/block nameplate
    mechanism - same "build real geometry, verify with real booleans"
    discipline as check_fuse_overlap/check_cap_solid, replacing the old
    dovetail-slot check (see git history) now that the mechanism itself
    has changed from a wall-mounted dovetail slide to a straight-down
    press-fit pocket in the riser's top face.

      1. CONTAINMENT - the ACTUAL nameplate block (make_nameplate's real
         nameplate_w/h/t dimensions, no clearance added - the physical
         object that has to fit, not the oversized cutter) at its real
         seated position (_nameplate_block_in_pocket, embed=0) should sit
         essentially 100% inside the pocket cavity (make_nameplate_
         pocket_cutter) - unlike the old dovetail check's ~90% threshold
         (that gap was the tail's own intentional FUSE_EMBED root
         overlap; this check has no embed baked into the seated position
         at all, so a correct design should land at, or extremely close
         to, 100%).
      2. COLLISION - the pocket cavity itself must not collide with either
         drive's post or either half of the piece-to-piece dovetail (0.0
         mm3 overlap expected for all of them) - they sit in different
         regions of the base, but this checks the real geometry rather
         than assuming from separation by eye.
      3. FOOTPRINT - the pocket cavity's own X/Y extent stays within the
         template's footprint with real margin on the front wall side and
         both left/right sides (the back side is bounded by the post
         collision check above instead, since the post sits much closer
         than the back wall itself does).
      4. FLOOR - base_h - nameplate_t (the solid riser material left
         below the pocket) clears a minimum floor thickness, so a future
         PARAMS change can't silently cut the pocket through the whole
         riser without this check catching it - written generally (as a
         formula, not a hardcoded pass) so it stays meaningful if base_h
         or nameplate_t change later.
    """
    issues = []
    cavity = make_nameplate_pocket_cutter(p)
    block = _nameplate_block_in_pocket(p, embed=0.0)

    block_vol = block.Volume
    contained_vol = block.common(cavity).Volume
    frac = contained_vol / block_vol if block_vol > 0 else 0.0
    print("  nameplate block/pocket containment: %.4f of %.4f mm3 block "
          "volume (%.1f%%)" % (contained_vol, block_vol, frac * 100))
    if frac < 0.999:
        issues.append(
            "nameplate block only %.1f%% contained in the pocket cavity "
            "(expected ~100%% - a plain press fit with no FUSE_EMBED baked "
            "into the seated position) - pocket/block geometry likely "
            "misaligned" % (frac * 100))

    for drive in p["drives"]:
        post_overlap = cavity.common(make_post(p, drive)).Volume
        if post_overlap > 1e-6:
            issues.append(
                "nameplate pocket overlaps the %s post by %.4f mm3"
                % (drive, post_overlap))

    tail_overlap = cavity.common(make_dovetail_tail(p)).Volume
    if tail_overlap > 1e-6:
        issues.append(
            "nameplate pocket overlaps the piece-to-piece dovetail tail by "
            "%.4f mm3" % tail_overlap)
    groove_overlap = cavity.common(make_dovetail_groove_cutter(p)).Volume
    if groove_overlap > 1e-6:
        issues.append(
            "nameplate pocket overlaps the piece-to-piece dovetail groove "
            "cutter by %.4f mm3" % groove_overlap)

    bb = cavity.BoundBox
    margin_left = bb.XMin
    margin_right = p["base_w"] - bb.XMax
    margin_front = bb.YMin
    print("  nameplate pocket footprint: X[%.2f,%.2f] Y[%.2f,%.2f] within "
          "base_w=%.1f base_d=%.1f -> margin left=%.2f right=%.2f "
          "front=%.2f" % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, p["base_w"],
                           p["base_d"], margin_left, margin_right,
                           margin_front))
    if min(margin_left, margin_right, margin_front) < 2.0:
        issues.append(
            "nameplate pocket footprint margin too tight: left=%.2f "
            "right=%.2f front=%.2f (expected >=2.0mm on each)"
            % (margin_left, margin_right, margin_front))

    floor = p["base_h"] - p["nameplate_t"]
    print("  nameplate pocket floor thickness: %.2fmm" % floor)
    if floor < 2.0:
        issues.append(
            "nameplate pocket floor %.2fmm below 2.0mm minimum - pocket "
            "cuts too close through the riser" % floor)

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
              "both caps and both drives' templates are single valid "
              "solids, nameplate block/pocket-floor)" % len(PARAMS["drives"]))

    print("\n--- nameplate pocket/block fit self-check "
          "(real B-rep containment/collision/footprint/floor) ---")
    nameplate_fit_issues = check_nameplate_fit(PARAMS)
    if nameplate_fit_issues:
        for issue in nameplate_fit_issues:
            print("NAMEPLATE-FIT: %s" % issue)
    else:
        print("nameplate block is essentially fully contained in the "
              "template's pocket cavity, the pocket collides with neither "
              "post nor the piece-to-piece dovetail, the pocket stays "
              "within the template's footprint with real margin, and the "
              "floor left below the pocket clears the minimum thickness")

    print("\n--- socket OD clearance self-check "
          "(real cylinder probe, worst-case OD) ---")
    od_clearance_issues = check_socket_od_clearance(PARAMS)
    if od_clearance_issues:
        for issue in od_clearance_issues:
            print("OD-CLEARANCE: %s" % issue)
    else:
        print("the worst-case estimated socket OD clears the base "
              "footprint (and stays clear of the dovetail tail/groove) by "
              "more than the %.2fmm floor" % OD_CLEARANCE_FLOOR)

    print("\n--- socket/nameplate overlap self-check "
          "(real cylinder probe vs real pocket cavity, direct B-rep) ---")
    socket_nameplate_issues = check_socket_nameplate_clearance(PARAMS)
    if socket_nameplate_issues:
        for issue in socket_nameplate_issues:
            print("SOCKET-NAMEPLATE: %s" % issue)
    else:
        print("the worst-case socket probe and the nameplate pocket cavity "
              "have exactly zero volumetric overlap - a large socket "
              "resting on the post can no longer sit on top of the label")

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
        "nameplate pocket/block fit check failed, see report above")
    assert not od_clearance_issues, (
        "socket OD clearance check failed, see report above")
    assert not socket_nameplate_issues, (
        "socket/nameplate overlap check failed, see report above")
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
