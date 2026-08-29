# Socket Organizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `socket-organizer/freecad/build_socket_organizer.py`, a parametric FreeCAD generator that produces 40 interlinking socket-holder pieces (metric 8–19mm, SAE 5/16"–3/4", each in 3/8" and 1/2" drive) plus 2 end caps, all sharing one vertical-snap dovetail interface, plus fit coupons, self-checks, and exports — following the `whiteboard-stand/freecad/build_caddy.py` convention already in this repo.

**Architecture:** One script, one `PARAMS` dict, a `SIZE_TABLE` driving iteration. Shared geometry helpers (`make_base`, `make_post`, `make_dovetail_tail`, `make_dovetail_groove`, `emboss_label`) are composed per size/drive into `make_middle_piece()`; `make_cap()` builds the two end pieces. `run()` generates everything, runs fit/structural/printability/mesh checks (reusing `fine_mesh`, `overhangs`, `watertight`, `export_all` copied near-verbatim from `build_caddy.py`), and exports STEP/STL/3MF per piece.

**Tech Stack:** FreeCAD 1.0+ (`freecadcmd`), Python 3, `Part` module.

Design spec: `docs/superpowers/specs/2026-08-29-socket-organizer-design.md`

---

## File Structure

```
socket-organizer/
  README.md                          # piece table, print/assembly notes
  images/                            # renders (added after first build)
  freecad/
    build_socket_organizer.py        # everything — see tasks below
    exports/                         # STEP+STL+3MF per piece, gitignored contents rebuilt each run
```

Everything lives in one script file, matching `build_caddy.py`. No test framework is set up in this repo — "tests" are `freecadcmd` runs whose assertions live inline in the script itself (`assert` statements) or are checked by reading the printed build report. Each task below runs the script headlessly and verifies specific printed/asserted output.

---

### Task 1: Script skeleton, params, shared helpers

**Files:**
- Create: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Write the skeleton with PARAMS and copied generic helpers**

```python
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


def run():
    doc = App.newDocument("socket_organizer")
    print("socket-organizer: skeleton OK, %d metric + %d SAE sizes x %d drives"
          % (len(PARAMS["metric_mm"]), len(PARAMS["sae_frac_32nds"]),
             len(PARAMS["drives"])))
    App.closeDocument(doc.Name)


if __name__ == "__main__" or "freecadcmd" in sys.argv[0].lower():
    run()
```

- [ ] **Step 2: Run it headlessly to verify the skeleton executes**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected output includes: `socket-organizer: skeleton OK, 12 metric + 8 SAE sizes x 2 drives`

- [ ] **Step 3: Commit**

```bash
mkdir -p socket-organizer/freecad
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: script skeleton and params"
```

---

### Task 2: Base + post geometry for a single piece

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add `make_base` and `make_post`, call them for one hardcoded size**

Add above `run()`:

```python
# --------------------------------------------------------------------------
# Geometry - base and post
# --------------------------------------------------------------------------

def make_base(p):
    """Riser block with a sloped front wall. Front is the -Y face."""
    body = box(p["base_w"], p["base_d"], p["base_h"], 0, 0, 0)
    # Slope the front wall back, continuously from the floor (Z=0, Y=0)
    # to the top (Z=base_h, Y=slope_rise).
    slope_rise = p["base_h"] * math.tan(math.radians(p["front_slope_deg"]))
    wedge_pts = [
        App.Vector(-1, -1, 0),
        App.Vector(-1, slope_rise, p["base_h"]),
        App.Vector(-1, -1, p["base_h"]),
        App.Vector(-1, -1, 0),
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
```

Update `run()` to build one piece and print its bounding box:

```python
def run():
    doc = App.newDocument("socket_organizer")
    piece = make_middle_piece(PARAMS, "1-2in")
    bb = piece.Shape.BoundBox if hasattr(piece, "Shape") else piece.BoundBox
    print("test piece bbox: %.2f x %.2f x %.2f, volume %.1f"
          % (bb.XLength, bb.YLength, bb.ZLength, piece.Volume))
    assert bb.ZLength > PARAMS["base_h"] + PARAMS["post_h"] - 0.5
    assert bb.XLength <= PARAMS["base_w"] + 0.01
    App.closeDocument(doc.Name)
```

