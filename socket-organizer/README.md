# Socket Organizer

Modular, interlinking socket holder. Metric and SAE, 3/8" and 1/2" drive.
Each socket stands on a molded post sized to its drive square — friction on
the post corners holds it upright, no magnet, no stick. Pieces snap
together with a vertical dovetail: press a piece straight down to seat it,
lift straight up to remove it. Any single piece comes out without
disturbing its neighbors, so you build out exactly the sockets you own.

| | |
|---|---|
| Size | 43 × 53 × 21 mm per piece (base + post, before the socket itself) |
| Print time | Small parts — roughly 15–25 min per piece on a typical FDM printer; total time scales with however many of the 61 pieces you print, and several batch easily on one plate |
| Material | A few grams per piece in PLA or PETG |
| Supports | None |
| Bed needed | Any — pieces are small and print individually or in batches |
| Status | Generated and checked (fit/printability/mesh); not yet printed |

## Sizes

Sized against two real photographed Craftsman socket trays, not a guess —
their 3/8" drive tray runs 6–22mm metric / 5/16"–1" SAE, and their 1/2"
drive tray covers the same range plus 23–25mm metric at the top (SAE tops
out at 1" either way).

- **Metric**: 6–7mm in 3/8" drive only (2 sizes), 8–22mm in both drives
  (15 sizes), plus 23–25mm in 1/2" drive only (3 sizes)
- **SAE**: 5/16"–1" in 1/16" steps, in both drives (12 sizes) — no
  drive-only sizes at either end
- The small metric end (6–7mm) is 3/8" drive only because 1/2" drive
  sockets don't come that small; the large metric end (23–25mm) is 1/2"
  drive only because 3/8" drive sets don't typically go that large — SAE
  doesn't split this way, since the user's 3/8" tray goes all the way to
  1", matching their 1/2" tray
- 59 middle pieces + 2 end caps = 61 pieces total, all sharing one
  dovetail interface — mix metric, SAE, and drive size in any order

A row is any number of middle pieces snapped together, with one cap on
each end — the caps close off the exposed dovetail edge so the finished
row doesn't have a raw connector sticking out. Caps are universal, not
sized to any socket, so the same two caps close off any row regardless of
which or how many middle pieces you use.

## Print the coupons first

Three small coupons ship alongside the full set:

- [`freecad/exports/post_coupon_3-8in.3mf`](freecad/exports/post_coupon_3-8in.3mf) /
  [`freecad/exports/post_coupon_1-2in.3mf`](freecad/exports/post_coupon_1-2in.3mf) —
  one middle piece each, so you can test-fit a real socket before
  committing to the full run
- [`freecad/exports/dovetail_coupon.3mf`](freecad/exports/dovetail_coupon.3mf) —
  two pre-joined pieces, to check the snap seats and releases cleanly

STL and STEP versions are alongside them in
[`freecad/exports/`](freecad/exports/), along with all 61 pieces.

If a post is too loose or tight, adjust `post_af_undersize` in
[`freecad/build_socket_organizer.py`](freecad/build_socket_organizer.py) and
re-run. If the dovetail snap is too loose or tight, adjust `dt_clearance`.

## Multi-color labels

Every middle piece's size label (`10`, `5/16`, etc.) can be printed in a
different filament color from the body on a multi-color printer (Bambu
AMS, or any similar MMU/AMS setup). For each of the 59 middle pieces
(not the 2 end caps, which have no label), `exports/` includes:

- `<name>_multicolor.3mf` — **one file**, containing the body and the
  label as two separate objects at the same position. Import just this
  file into a multi-color-capable slicer (Bambu Studio, OrcaSlicer,
  PrusaSlicer) and it shows up as two independently-colorable objects,
  already aligned — assign the body one filament/AMS slot and the label
  another, and slice. No second import step needed.
- `<name>_body.stl` / `.step` and `<name>_label.stl` / `.step` — the same
  two pieces as separate single-object files, in the same coordinate
  frame (no relative offset between them). These aren't needed for the
  Bambu-style single-file workflow above; they're kept for non-3MF
  tooling or CAD software that needs the split geometry on its own.

The plain `<name>.stl` / `.step` files (the fused single-color piece) are
unchanged and still there for single-color printing. There's no plain
`<name>.3mf` for the 59 middle pieces — `<name>_multicolor.3mf` above
supersedes it for anyone with a multi-color printer, and it's redundant
with `.stl`/`.step` for single-color printing. If you have a multi-color
printer but want a single-color result, use `<name>_multicolor.3mf` and
assign both objects (body and label) the same filament/AMS slot instead of
different ones. The 2 end caps have no label or multicolor variant, so
they keep their plain `<name>.3mf` as before.

## Regenerating

```bash
cd socket-organizer/freecad
freecadcmd build_socket_organizer.py
```

Needs FreeCAD 1.0+. Outputs land in `exports/` as STEP and STL for every
piece, plus a plain 3MF for the 2 end caps and 3 coupons (the 59 middle
pieces get a multi-color 3MF instead — see above). Every run reports fit,
structural, printability and mesh-health checks — see the repo root
README for what each one means.

---

Printed parts are not toys and are not food-safe; see the
[safety notes](../README.md#safety). Provided as-is, with no warranty.

Part of a collection of free 3D models — [see them all](../README.md).
MIT licensed; free for personal and commercial use.
