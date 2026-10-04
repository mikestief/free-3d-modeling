# French-Cleat Bins: design notes

## The cleat

The rail and the hook are both taken from the *Multiboard French Cleat
Storage Bins* set, measured off the meshes in its 3MF.

**Rail.**
- A 42.8 mm tall, 5.0 mm plate.
- The top 8.74 mm is bevelled 20° on the *board* side, which thins the top
  edge to 1.82 mm.
- On its board side are octagonal bosses: 13.5 mm across the flats at the
  root, tapering slightly, with a 0.5 mm chamfered tip, 8.4 mm tall. They
  hold the plate's front face 13.4 mm off the board.
- Each boss is centred 12.5 mm up from the rail's bottom edge, on a 25 mm
  unit centre. There is always a boss on both end units, then one on every
  other unit working inwards, mirrored. That rule reproduces all four
  original rails (3, 4, 5 and 6 units).
- When this model was built, the generated 3–6 unit rails were compared
  against the original meshes (a one-off check, not part of the script,
  since those meshes aren't in this repo). Every original vertex lay within
  0.001 mm of the generated rail, and the volumes matched to within 1 mm³.

**Bin hook.**
- A 20° wedge slot, 18 mm deep, at the top of the back wall.
- The lip is 1.82 mm thick at its tip. It slides down into the gap that the
  rail's bevel leaves between the rail and the board.
- The back wall rests on the rail's flat front face.
- Slot and bevel have the same taper, so the rail bears on the whole wedge
  face. The original bins use zero clearance here, and so do these
  (`slot_clear = 0`).

The only change from the original hook is the slot apex. The original has a
1.8 mm flat ceiling there. Here it is a peaked roof instead, so an upright
print has nothing to bridge inside the slot.

## Foot or no foot

A bin should hang plumb, which means the bottom of its back needs something
to rest on.

- **Shallow basket.** The back is 50 mm, about the rail's own height, so it
  rests on the full rail. The rail's bottom edge lands 0.2 mm above the
  basket's bottom, and no foot is needed.
- **Screw bin.** It is 70 mm tall, so its bottom 20 mm hangs below the rail.
  Three 20 mm wide, 8 mm tall foot pads (the two ends and the middle)
  reach back to the board face to hold it plumb. They only need to touch
  the board, so they don't run the full width. That also leaves the slicer
  a clear path from the bed to the lip for its support.

With a foot, the script checks two things:
- The rail's bottom edge clears the top of the foot (12.2 mm as shipped).
- The foot stays outside the rail's swing radius, so the bin can be hooked
  on and swung in.

Without a foot, it checks that the rail reaches within 5 mm of the bin
bottom.

50 mm is also the lowest back wall that still carries the hook and rests on
the whole rail. To make the basket shallower, lower `front_h`, not
`wall_h`.

## Why upright

The original bins print on their side. That puts the whole profile in each
layer, which makes a strong hook with no overhangs. The catch is that the
far side wall would then be a large bridge, which is why those bins ship as
a body plus a glued panel.

Printing upright gives one piece with vertical walls and nothing to bridge.
The cost is one supported overhang: the underside of the lip, a
1.8 × 189 mm strip. The printability check reports it as the one expected
flat ceiling.

Upright also puts the layer lines across the back wall, which is the load
path. That is fine at these loads. Two 1 lb boxes put under 2 MPa of
bending stress into a 189 mm wide, 2.4 mm wall, far below PETG's layer
strength.

## Where the plastic goes

Only the back wall and the hook carry the hanging load, so only they are
kept thick.

| Part | Thickness | Why |
|---|---|---|
| Hook and lip | Unchanged from the original | Load path, and the shape that fits the rail |
| Back wall (`back_wall`) | 2.4 mm | Carries the load |
| Front and side walls (`wall`) | 1.6 mm | Only hold the contents in |
| Floor (`floor_t`) | 2.0 mm | Prints on the bed, and every edge is on a wall |
| Foot | 3 pads, not a full-width strip | Only needs to touch the board |

Compared with an all-2.4 mm first pass (3 mm floor, full-width foot on the
screw bin), the solid volume dropped from 167 to 126 cm³ on the screw bin
(−25%) and from 138 to 117 cm³ on the basket (−15%).

Wall thickness in the model is the lever that matters. A wall of 2.4 mm or
less prints as solid perimeters whatever the slicer's wall count is set to.
Only the thick hook block and the foot pads get infill. For those, 3 wall
lines and 10–15% gyroid infill is plenty.

## Checks

Every run of `build_cleat_bins.py` checks the following.

- **Fit (per bin).** Probes for each screw box, the rail (plate, bevel and
  the boss band) and the board face must clear the bin. The rail is also
  raised 0.3 mm to confirm it bears on the lip rather than rattling in a
  loose slot.
- **Rail consistency.** Each printed rail must sit inside the envelope that
  the bins were fit-checked against, and must be no wider than the bin
  named for it in `RAILS`, so it stays hidden behind that bin.
- **Structural.** Lip tip ≥ 1.2 mm, hook block ≥ 4 mm, back wall, walls,
  floor and divider each ≥ 1.6 mm, the lip stays off the board and above the bosses, plus the
  foot/rail checks above.
- **Printability.** Any flat ceiling other than the lip underside fails.
- **Mesh health.** B-rep check, closed shell, and non-manifold and
  self-intersecting tessellation, for every part and coupon piece.

## Regenerating

```bash
cd french-cleat-bins/freecad
freecadcmd build_cleat_bins.py
```
