# Whiteboard Caddy — build and design notes

Classroom desk caddy holding **8 lap boards, 10 markers, 16 eraser pads** in
two boxes, with an arched carry handle and optional swappable name plates.

Generated parametrically by [`build_caddy.py`](build_caddy.py) in FreeCAD.
Printed and in classroom use. Licensed MIT — see [LICENSE](../../LICENSE);
free for personal and commercial use.

Developed on a **Bambu Lab X2D** in **PETG**, but nothing is specific to that
printer beyond the bed-size check.

Size: **244 × 159 × 94 mm**, ~601 cm³ solid.

---

## Print this first

**[`exports/fit_coupon.3mf`](exports/fit_coupon.3mf) — ~20 minutes, ~12 g.**

It carries one marker tube, a slice of the board channel, and an eraser-pad
depth gauge, all at the exact dimensions the real part uses.

1. A marker drops in cap-up and comes out without a fight.
2. A board slides into the channel without forcing.
3. An eraser pad clears the bay-wall gauge.

If any of those are wrong, change **one number** in `PARAMS` and re-run. Don't
print the 601 cm³ body until the coupon passes — the tolerances that matter
depend on the markers and boards *you* own.

| If… | Change |
|-----|--------|
| Marker too tight / too loose | `tube_id` (20.0) |
| Boards too tight in the channel | `slot_w` (5.0, per board) |
| Boards rub the end walls | `board_clear_x` (3.0) |
| Pads too tight in a box | `bay_clear` (3.2) |

---

## Opening the files

| Job | Import |
|-----|--------|
| Test print, first | `exports/fit_coupon.3mf` |
| The caddy | `exports/whiteboard_caddy.3mf` |

One file per plate — the caddy fills the plate on its own.

Bambu Studio will say **"The 3mf file has invalid config, load geometry data
only"**. That is normal and harmless; click OK. A FreeCAD 3MF is plain geometry
plus `unit="millimeter"`, and Bambu is only noting it contains none of its own
slicer settings. Import the `.stl` instead if the dialog annoys you. `.step` is
exact B-rep, for taking into other CAD software.

---

## Adapting it to your supplies

The numbers most likely to be wrong for you, all near the top of `PARAMS`:

| Your situation | Change |
|---|---|
| Different marker brand | `tube_id` (20.0 — sized for an Expo chisel cap) |
| More or fewer markers | `n_markers` (10) |
| Thicker or thinner boards | `slot_w` (5.0 per board), `n_boards` (8) |
| Different eraser pads | `pad_w` / `pad_d` / `pad_t` (50 × 50 × 8) |
| One eraser box, or three | `n_bays` (2), `pads_per_bay` (8) |
| Want the board divider ribs | `board_dividers` → `True` |
| Want name plates | `nameplate` → `True`, then `school_name` / `teacher_name` |
| Smaller printer | `bed_x` / `bed_y` / `bed_z`, then check the bed-fit line |

Name plates need a bold TTF; the script finds one automatically on macOS,
Windows and Linux, or set `FONT_OVERRIDE` to a specific `.ttf` path.

The generator refuses to produce impossible geometry — asking for 11 markers
raises a `ValueError` rather than silently merging the tube bores together.

---

## Current configuration

| Item | Value |
|------|-------|
| Boards | 8 × 9"×12", **open channel, no divider ribs** |
| Channel depth | 40 mm (8 × 5.0 mm per board) |
| Actual capacity | **11 boards** at 3.5 mm — measured, not calculated |
| Board lean | 10° rearward |
| Markers | **10**, single merged row, cap-up |
| Marker pitch | 22.56 mm — squeezed to fit; 2.56 mm of material between bores |
| Erasers | **2 boxes**, 8 pads each = 16 pads (50 × 50 × 8 mm) |
| Box size | 58 × 58 × 73 mm each, side by side, centred |
| Name plates | none (`nameplate: False`) |
| Handle | 80 mm arched cutout in the back wall |

---

## Re-running the generator

Headless, from this folder — no GUI required:

```bash
freecadcmd build_caddy.py
```

On macOS, `freecadcmd` is inside the app bundle:

```bash
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd build_caddy.py
```

Or from the Python console inside FreeCAD:

```python
import sys; sys.path.insert(0, "/path/to/whiteboard-stand/freecad")
import importlib, build_caddy; importlib.reload(build_caddy); print(build_caddy.run())
```

Requires FreeCAD 1.0 or newer; no other dependencies. A full rebuild takes a
few seconds and rewrites everything in `exports/`.

The `Params` spreadsheet inside the `.FCStd` is a **record** of the values
used, not a live driver — edit `PARAMS` in the script and re-run.

---

## Slicer settings (PETG, 0.4 nozzle)

