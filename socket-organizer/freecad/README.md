# Socket Organizer: design notes

## Why there is no per-size piece

A post's size depends only on the **drive** (3/8" is 9.53 mm across the flats,
1/2" is 12.70 mm), never on which socket sits on it, because every socket of a
given drive has the same square drive hole. So one blank template per drive
physically fits every socket size that drive makes. This replaced an earlier
design with one labeled piece per size and drive, 61 pieces in all.

## Why there are three width tiers

A single width sized for a ~36 mm socket wastes plastic and wall space on a
small 6 mm socket. So the template comes in three widths, each with clearance
for its target socket:

| Tier | Socket range | Target OD | `base_w` | OD clearance (left/right) |
|---|---|---|---|---|
| Small  | 6–12 mm  | 17 mm | 30 mm | 6.50 mm |
| Medium | 13–19 mm | 24 mm | 31 mm | 3.50 mm |
| Large  | 20–25 mm | 36 mm | 40 mm | 2.00 mm |

Nothing in the geometry stops you from putting an oversized socket on a small
template, since the post is set by drive, not tier. It just won't have the
clearance listed here.

## What stays fixed across tiers

Only `base_w` (the width along the row) and the post's X-center change between
tiers. `base_d`, `base_h`, `post_h`, the post's Y-center, the nameplate pocket's
position and the dovetail's Y-offset are identical. That gives you:

- **Flush edges in a mixed row.** A small template next to a large one still
  lines up front to back and top to bottom.
- **Dovetails that interlock across tiers.** Any tier's tail fits any other
  tier's groove, or a cap's, at the same height and depth. The build fuses the
  `dovetail_coupon_cross_tier` and `cap_coupon_*` coupons at the real offset to
  check this alignment.
- **More pocket clearance on smaller tiers.** The pocket and post positions were
  derived against the large tier's 36 mm socket, the case where the socket comes
  closest to the pocket. Smaller sockets clear it by more:

  | Tier | Target OD | Pocket-to-socket Y margin |
  |---|---|---|
  | Small  | 17 mm | 11.75 mm |
  | Medium | 24 mm | 8.25 mm |
  | Large  | 36 mm | 2.25 mm (the binding case) |

## Why small and medium are nearly the same width

The nameplate pocket is one fixed size shared by every tier, so one nameplate
fits them all. With the 2 mm-per-side margin used elsewhere, that pocket needs
`base_w` of at least ~28.25 mm. A small tier sized from its 17 mm target OD alone
would be about 21 mm wide, too narrow for the pocket.

So small and medium are limited by the pocket, not by their target OD, which is
why they land at 30 and 31 mm. Only the large tier is limited by its socket.

| Tier | `base_w` | Pocket footprint margin (left/right) |
|---|---|---|
| Small  | 30 mm | 2.88 mm |
| Medium | 31 mm | 3.38 mm |
| Large  | 40 mm | 7.88 mm |

## Caps

`cap_start` and `cap_end` close off the exposed dovetail at each end of a row.
They carry no post and no pocket, so they are only 12 mm wide. They share the
templates' depth and base height, so they sit flush front to back. `cap_w`
leaves an 8 mm solid wall behind the dovetail groove, and the structural check
enforces a 1.2 mm minimum, so there is room to change it.

## Nameplates

Each template has a plain rectangular pocket in the top of its riser, in front
of the post. A nameplate presses straight down into it, grips by friction and
sits flush with the riser's top surface.

This replaced an earlier nameplate that slid into a dovetail slot on a sloped
front wall, which didn't print cleanly. The front wall is now plain and vertical.

No text is baked into the geometry, and there is no multi-color export. To color
a label, assign colors to the nameplate in your slicer.

## Regenerating

```bash
cd socket-organizer/freecad
freecadcmd build_socket_organizer.py
```

Needs FreeCAD 1.0 or newer. Each run writes STEP, STL and 3MF to `exports/` for
all 9 pieces and 7 coupons (16 objects × 3 formats = 48 files). It reports fit,
structural, printability, mesh-health and nameplate pocket fit checks, per tier
where the check depends on width. The [root README](../../README.md#what-the-scripts-check)
explains what each one means.
