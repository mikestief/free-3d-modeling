# Socket Organizer — Design Spec

Date: 2026-08-29

## Purpose

Modular, interlinking socket holder. Supports metric and SAE sockets in both
3/8" and 1/2" drive. Each socket stands upright, secured purely by friction
on its drive-square attachment point — no magnet, no long center stick.
Pieces snap together vertically to build out exactly the sockets you own, in
any order.

## Piece types

1. **Middle piece** — one socket each. Molded post (sized to the socket's
   drive square) rises from a base; size number/fraction is embossed on the
   sloped front wall, in front of the socket. Dovetail groove on the left
   edge, dovetail tail on the right edge.
2. **Start/end cap** — rounded, closed piece with a single dovetail face and
   no post. Caps off the exposed end of a row. Universal — one design, not
   per-drive or per-size. 2 pieces total.

## Sizes covered

- **Metric**: 8–19mm, 1mm steps → 12 sizes
- **SAE**: 5/16"–3/4", 1/16" steps → 8 sizes (5/16, 3/8, 7/16, 1/2, 9/16,
  5/8, 11/16, 3/4)
- **Drives**: 3/8" and 1/2", every size available in both
- Total: 20 sizes × 2 drives = **40 middle pieces**, plus 2 caps = **42
  pieces**

Metric and SAE pieces share one dovetail interface — mix and order freely,
no separate metric/SAE sets.

## Mounting concept — center post (friction on drive square)

Each middle piece has a short square post molded up from its base, sized to
the socket's drive-square broach hole:

- 3/8" drive: ~9.5mm across flats (nominal; corners lightly rounded to match
  a real broach corner)
- 1/2" drive: ~12.7mm across flats

The socket presses down over the post, drive-hole down. Friction on the
post's corners holds it upright; no magnet, no lid, no long stick through
the socket. Post height ~10–12mm: enough engagement to grip, short enough
that long/deep sockets don't tip.

Exact post dimensions are **not** fixed in this spec — they're dialed in via
the post fit coupon (see Testing) since printer/filament shrinkage varies
per shop. The generator script takes the target interference as a
parameter.

## Base geometry

- Fixed footprint for **every** piece regardless of socket size or drive —
  roughly 24–26mm × 30–34mm (exact number set in the fit coupon pass; must
  clear the largest socket, 19mm/3/4", with margin). This is what makes
  differently-sized pieces line up flush and keeps the dovetail interface
  identical across the whole set.
- Front wall is sloped; the size label is embossed (raised) on it, reading
  correctly when the row sits on a bench in front of the user.
- Base sits flat on a bench or drawer liner — not wall/pegboard mounted.

## Joint mechanism — vertical dovetail (snap, not slide)

Each piece has a dovetail **groove** on its left edge and a dovetail
**tail** on its right edge, both running the full height of the piece,
open at the top and closed at the bottom.

- **Assembly**: press a piece straight down so its tail slides down into
  the neighboring piece's open-top groove.
- **Removal**: lift straight up and out.
- Because the groove is open only at the top (not threaded through a full
  rail), any single piece can be added or removed independently without
  disturbing its neighbors — this was an explicit requirement ("build what
  you need").
- Cross-section is a constant trapezoid extruded straight up in Z — no
  overhang, no supports needed regardless of piece height.
- Tolerance (how snug the snap is) is dialed via the dovetail fit coupon,
  same reasoning as the post fit.

## Generator architecture

Follows the existing repo convention (see `whiteboard-stand/`):

```
socket-organizer/
  README.md
  images/
  freecad/
    build_socket_organizer.py
    exports/
```

- `build_socket_organizer.py` is driven by a size table: metric list (mm),
  SAE list (fraction), drive list (3/8", 1/2"). Iterates the table and
  generates every middle piece plus the 2 caps in one run.
- Common geometry (base footprint, dovetail profile, label mechanics) is
  shared code; only the post cross-section and label text vary per piece.
- Exports STEP + STL + 3MF per piece, plus a build report, same as
  `build_caddy.py`.
- File naming: `<unit>_<size>_<drive>.stl`, e.g. `metric_10mm_3-8in.stl`,
  `sae_5-8in_1-2in.stl`; caps are `cap_start.stl` / `cap_end.stl`.

## Testing / fit coupons

Two small coupons ship ahead of the full 42-piece set, per the repo's
"print the fit coupon first" convention:

1. **Post fit coupon** — one middle piece per drive size (2 total, using a
   mid-range socket like 12mm/1/2"), so a real socket can be test-fit
   before committing to the full run.
2. **Dovetail fit coupon** — a 2-piece minimal join (any two adjacent
   pieces) to confirm the snap tolerance seats and releases cleanly.

## Self-checks (generator output, per run)

Matches the existing repo pattern:

- **Fit** — probe solid of the target socket's drive-square pushed onto
  each post; must engage without collision beyond the intended
  interference band.
- **Structural** — minimum wall thickness at the post base and dovetail
  tail/groove walls.
- **Printability** — flags any downward-facing surface beyond the known
  dovetail/post geometry (should be none; both are Z-extruded prisms).
- **Mesh health** — manifold, closed shell, no self-intersection, valid
  tessellation for slicing.

## Out of scope

- Wall/pegboard mounting
- Two sockets per piece
- 1/4" drive
- Deep-socket-specific post tuning (deep sockets use the same post; if a
  particular deep socket is loose/tight, that's a fit-coupon adjustment,
  not a separate piece type)

## Open items for the implementation plan

- Exact post fit tolerance and base footprint dimensions (from fit coupon
  iteration)
- Exact dovetail trapezoid angle/depth (from fit coupon iteration)
- Font/depth for embossed label text
