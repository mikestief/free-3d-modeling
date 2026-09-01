# Socket Organizer

Modular, interlinking socket holder. Metric and SAE, 3/8" and 1/2" drive —
one blank template per drive fits every socket size in that drive, so
there's no per-size piece to generate, print, or manage. Each socket
stands on a molded post sized to its drive square — friction on the post
corners holds it upright, no magnet, no stick. Pieces snap together with a
vertical dovetail: press a piece straight down to seat it, lift straight
up to remove it. Any single piece comes out without disturbing its
neighbors, so you build out exactly the sockets you own.

| | |
|---|---|
| Size | 43 × 53 × 21 mm per template (base + post, before the socket itself) |
| Print time | Small parts — roughly 15–25 min per template on a typical FDM printer, a couple minutes per nameplate; several print easily on one plate |
| Material | A few grams per piece in PLA or PETG |
| Supports | None |
| Bed needed | Any — pieces are small and print individually or in batches |
| Status | Generated and checked (fit/printability/mesh); not yet printed |

## 5 piece types, not 61

This used to be a size table: one uniquely-labeled piece per metric/SAE
size × drive combination. It doesn't scale — every new size means
regenerating, re-checking, and reprinting the whole set. The insight that
replaced it: a socket's post only depends on the **drive** (3/8" af=9.53mm
vs. 1/2" af=12.70mm), never on which socket size sits on it — every socket
of a given drive shares the same square drive-hole. So one blank template
per drive already physically fits every socket size that drive makes.
Removing the size label removes the need for per-size pieces entirely.

The whole system is now exactly 5 piece types:

- **`template_3-8in`** / **`template_1-2in`** — a blank base + post,
  drive-specific, with the usual piece-to-piece dovetail for joining into
  a row. No text baked into the geometry anywhere. Instead, a small
  dovetail **slot** sits on the sloped front wall, in the spot the old
  embossed label used to occupy.
- **`cap_start`** / **`cap_end`** — unchanged row-end pieces. Always were
  blank, still are.
- **`nameplate_template`** — a single small blank plaque with a dovetail
  **tail** on its back that slides into a template's slot. Print as many
  as you want, and label each one yourself.

A row is any number of templates snapped together, with one cap on each
end — the caps close off the exposed dovetail edge so the finished row
doesn't have a raw connector sticking out. Mix metric, SAE, and drive size
in any order; the templates don't care, since none of them are sized to a
specific socket in the first place.

## Labeling — your slicer, not this generator

This generator no longer bakes any size text into the geometry at all.
Instead, each template has a small dovetail slot molded into its front
wall, and the separate `nameplate_template` piece has a matching tail on
its back — press a nameplate down into a template's slot (same
press-down-to-seat, lift-straight-up-to-remove mechanic as the
piece-to-piece dovetail, just lighter-duty and mounted on the sloped wall
instead of the side) and it locks in place.

Print a stack of blank nameplates, then use your slicer's own text tool
(Bambu Studio, OrcaSlicer, PrusaSlicer, etc. all have one) to add whatever
label you want — `10`, `5/16`, `1/2" DR`, anything — directly on each
nameplate before you print it. Snap it onto a template once it's done.
This means:

- Any size, any label text, any language — nothing about it is
  constrained by this generator any more.
- If you print a nameplate wrong or want to relabel a slot, just print
  another nameplate — the template underneath never changes.
- No multi-color printer required. If you want the label in a different
  color, that's your slicer's per-object color assignment on the
  nameplate object, same as coloring any other single print differently
  from the rest of your plate — this generator has no multi-color export
  path any more, since there's only one blank object per nameplate to
  color in the first place.

## Print the coupons first

Four small coupons ship alongside the 5 real pieces:

- [`freecad/exports/post_coupon_3-8in.3mf`](freecad/exports/post_coupon_3-8in.3mf) /
  [`freecad/exports/post_coupon_1-2in.3mf`](freecad/exports/post_coupon_1-2in.3mf) —
  one template each (same geometry as the real piece — there's no
  separate "coupon-only" version any more, since a template is already a
  single small part), so you can test-fit a real socket before printing a
  full row.
- [`freecad/exports/dovetail_coupon.3mf`](freecad/exports/dovetail_coupon.3mf) —
  two pre-joined templates, to check the piece-to-piece snap seats and
  releases cleanly.
- [`freecad/exports/nameplate_coupon.3mf`](freecad/exports/nameplate_coupon.3mf) —
  one template with one nameplate pre-seated in its slot, fused into a
  single printable test object, to check the new nameplate slot/tail fit
  before committing to a full print run. This is brand new geometry with
  no prior print history — verify it fits by hand before relying on it.

STL and STEP versions are alongside them in
[`freecad/exports/`](freecad/exports/), along with all 5 real pieces.

If a post is too loose or tight, adjust `post_af_undersize` in
[`freecad/build_socket_organizer.py`](freecad/build_socket_organizer.py) and
re-run. If the piece-to-piece dovetail snap is too loose or tight, adjust
`dt_clearance`. If the nameplate slot/tail is too loose, tight, or doesn't
seat right, adjust `nameplate_dt_neck_w` / `nameplate_dt_tip_w` /
`nameplate_dt_depth` / `nameplate_dt_clearance` — these four are a first
engineering pass with no prior print history behind them (unlike
`dt_clearance`, which has years of this file's own history and real
prints backing it), so treat the coupon test as the real source of truth,
not the numbers themselves.

## Regenerating

```bash
cd socket-organizer/freecad
freecadcmd build_socket_organizer.py
```

Needs FreeCAD 1.0+. Outputs land in `exports/` as STEP, STL and 3MF for
all 5 pieces plus all 4 fit coupons (post × 2 drives, piece-to-piece
dovetail × 1, nameplate × 1) — 9 objects × 3 formats = 27 files. Every run
reports fit, structural, printability, mesh-health, and nameplate
slot/tail interlock checks — see the repo root README for what each one
means.

---

Printed parts are not toys and are not food-safe; see the
[safety notes](../README.md#safety). Provided as-is, with no warranty.

Part of a collection of free 3D models — [see them all](../README.md).
MIT licensed; free for personal and commercial use.
