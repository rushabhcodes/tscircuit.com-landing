# Regenerating hero-board GLBs

The landing-page render has two distinct build steps:

1. Circuit JSON is converted into a self-contained GLB with realistic PCB
   textures.
2. Blender imports the checked-in GLBs and renders the shared hero composition.

This document covers the first step. See [README.md](README.md) for the Blender
render command.

## Use the pinned exporter

The current hero models were generated with `circuit-json-to-gltf` commit
`d95429b`. Pinning the exporter keeps its material model and texture generation
stable when the package changes later.

```sh
git clone https://github.com/tscircuit/circuit-json-to-gltf.git
cd circuit-json-to-gltf
git checkout d95429b
bun install
bun run build
```

The generated module is `dist/index.js` in that checkout.

## Start with Circuit JSON

Download Circuit JSON from the tscircuit project export menu and keep the full
array of elements, including the `pcb_board`, PCB primitives, component
placements, and CAD model URLs. The exporter fetches referenced CAD models while
generating the GLB, but the final GLB embeds its meshes and board textures and
is self-contained.

Board colors belong on the `pcb_board` element:

```json
{
  "type": "pcb_board",
  "solder_mask_color": "#d94a4a",
  "silkscreen_color": "#ffffff"
}
```

`solder_mask_color` is the canonical field. The legacy `soldermask_color` alias
is also accepted. When only the solder-mask color is set, the exporter derives
the covered-copper color, substrate edge color, and a contrasting silkscreen
color. Set `silkscreen_color` when the design needs a specific legend color,
such as the white legend used by the hero boards.

## Generate a GLB

Save the following as `/tmp/regenerate-hero-glb.mjs`:

```js
import { readFile, writeFile } from "node:fs/promises"
import { pathToFileURL } from "node:url"

const [sourcePath, outputPath, solderMask, silkscreen] = process.argv.slice(2)
const exporterPath = process.env.CIRCUIT_JSON_TO_GLTF_DIST

if (!sourcePath || !outputPath || !solderMask || !exporterPath) {
  throw new Error(
    "Usage: CIRCUIT_JSON_TO_GLTF_DIST=/path/to/dist/index.js " +
      "bun regenerate-hero-glb.mjs input.json output.glb '#d94a4a' ['#ffffff']",
  )
}

const { convertCircuitJsonTo3D, convertSceneToGLTF } = await import(
  pathToFileURL(exporterPath).href
)
const circuitJson = JSON.parse(await readFile(sourcePath, "utf8"))

if (!Array.isArray(circuitJson)) {
  throw new Error("Expected Circuit JSON to be an array of elements")
}

const recoloredCircuitJson = circuitJson.map((element) => {
  if (element.type !== "pcb_board") return element

  const recoloredBoard = {
    ...element,
    solder_mask_color: solderMask,
  }

  delete recoloredBoard.soldermask_color
  if (silkscreen) recoloredBoard.silkscreen_color = silkscreen
  else delete recoloredBoard.silkscreen_color

  return recoloredBoard
})

const scene = await convertCircuitJsonTo3D(recoloredCircuitJson, {
  componentColor: "#f4f5f7",
  copperColor: "#d7b56d",
  drillColor: "#11151d",
  boardDrillQuality: "high",
  boardSurfaceMode: "realistic",
  renderBoardTextures: true,
  textureResolution: 2048,
  showBoundingBoxes: false,
})
const glb = await convertSceneToGLTF(scene, {
  binary: true,
  embedImages: true,
})

await writeFile(outputPath, new Uint8Array(glb))
console.log(`Wrote ${outputPath}`)
```

Run it from the landing-page repository. For example, this regenerates the
top-right Game Boy board with red solder mask and white silkscreen:

```sh
CIRCUIT_JSON_TO_GLTF_DIST=/absolute/path/to/circuit-json-to-gltf/dist/index.js \
  bun /tmp/regenerate-hero-glb.mjs \
  /absolute/path/to/gameboy-circuit.json \
  rendering/hero-boards/models/gameboy.glb \
  '#d94a4a' \
  '#ffffff'
```

Use the same command with a different output filename and color values for the
other boards. Omit the final silkscreen argument to let the exporter derive a
contrasting legend color from the solder mask.

## Optional material overrides

For normal recoloring, prefer `pcb_board.solder_mask_color` so the related board
colors stay coordinated automatically. `convertCircuitJsonTo3D` also accepts
explicit overrides when art direction requires them:

- `pcbColor`: board-face/solder-mask color
- `boardSideColor`: substrate edge color
- `solderMaskWithCopperColor`: covered traces and copper pours
- `silkscreenColor`: legend color
- `copperColor`: exposed copper and pads
- `drillColor`: drilled openings

Explicit options take precedence over board metadata. Avoid setting them unless
the derived palette is unsuitable, because independent overrides can make the
board face, traces, and edges look unrelated.

## Re-render the hero

After replacing a GLB under `rendering/hero-boards/models/`, render a quick
Eevee preview first, then regenerate the production Cycles image using the
commands in [README.md](README.md). Do not apply a separate contrast,
brightness, or compositing pass; the checked-in PNG should match Blender's
output.