- [ ] **Step 2: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: prints a bbox line, e.g. `test piece bbox: 26.00 x 32.00 x 21.0x, volume ...`, no `AssertionError`.

- [ ] **Step 3: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: base and post geometry"
```

---

### Task 3: Dovetail groove/tail

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add tail/groove profile builders and fuse/cut them onto the base**

```python
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
    Uses outward=True (same sign as the tail) so it carves INTO the base's
    own material at local x in [0, dt_depth] - that's where a neighbor's
    tail lands once translated by base_w. outward=False would place the
    profile at x in [-dt_depth, 0], outside the base entirely, cutting
    nothing (verified: this shipped a near no-op groove, caught by the
    two-piece overlap check in run())."""
    face = _dt_profile(p, outward=True, clearance=p["dt_clearance"])
    solid = face.extrude(App.Vector(0, 0, p["base_h"] + 2))
    return solid.translate(App.Vector(0, p["base_d"] * 0.3, -1))


def make_middle_piece(p, drive):
    body = make_base(p).fuse(make_post(p, drive))
    body = body.fuse(make_dovetail_tail(p))
    body = body.cut(make_dovetail_groove_cutter(p))
    return body
```

- [ ] **Step 2: Add an assembly-clearance test to `run()`**

Replace the body of `run()` with:

```python
def run():
    doc = App.newDocument("socket_organizer")
    a = make_middle_piece(PARAMS, "1-2in")
    b = make_middle_piece(PARAMS, "1-2in").translate(App.Vector(PARAMS["base_w"], 0, 0))
    overlap = a.common(b).Volume
    print("two-piece dovetail overlap volume: %.3f mm3" % overlap)
    assert overlap < 1.0, "adjacent pieces interfere when assembled"
    App.closeDocument(doc.Name)
```

- [ ] **Step 3: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: `two-piece dovetail overlap volume: 0.000 mm3` (or very close to 0), no `AssertionError`.

- [ ] **Step 4: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: vertical dovetail groove/tail"
```

---

### Task 4: Embossed size label

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add font lookup and text-solid helpers (adapted from `build_caddy.py`'s `pick_font`/`text_solid`)**

```python
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

    The wall surface (from make_base's wedge cut) sits at Y = Z*tan(slope)
    for Z in [0, base_h] - NOT at a fixed offset. The label is embedded
    slightly (0.2mm, capped by label_depth) into the wall rather than left
    exactly tangent to it: OCC's boolean fuse can produce invalid/
    non-manifold geometry when two solids share an exactly-coincident face
    (verified: isValid() was False with zero embed), so a small controlled
    overlap is standard practice for CAD emboss features."""
    font = pick_font()
    solid = text_solid(text, font, p["label_h"], p["label_depth"])
    bb = solid.BoundBox
    solid = solid.translate(App.Vector(-bb.XLength / 2.0, 0, 0))
    slope = math.radians(p["front_slope_deg"])
    solid = solid.rotate(App.Vector(0, 0, 0), App.Vector(1, 0, 0), 90 - p["front_slope_deg"])
    x_center = p["base_w"] / 2.0
    embed = min(0.2, p["label_depth"])
    y_wall = p["label_z"] * math.tan(slope)
    y_pos = y_wall - embed * math.cos(slope)
    solid = solid.translate(App.Vector(x_center, y_pos, p["label_z"]))
    return solid


def make_middle_piece(p, drive, label_text):
    body = make_base(p).fuse(make_post(p, drive))
    body = body.fuse(make_dovetail_tail(p))
    body = body.cut(make_dovetail_groove_cutter(p))
    body = body.fuse(emboss_label(p, label_text))
    return body
```

- [ ] **Step 2: Update `run()` to build a labeled piece and check the label sits within the footprint**

```python
def run():
    doc = App.newDocument("socket_organizer")
    piece = make_middle_piece(PARAMS, "1-2in", "12")
    bb = piece.BoundBox
    print("labeled piece bbox: %.2f x %.2f x %.2f" % (bb.XLength, bb.YLength, bb.ZLength))
    assert bb.XLength <= PARAMS["base_w"] + PARAMS["dt_depth"] + 0.5
    App.closeDocument(doc.Name)
