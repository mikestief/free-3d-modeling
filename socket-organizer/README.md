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
| Size | 3 width tiers (small/medium/large — see table below) × 51 × 26 mm per template (base + post, before the socket itself); end caps are narrower, 12 × 51 × 15 mm |
| Print time | Small parts — roughly 10–25 min per template depending on tier, a couple minutes per cap or nameplate; several print easily on one plate |
| Material | A few grams per piece in PLA or PETG |
| Supports | None |
| Bed needed | Any — pieces are small and print individually or in batches |
| Status | Generated and checked (fit/printability/mesh); not yet printed |

## 9 piece types: 3 width tiers × 2 drives, plus shrunk caps and a nameplate

This used to be a size table: one uniquely-labeled piece per metric/SAE
size × drive combination (61 pieces). The insight that removed that: a
socket's post only depends on the **drive** (3/8" af=9.53mm vs. 1/2"
af=12.70mm), never on which socket size sits on it — every socket of a
given drive shares the same square drive-hole. So one blank template per
drive already physically fits every socket size that drive makes,
regardless of width.

Width still matters, though — the earlier single-width template (`base_w`
= 40mm) was sized to clear a worst-case ~36mm-OD socket in every
direction, which is a lot of wasted plastic and footprint for a small
6mm socket that only needs a fraction of that room. So the template comes
in 3 width **tiers**, matched to real socket-size ranges, on top of the 2
drives — 6 template combinations total:

| Tier | Socket range | Target OD | `base_w` | Live-verified OD clearance margin |
|---|---|---|---|---|
| Small  | 6–12mm  | 17mm | 30mm | 6.50mm (left/right) |
| Medium | 13–19mm | 24mm | 31mm | 3.50mm (left/right) |
| Large  | 20–25mm | 36mm | 40mm | 2.00mm (left/right) |

Plus:

- **`cap_start`** / **`cap_end`** — row-end pieces, still blank, now
  shrunk to their own 12mm-wide footprint (down from the old full
  `base_w`) since a cap carries no post and no nameplate pocket — nothing
  that needs template width, just the dovetail connector. Same depth and
  height as every template tier, so caps still align flush front-to-back
  and top-to-bottom in a mixed row.
- **`nameplate_template`** — a single small blank rectangular block that
  presses straight down into any tier's top pocket, snug/friction fit.
  Print as many as you want, and label each one yourself.

A row is any number of templates (any mix of tiers and drives) snapped
together, with one cap on each end — the caps close off the exposed
dovetail edge so the finished row doesn't have a raw connector sticking
out. The piece-to-piece dovetail sits at the exact same position on every
tier's template and on both caps, so any tier interlocks with any other
tier, or with a cap, without modification — verified live with cross-tier
and cap/template fit coupons (see below).

### Why base_d, height, post position, and the pocket stay fixed across tiers

Only `base_w` (width — the row-direction pitch) and the post's X-center
change between tiers. Everything else — `base_d` (depth), `base_h`
(height), `post_h`, the post's Y-center, the nameplate pocket's position,
and the piece-to-piece dovetail's Y-offset — is identical across all 3
tiers. That's deliberate, not an oversight:

- **Flush edges in a mixed row.** `base_d` is the fixed "length"
  dimension every piece shares, so a small-tier template sitting next to
  a large-tier template still lines up front-to-back and top-to-bottom.
