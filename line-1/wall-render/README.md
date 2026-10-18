# Wall finishing for mark 23

The cave painting was edited with the built-in image-generation tool. This
local Node helper only preserves the ancestral pixels outside a bounded empty
patch and produces the required JPEG. It has no network or package installation
at runtime. It is separate from the Python-only benchmark tools.

The new paint was composited inside original-image bounds
`[305,322,649,535)` with a 12-pixel edge blend. All decoded RGB pixels outside
that patch exactly equal the supplied predecessor `wall-v2.png`. The comparison
reported 71,711 changed pixels, all inside the patch. Both earlier Pepe figures,
the balance and branching pebble paths are outside it. No ancestral paint is
removed or drawn again.

Regenerate just the 512-square record preview, from the workspace root:

```sh
node line-1/wall-render/finish_wall.js preview artifacts/line-1/wall-v3.png dist/line-1/23.jpg
```

The resulting JPEG was 65,600 bytes and was separately decoded and inspected.
PNG decoding/encoding uses Node's built-in `zlib`; JPEG encoding uses the
unmodified ordinary source file `vendor/jpeg_encoder.js` from jpeg-js v0.4.4:
https://raw.githubusercontent.com/jpeg-js/jpeg-js/v0.4.4/lib/encoder.js
Its copyright and BSD license are retained at the beginning of that file.
This vendored file is delivered with the source; no npm package, submodule,
remote image, API token or installed image library is needed for preview work.
The generator input itself is not retained as an additional picture.

The helper supports noninterlaced 8-bit RGB/RGBA PNGs, validates chunk CRCs,
limits dimensions to 4096, and keeps explicit file paths inside the workspace.
It is a small finishing utility for these trusted images, not a general PNG
security boundary. The generation prompt and visual review are in
`line-1/wall-review-23.json`. No generator call is made by this helper.