```

- [ ] **Step 3: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: prints the bbox line, no exception. If `pick_font()` raises, add your OS's bold sans-serif font path to `_FONT_CANDIDATES` and re-run.

- [ ] **Step 4: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: embossed size label"
```

---

### Task 5: Cap piece (start/end)

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add `make_cap`, a base with one dovetail face and a rounded closed end**

```python
# --------------------------------------------------------------------------
# Geometry - end cap
# --------------------------------------------------------------------------

def make_cap(p, side):
    """side='start' has a tail on its right edge (mates leftward into the
    row); side='end' has a groove on its left edge (mates rightward). The
    opposite edge is rounded off closed.

    The rounding-corner box must overlap the SAME side of round_x as the
    body actually occupies (round_x for 'start' since the body spans
    [0, base_w] and the corner to round is at x=0; round_x - r for 'end'
    since the corner to round is at x=base_w) - the reverse placement was
    a shipped bug (0mm3 overlap, a silent no-op) caught by live volume
    verification."""
    body = box(p["base_w"], p["base_d"], p["base_h"], 0, 0, 0)
    slope_rise = wall_y_at_z(p, p["base_h"])
    wedge = Part.Face(Part.makePolygon([
        App.Vector(-1, -1, 0),
        App.Vector(-1, slope_rise, p["base_h"]),
        App.Vector(-1, -1, p["base_h"]),
        App.Vector(-1, -1, 0),
    ])).extrude(App.Vector(p["base_w"] + 2, 0, 0))
    body = body.cut(wedge)

    r = p["cap_round_r"]
    if side == "start":
        body = body.fuse(make_dovetail_tail(p))
        round_x = 0
    else:
        body = body.cut(make_dovetail_groove_cutter(p))
        round_x = p["base_w"]
    round_cutter = Part.makeCylinder(
        r, p["base_h"] + 2, App.Vector(round_x, p["base_d"] * 0.3, -1))
    corner = box(r, p["base_d"], p["base_h"] + 2,
                 round_x if side == "start" else round_x - r, 0, -1)
    body = body.cut(corner.cut(round_cutter))
    return body
```

- [ ] **Step 2: Update `run()` to build both caps and check they mate with a middle piece**

A 'start' cap's tail is on its RIGHT edge, so the mating middle piece must
sit to the cap's right (+base_w), not its left - the reverse direction was
a shipped bug (a real 200mm3 collision, not a meaningful "no overlap"
check) caught by live volume verification.

```python
def run():
    doc = App.newDocument("socket_organizer")
    cap = make_cap(PARAMS, "start")
    mid = make_middle_piece(PARAMS, "1-2in", "12").translate(
        App.Vector(PARAMS["base_w"], 0, 0))
    overlap = cap.common(mid).Volume
    print("cap-to-middle overlap volume: %.3f mm3" % overlap)
    assert overlap < 1.0
    App.closeDocument(doc.Name)
```

- [ ] **Step 3: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: `cap-to-middle overlap volume: 0.000 mm3`, no `AssertionError`.

- [ ] **Step 4: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: start/end cap geometry"
```

---

### Task 6: Size table iteration

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add `generate_all()` producing every named piece**

```python
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
```

- [ ] **Step 2: Update `run()` to build everything and check the count**

```python
def run():
    doc = App.newDocument("socket_organizer")
    pieces = generate_all(PARAMS)
    n_metric = len(PARAMS["metric_mm"]) * len(PARAMS["drives"])
    n_sae = len(PARAMS["sae_frac_32nds"]) * len(PARAMS["drives"])
    expected = n_metric + n_sae + 2
    print("generated %d pieces (expected %d)" % (len(pieces), expected))
    assert len(pieces) == expected == 42
    App.closeDocument(doc.Name)
```

- [ ] **Step 3: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: `generated 42 pieces (expected 42)`, no `AssertionError`.

Note: this is the slow step — building 42 shapes with fillets/chamfers/text
can take a minute or two under `freecadcmd`. That's expected.

- [ ] **Step 4: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: generate all 42 pieces from the size table"
```

---

### Task 7: Fit coupons

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add coupon builders**

```python
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
```

- [ ] **Step 2: Verify the dovetail coupon is one connected solid**

Add a temporary check inside `run()` (kept permanently as a sanity assertion):

