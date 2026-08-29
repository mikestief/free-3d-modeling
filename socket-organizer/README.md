# Socket Organizer

Modular, interlinking socket holder. Metric and SAE, 3/8" and 1/2" drive.
Each socket stands on a molded post sized to its drive square — friction on
the post corners holds it upright, no magnet, no stick. Pieces snap
together with a vertical dovetail: press a piece straight down to seat it,
lift straight up to remove it. Any single piece comes out without
disturbing its neighbors, so you build out exactly the sockets you own.

| | |
|---|---|
| Size | 26 × 32 × 21 mm per piece (base + post, before the socket itself) |
| Print time | Small parts — roughly 15–25 min per piece on a typical FDM printer; total time scales with however many of the 42 pieces you print, and several batch easily on one plate |
| Material | A few grams per piece in PLA or PETG |
| Supports | None |
| Bed needed | Any — pieces are small and print individually or in batches |
| Status | Generated and checked (fit/printability/mesh); not yet printed |

## Sizes

- **Metric**: 8–19mm (12 sizes)
- **SAE**: 5/16"–3/4" in 1/16" steps (8 sizes)
- Every size in both **3/8"** and **1/2"** drive
- 40 middle pieces + 2 end caps = 42 pieces total, all sharing one dovetail
  interface — mix metric, SAE, and drive size in any order

## Print the coupons first

Three small coupons ship alongside the full set:

- [`freecad/exports/post_coupon_3-8in.3mf`](freecad/exports/post_coupon_3-8in.3mf) /
  [`freecad/exports/post_coupon_1-2in.3mf`](freecad/exports/post_coupon_1-2in.3mf) —
  one middle piece each, so you can test-fit a real socket before
  committing to the full run
- [`freecad/exports/dovetail_coupon.3mf`](freecad/exports/dovetail_coupon.3mf) —
  two pre-joined pieces, to check the snap seats and releases cleanly

STL and STEP versions are alongside them in
[`freecad/exports/`](freecad/exports/), along with all 42 pieces.

If a post is too loose or tight, adjust `post_af_undersize` in
[`freecad/build_socket_organizer.py`](freecad/build_socket_organizer.py) and
re-run. If the dovetail snap is too loose or tight, adjust `dt_clearance`.

## Regenerating

```bash
cd socket-organizer/freecad
freecadcmd build_socket_organizer.py
```

Needs FreeCAD 1.0+. Outputs land in `exports/` as STEP, STL and 3MF, one
set per piece plus the coupons. Every run reports fit, structural,
printability and mesh-health checks — see the repo root README for what
each one means.

---

Printed parts are not toys and are not food-safe; see the
[safety notes](../README.md#safety). Provided as-is, with no warranty.

Part of a collection of free 3D models — [see them all](../README.md).
MIT licensed; free for personal and commercial use.
