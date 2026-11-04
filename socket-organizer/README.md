# Socket Organizer

A modular socket holder for metric and SAE sockets, 3/8" and 1/2" drive. Each
socket stands on a molded post sized to its drive square, and friction on the
post corners holds it upright, with no magnets. Pieces join with a vertical
dovetail: press one straight down to seat it, lift it straight up to remove it.
Any piece comes out without disturbing its neighbors, so you build out exactly
the sockets you own.

| | |
|---|---|
| Size | Templates 30, 31 or 40 mm wide × 51 × 19 mm, plus a 4 mm dovetail tail. Caps 12 mm wide × 51 × 8 mm (`cap_start` also has the tail) |
| Print time | Roughly 10–25 min per template, a couple of minutes per cap or nameplate |
| Material | PLA or PETG. Up to ~20 g per template, ~6 g per cap, ~1 g per nameplate (upper bounds, from solid volume; the slicer will show less) |
| Supports | None |
| Bed needed | Any. Pieces are small, and several fit on one plate |
| Status | Printed |

## What to print for a row

A row is any mix of templates, with a cap on each end to close off the exposed
dovetail. Any template joins any other template or cap.

**1. One template per socket.** Pick the drive that matches the socket, and the
width that matches its size:

| Width | Socket range | 3/8" drive | 1/2" drive |
|---|---|---|---|
| Small (30 mm) | 6–12 mm | [`template_small_3-8in`](freecad/exports/template_small_3-8in.3mf) | [`template_small_1-2in`](freecad/exports/template_small_1-2in.3mf) |
| Medium (31 mm) | 13–19 mm | [`template_medium_3-8in`](freecad/exports/template_medium_3-8in.3mf) | [`template_medium_1-2in`](freecad/exports/template_medium_1-2in.3mf) |
| Large (40 mm) | 20–25 mm | [`template_large_3-8in`](freecad/exports/template_large_3-8in.3mf) | [`template_large_1-2in`](freecad/exports/template_large_1-2in.3mf) |

For SAE sockets, go by the outside diameter: up to ~17 mm for small, ~24 mm for
medium, ~36 mm for large.

**2. Two caps per row:** [`cap_start`](freecad/exports/cap_start.3mf) and
[`cap_end`](freecad/exports/cap_end.3mf).

**3. One nameplate per template:**
[`nameplate_template`](freecad/exports/nameplate_template.3mf). See
[Labeling](#labeling).

STL and STEP versions are alongside them in
[`freecad/exports/`](freecad/exports/).

## Print the coupons first

These small test pieces let you check the fits before you print a full set. You
don't need all of them:

| To check | Print |
|---|---|
| A real socket fits on its post | [`post_coupon_3-8in`](freecad/exports/post_coupon_3-8in.3mf), [`post_coupon_1-2in`](freecad/exports/post_coupon_1-2in.3mf) |
| How two joined templates line up | [`dovetail_coupon`](freecad/exports/dovetail_coupon.3mf) (large + large) |
| How two different widths line up | [`dovetail_coupon_cross_tier`](freecad/exports/dovetail_coupon_cross_tier.3mf) (small + medium) |
| How a cap lines up with a template | [`cap_coupon_small`](freecad/exports/cap_coupon_small.3mf), [`cap_coupon_medium`](freecad/exports/cap_coupon_medium.3mf) |
| How a seated nameplate sits | [`nameplate_coupon`](freecad/exports/nameplate_coupon.3mf) |

The dovetail, cap and nameplate coupons each print as one fused object, so they
don't come apart. To feel the snap or the press fit, print two small templates,
or a template and a nameplate.

## Labeling

No text is built into the parts, so a label can say anything: `10`, `5/16`,
`1/2" DR`.

1. Open [`nameplate_template`](freecad/exports/nameplate_template.3mf) in your
   slicer. Bambu Studio, OrcaSlicer and PrusaSlicer all have a text tool.
2. Add your label and print it.
3. Press the nameplate straight down into the pocket on top of a template.

To relabel a socket, print a new nameplate. The template stays as it is.

## Change it

Change these numbers in
[`freecad/build_socket_organizer.py`](freecad/build_socket_organizer.py), then
re-run the script (`freecadcmd build_socket_organizer.py`, from `freecad/`) to
rebuild every file:

| If… | Change |
|---|---|
| A socket is too loose or tight on its post | `post_af_undersize` |
| The dovetail is too loose or tight | `dt_clearance` |
| A nameplate is too loose or tight, or doesn't sit flush | `nameplate_clearance` |
| A cap feels fragile | `cap_w` |

**[Design notes and tier measurements →](freecad/README.md)**

---

Printed parts are not toys and are not food-safe; see the
[safety notes](../README.md#safety). Provided as-is, with no warranty.

Part of a collection of free 3D models — [see them all](../README.md).
MIT licensed; free for personal and commercial use.