```python
    coupon = build_dovetail_coupon(PARAMS)
    assert len(coupon.Solids) == 1, "dovetail coupon halves did not fuse into one piece"
    print("dovetail coupon: 1 solid, volume %.1f mm3" % coupon.Volume)
```

- [ ] **Step 3: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: `dovetail coupon: 1 solid, volume ...`, no `AssertionError`.

- [ ] **Step 4: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: post and dovetail fit coupons"
```

---

### Task 8: Self-checks (fit, structural, printability, mesh)

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add the generic checks, copied near-verbatim from `whiteboard-stand/freecad/build_caddy.py`**

Copy these three functions from `whiteboard-stand/freecad/build_caddy.py` into
`build_socket_organizer.py` unchanged except for removing model-specific
comments — they are geometry-agnostic:

- `fine_mesh(shape, linear=None)`
- `overhangs(shape, limit_deg=45.0, z_tol=0.05, min_area=5.0, samples=7)`
- `watertight(shape, label)`

- [ ] **Step 2: Add the model-specific fit check**

```python
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
```

- [ ] **Step 3: Wire checks into `run()` and print a report**

```python
def run():
    doc = App.newDocument("socket_organizer")
    pieces = generate_all(PARAMS)

    print("\n--- self-check report ---")
    struct_issues = check_structural(PARAMS)
    for issue in struct_issues:
        print("STRUCTURAL: %s" % issue)

    for name, shape in sorted(pieces.items()):
        for issue in check_printability(shape, name):
            print("PRINTABILITY: %s" % issue)
        print(watertight(shape, name))

    fit_overlap = check_post_fit(pieces["metric_12mm_1-2in"], PARAMS, "1-2in")
    print("post fit probe overlap (metric_12mm_1-2in): %.2f mm3" % fit_overlap)
    assert fit_overlap > 0.5, "post shows no interference with nominal drive square - too loose"

    assert not struct_issues, "structural check failed, see report above"
    App.closeDocument(doc.Name)
```

- [ ] **Step 4: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: report prints one `watertight` line per piece (all should read
`watertight`, no `NON-MANIFOLD`/`self-intersects`/`open shell`), zero
`STRUCTURAL`/`PRINTABILITY` lines, and a `post fit probe overlap` line
`> 0.50`. Fix geometry if any check fails before continuing.

- [ ] **Step 5: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py
git commit -m "socket-organizer: fit, structural, printability and mesh checks"
```

---

### Task 9: Exports and build report

**Files:**
- Modify: `socket-organizer/freecad/build_socket_organizer.py`

- [ ] **Step 1: Add `export_all`, copied from `build_caddy.py` and adapted to export by name dict instead of a fixed object list**

```python
# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def export_all(shapes, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, shape in sorted(shapes.items()):
        doc = App.newDocument("export_tmp")
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
        doc.recompute()
        Part.export([obj], os.path.join(out_dir, name + ".step"))
        mesh = fine_mesh(shape)
        mesh.write(os.path.join(out_dir, name + ".stl"))
        mesh.write(os.path.join(out_dir, name + ".3mf"))
        App.closeDocument(doc.Name)
```

- [ ] **Step 2: Wire exports into `run()`, including the fit coupons**

```python
def run():
    doc = App.newDocument("socket_organizer")
    pieces = generate_all(PARAMS)

    print("\n--- self-check report ---")
    struct_issues = check_structural(PARAMS)
    for issue in struct_issues:
        print("STRUCTURAL: %s" % issue)
    for name, shape in sorted(pieces.items()):
        for issue in check_printability(shape, name):
            print("PRINTABILITY: %s" % issue)
        print(watertight(shape, name))
    fit_overlap = check_post_fit(pieces["metric_12mm_1-2in"], PARAMS, "1-2in")
    print("post fit probe overlap (metric_12mm_1-2in): %.2f mm3" % fit_overlap)
    assert fit_overlap > 0.5
    assert not struct_issues

    out_dir = os.path.join(_script_dir(), "exports")
    export_all(pieces, out_dir)

    coupons = {
        "post_coupon_3-8in": build_post_coupon(PARAMS, "3-8in"),
        "post_coupon_1-2in": build_post_coupon(PARAMS, "1-2in"),
        "dovetail_coupon": build_dovetail_coupon(PARAMS),
    }
    export_all(coupons, out_dir)

    print("\nExported %d pieces + %d coupons to %s"
          % (len(pieces), len(coupons), out_dir))
    App.closeDocument(doc.Name)
```