| Setting | Value |
|---------|-------|
| Layer height | 0.2 mm |
| Walls / wall loops | **4** |
| Top / bottom layers | 5 / 4 |
| Infill | 15% gyroid |
| Supports | **None** — print flat on the base as oriented |
| Brim | Not required on textured PEI |

Roughly **380–450 g** and **20–28 h**.

---

## Automated checks

`run()` reports on every rebuild. All currently pass:

- **Fit** — a probe solid of every real object (10 markers, the 8-board stack,
  both eraser stacks, both tiles when enabled) is pushed through the model.
  Any intersection is a thing that physically will not fit. This caught a name
  plate that could not enter its own pocket.
- **Structural** — material above the handle, bay post width, web between
  adjacent marker bores.
- **Printability** — downward-facing surfaces, split into *flat ceilings*
  (true bridges, worth designing out) and *curved overhang* (progressive,
  fine). The checker re-validates itself against a control solid with a
  deliberate floating ledge every run, because an early version of it silently
  reported nothing at all.
- **Mesh health** — B-rep self-intersection, closed shell, non-manifold
  tessellation.

Both the shipped configuration and the fully-optional one (`nameplate` and
`board_dividers` both `True`) are verified to build watertight with all fit
probes clear, so the flags in the table above are safe to turn on.

Filleting is self-validating: rounding an edge that a tile pocket opens onto
produces a solid that passes every B-rep check and *still* tessellates into a
self-intersecting mesh. The generator now tries all edges at once, tests the
result, and falls back to adding them one at a time — keeping only the edges
that leave a clean solid.

Current state: **no flat ceilings**, body or coupon; both meshes watertight.
The only flagged surfaces are ~162 mm² × 2 at the apex of the handle arch —
normal progressive overhang, no support needed.

---

## Mesh validity

Bambu Studio once reported **6 non-manifold edges** on this model. Two separate
causes, both fixed at source rather than with a repair tool:

1. **`removeSplitter()`** — merging coplanar faces after the booleans made OCC
   emit six self-intersecting edge/face pairs. `Shape.isValid()` returns True
   on these; only `Shape.check()` catches them. That call is now gone.
2. **Tangential contact** — the eraser bay's rear wall sat exactly flush with
   the front of the tube row, so it was tangent to all ten cylinders. A
   cylinder kissing a plane tessellates into non-manifold edges even from a
   perfectly valid solid. Adjacent bodies now overlap by `weld_overlap`
   (1.0 mm) so every contact is transversal.

If a mesh ever comes out non-manifold, fix the generator — don't run the
exported file through an STL repair service.

---

## Design decisions worth knowing

- **Board stack leans back 10°.** Gravity holds boards against the back wall at
  any fill level and moves the centre of mass over the 25 mm anti-tip foot.
  Loaded, this is ~3.5 kg standing 305 mm tall.
- **Markers are one continuous row.** A 20 mm bore needs ≥22.5 mm pitch to keep
  a printable web between neighbours. Splitting the row around a centre box
  would need a body wider than the bed.
- **Cap-up, with drain slots.** Cap-up keeps ink at the tip so markers stay
  wet; the slots let dried ink and grit fall through instead of caking.
- **Handle is an arch.** A rectangular slot leaves a flat ceiling that must
  bridge unsupported. An arch has none, and carries load better.
- **The underside is flat.** Recessed pads for stick-on feet were tried and
  removed — each 30 mm recess is a 30 mm unsupported ceiling on the first
  layer. Stick felt pads directly to the flat bottom.
- **Name plates are dovetailed, not square-lipped.** Square retaining lips
  meant the upper lip printed as a long unsupported ledge in mid-air. The
  flared section retains just as well and self-supports.

---

## Known rough edges

- Board thickness assumed **3.5 mm**, pad thickness **8 mm**. Neither was
  measured against the real articles — the coupon exists to catch both.
- **The channel holds more than its nominal 8.** The 40 mm depth was sized as
  8 slots × 5.0 mm, where 1.5 mm of each slot was slack so a board would not
  bind on a divider rib. With the ribs dropped that slack became free space, so
  8 boards occupy 28 mm of a 40 mm trough and up to 11 will fit. Verified by
  pushing progressively thicker stacks through the solid: 11 fits, 12 jams.
  Left deliberately loose — forgiving of warped or thicker boards, and the 10°
  lean keeps the stack tidy even when half empty. Tighten with `slot_w` if a
  snug 8 is ever wanted.
- **The two eraser boxes block front access to the six middle markers.** The
  boxes are 73 mm tall and the tubes 50 mm, so those markers are reached from
  above rather than head-on. Markers stand ~85 mm proud of the tube rim, so
  this is awkward-looking rather than actually obstructive.