- **The dovetail interlocks across tiers.** Since the dovetail's Y-offset
  never varies by tier, any tier's tail fits any other tier's groove (and
  the cap's) at the exact same height and depth — verified with the
  `dovetail_coupon_cross_tier` and `cap_coupon_*` fit coupons below.
- **The nameplate pocket gets extra-safe on smaller tiers, for free.**
  The pocket's position and the post's Y-center were both derived against
  the *large* tier's worst-case 36mm socket — the binding case, where the
  socket's own circular footprint comes closest to reaching the pocket.
  A smaller tier's smaller socket automatically clears the pocket by
  *more* real margin, with no separate derivation needed. Live-verified
  numbers (Y-gap between the pocket and the socket's own footprint):

  | Tier | Target OD | Pocket-to-socket Y margin |
  |---|---|---|
  | Small  | 17mm | 11.75mm |
  | Medium | 24mm | 8.25mm |
  | Large  | 36mm | 2.25mm (the binding case — this margin is what everything else is sized against) |

### The nameplate pocket sets its own floor on `base_w`

One real finding from live-verifying this design, not assumed from the
naive "OD + 2mm/side" arithmetic that first scoped the tier widths above:
the nameplate pocket is a single fixed size shared by every tier (it's
the same physical nameplate block, meant to press into any template), and
that fixed-size pocket needs `base_w` ≥ ~28.25mm just to sit centered in
a template with the same 2mm-per-side footprint margin every other check
in this file uses. A "small" tier scoped purely off its own 17mm target
OD would want `base_w` around 21mm — narrower than the pocket can
physically fit in. So **small and medium are actually bounded by the
shared nameplate mechanism, not by their own (much smaller) target OD** —
that's why their `base_w` values (30mm / 31mm) land close together
instead of scaling down with target OD the way the naive arithmetic
suggested. Only the large tier is genuinely OD-bound (36mm target OD
needs more room than the nameplate floor does). Live-verified nameplate
footprint margins per tier:

| Tier | `base_w` | Nameplate pocket footprint margin (left/right) |
|---|---|---|
| Small  | 30mm | 2.88mm |
| Medium | 31mm | 3.38mm |
| Large  | 40mm | 7.88mm |

### Picking a tier

Match the tier to the socket range you're actually storing on that piece
(see the table above). Nothing in the geometry stops you from resting an
oversized socket on a small/medium-tier post — the post's own size is set
by **drive**, not tier, so a 1/2" drive small-tier template still accepts
any 1/2"-drive socket physically. Pick the tier the way you'd pick the
right size bin for anything: this is an inherent property of a
post-style socket holder (the post doesn't know how big a socket sits on
it), not a defect the geometry tries to engineer around.

## Labeling — your slicer, not this generator

This generator no longer bakes any size text into the geometry at all.
Instead, each template has a plain rectangular pocket inset into the top of
its riser, in front of the post, and the separate `nameplate_template`
piece is a matching plain rectangular block — press a nameplate straight
down into a template's pocket and it grips by friction, snug enough to
stay put, sitting flush with the riser's top surface once seated. The
pocket is identical across every tier, so one nameplate design fits all of
them.

This replaces an earlier design where the nameplate slid into a dovetail
slot on a sloped front wall — that mechanism didn't print cleanly, so the
front wall is now a plain vertical wall (no slope at all) and the
nameplate mechanism is a straight-down press fit instead of a sliding
dovetail.

Print a stack of blank nameplates, then use your slicer's own text tool
(Bambu Studio, OrcaSlicer, PrusaSlicer, etc. all have one) to add whatever
label you want — `10`, `5/16`, `1/2" DR`, anything — directly on each
nameplate before you print it. Press it into a template's pocket once it's
done. This means:

- Any size, any label text, any language — nothing about it is
  constrained by this generator any more.
- If you print a nameplate wrong or want to relabel a pocket, just print
  another nameplate — the template underneath never changes.
- No multi-color printer required. If you want the label in a different
  color, that's your slicer's per-object color assignment on the
  nameplate object, same as coloring any other single print differently
  from the rest of your plate — this generator has no multi-color export
  path any more, since there's only one blank object per nameplate to
  color in the first place.

## Print the coupons first

7 small coupons ship alongside the 9 real pieces:

- [`freecad/exports/post_coupon_3-8in.3mf`](freecad/exports/post_coupon_3-8in.3mf) /
  [`freecad/exports/post_coupon_1-2in.3mf`](freecad/exports/post_coupon_1-2in.3mf) —
  one (large-tier) template each — post geometry doesn't depend on tier,
  only drive, so one coupon per drive covers every tier — so you can
  test-fit a real socket before printing a full row.
- [`freecad/exports/dovetail_coupon.3mf`](freecad/exports/dovetail_coupon.3mf) —
  two pre-joined **same-tier** (large + large) templates, to check the
  piece-to-piece snap seats and releases cleanly — the regression case,
  unchanged from before the tier split.
- [`freecad/exports/dovetail_coupon_cross_tier.3mf`](freecad/exports/dovetail_coupon_cross_tier.3mf) —
  two pre-joined **different-tier** (small + medium) templates, proving
  the dovetail's shared Y-offset really does let mismatched tiers
  interlock, not just same-tier rows.
- [`freecad/exports/cap_coupon_small.3mf`](freecad/exports/cap_coupon_small.3mf) /
  [`freecad/exports/cap_coupon_medium.3mf`](freecad/exports/cap_coupon_medium.3mf) —
  a shrunk cap pre-joined to a small-tier and a medium-tier template
  respectively, proving the one cap design interlocks with more than one
  tier without modification.
- [`freecad/exports/nameplate_coupon.3mf`](freecad/exports/nameplate_coupon.3mf) —
  one template with one nameplate pre-seated in its top pocket, fused into
  a single printable test object, to check the pocket/block press fit
  before committing to a full print run. The pocket mechanism is identical
  across tiers, so one coupon covers all of them.

STL and STEP versions are alongside them in
[`freecad/exports/`](freecad/exports/), along with all 9 real pieces.

If a post is too loose or tight, adjust `post_af_undersize` in
[`freecad/build_socket_organizer.py`](freecad/build_socket_organizer.py) and
re-run. If the piece-to-piece dovetail snap is too loose or tight, adjust
`dt_clearance`. If the nameplate pocket/block press fit is too loose,
tight, or doesn't seat flush, adjust `nameplate_clearance` — this is a
first engineering pass with no prior print history behind it (unlike
`dt_clearance`, which has years of this file's own history and real
prints backing it), so treat the coupon test as the real source of truth,
not the number itself. If a cap feels fragile, `cap_w` (12mm, leaving an
8mm solid wall behind the dovetail groove cut) can grow — the structural
self-check enforces a 1.2mm minimum wall, so there's real room above that
floor already.

## Regenerating

```bash
cd socket-organizer/freecad
freecadcmd build_socket_organizer.py
```

Needs FreeCAD 1.0+. Outputs land in `exports/` as STEP, STL and 3MF for
all 9 pieces (6 templates + 2 caps + 1 nameplate) plus all 7 fit coupons
(post × 2 drives, dovetail × 2 — same-tier regression and cross-tier, cap
× 2 tiers, nameplate × 1) — 16 objects × 3 formats = 48 files. Every run
reports fit, structural, printability, mesh-health, and nameplate
pocket/block fit checks, per tier where the check depends on tier width —
see the repo root README for what each one means.

---

Printed parts are not toys and are not food-safe; see the
[safety notes](../README.md#safety). Provided as-is, with no warranty.

Part of a collection of free 3D models — [see them all](../README.md).
MIT licensed; free for personal and commercial use.