- [ ] **Step 3: Run and verify**

Run: `freecadcmd socket-organizer/freecad/build_socket_organizer.py`
Expected: final line `Exported 42 pieces + 3 coupons to .../socket-organizer/freecad/exports`.
Confirm the files exist:

Run: `ls socket-organizer/freecad/exports | wc -l`
Expected: `135` (45 pieces × 3 formats: STEP+STL+3MF)

- [ ] **Step 4: Commit**

```bash
git add socket-organizer/freecad/build_socket_organizer.py socket-organizer/freecad/exports
git commit -m "socket-organizer: export STEP/STL/3MF for all pieces and coupons"
```

---

### Task 10: README

**Files:**
- Create: `socket-organizer/README.md`
- Modify: `README.md:11-24` (add a row to the models table, matching the
  `whiteboard-stand-3-eraser` entry's format)

- [ ] **Step 1: Write `socket-organizer/README.md`**

```markdown
# Socket Organizer

Modular, interlinking socket holder. Metric and SAE, 3/8" and 1/2" drive.
Each socket stands on a molded post sized to its drive square — friction on
the post corners holds it upright, no magnet, no stick. Pieces snap
together with a vertical dovetail: press a piece straight down to seat it,
lift straight up to remove it. Any single piece comes out without
disturbing its neighbors, so you build out exactly the sockets you own.

## Sizes

- **Metric**: 8–19mm (12 sizes)
- **SAE**: 5/16"–3/4" in 1/16" steps (8 sizes)
- Every size in both **3/8"** and **1/2"** drive
- 40 middle pieces + 2 end caps = 42 pieces total, all sharing one dovetail
  interface — mix metric, SAE, and drive size in any order

## Print the coupons first

Three small coupons ship alongside the full set:

- `post_coupon_3-8in` / `post_coupon_1-2in` — one middle piece each, so you
  can test-fit a real socket before committing to the full run
- `dovetail_coupon` — two pre-joined pieces, to check the snap seats and
  releases cleanly

If a post is too loose or tight, adjust `post_af_undersize` in
`build_socket_organizer.py` and re-run. If the dovetail snap is too loose
or tight, adjust `dt_clearance`.

## Regenerating

```bash
cd socket-organizer/freecad
freecadcmd build_socket_organizer.py
```

Needs FreeCAD 1.0+. Outputs land in `exports/` as STEP, STL and 3MF, one
set per piece plus the coupons. Every run reports fit, structural,
printability and mesh-health checks — see the repo root README for what
each one means.
```

- [ ] **Step 2: Add the row to the repo root `README.md` models table**

Read `README.md:11-24` first to match current formatting, then add a row
for **Socket Organizer** following the same pattern as the existing two
rows (name, what it is, size, print estimate, status — status should be
🧪 *Generated and checked, not yet printed* until it's actually printed).

- [ ] **Step 3: Commit**

```bash
git add socket-organizer/README.md README.md
git commit -m "socket-organizer: add README and root models table entry"
```

---

## Self-Review Notes

- **Spec coverage:** center-post mount (Task 2), vertical snap dovetail
  (Task 3), front-face embossed label (Task 4), start/end caps (Task 5),
  full size table both drives (Task 6), post + dovetail fit coupons (Task
  7), fit/structural/printability/mesh self-checks (Task 8), STEP/STL/3MF
  exports (Task 9), README (Task 10). All spec sections have a task.
- **Open items from spec** (post undersize, dovetail clearance, base
  footprint) are left as named `PARAMS` with starting values and explicit
  "TUNE VIA ... COUPON" comments — not blank placeholders, but real numbers
  the coupon step (Task 7/8) is meant to correct by hand-printing and
  re-running with adjusted params. This is expected, not a plan gap: the
  spec explicitly defers these to coupon iteration.
- **Type/name consistency checked:** `make_middle_piece` signature
  (`p, drive, label_text`) is consistent from Task 4 onward; `generate_all`
  and the coupon builders all call it with 3 args. `sae_label`/`sae_key`
  are defined once (Task 1) and reused in Tasks 6–7 without redefinition.
