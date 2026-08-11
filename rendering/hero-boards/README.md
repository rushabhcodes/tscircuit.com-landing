# Hero board render

This directory contains the complete Blender input scene as code and the four
self-contained GLB models used to render the landing-page hero image.

The composition intentionally uses a top-down orthographic camera. All four
boards are imported into one Blender scene, so their transforms, lighting, and
shadows are evaluated together. The render is written directly as a transparent
1600 x 1500 PNG; there is no contrast, brightness, or compositing pass after
Blender.

## Requirements

- Blender 4.2 or newer available as `blender`
- Enough memory to import the four embedded GLB models (8 GB recommended)

## Render the production image

Run this from the repository root:

```sh
blender --background \
  --python rendering/hero-boards/render.py \
  -- \
  --engine cycles \
  --samples 96
```

The default output is `assets/hero-board-four-real-3d.png`. To render elsewhere,
append `--output /absolute/path/to/output.png`.

For a fast composition preview:

```sh
blender --background \
  --python rendering/hero-boards/render.py \
  -- \
  --engine eevee \
  --samples 32 \
  --output /tmp/hero-board-preview.png
```

## Adjusting the composition

Board size, position, and rotation live in `BOARD_SPECS` near the top of
`render.py`. Camera framing is controlled by `camera_data.ortho_scale` and
`camera.location` in `configure_scene`.

Each board receives the same off-center local key-light relationship, plus a
shared cool fill and mint rim. The exporter-authored board textures are kept
intact; Blender only applies component-finish and normal-cleanup heuristics.

## Model provenance

The checked-in GLBs were generated with the realistic board-surface output from
`circuit-json-to-gltf` commit `d95429b` and have 2048 px embedded board textures.
They are the reproducible source inputs for Blender:

- `rp2040-blue-soldermask.glb` — tscircuit RP2040 hero board, blue soldermask and white silkscreen
- `gameboy.glb` — tscircuit Game Boy board, red soldermask and white silkscreen
- `nrf52810.glb` — tscircuit nRF52810 board
- `attiny85-arcade-keychain.glb` — [rushabhcodes/Attiny85-Arcade-Keychain](https://tscircuit.com/rushabhcodes/Attiny85-Arcade-Keychain#3d)

The models contain their meshes and textures, so reproducing the hero PNG does
not require downloading CAD assets or rebuilding Circuit JSON.
