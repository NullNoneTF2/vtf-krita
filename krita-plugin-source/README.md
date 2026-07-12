# Krita VTF Import/Export

Import and export Valve Texture Format (`.vtf`) files directly from Krita,
with optional companion `.vmt` material generation. Works on **Windows and
Linux** (see "Platform notes" below for macOS).

Built on a custom compile of [panzi's VTFLib fork](https://github.com/panzi/VTFLib)
(LGPL) linked against [libtxc_dxtn](https://github.com/misyltoad/libtxc_dxtn-cmake)
for portable DXT (S3TC) compression -- no proprietary/Windows-only nvDXTLib
dependency, so DXT read+write works identically on both platforms. See
`krita_vtf/licenses/` for the bundled libraries' license texts.

## Installing

1. Close Krita if it's running.
2. Find your Krita "pykrita" plugin folder:
   - **Windows**: `%APPDATA%\krita\pykrita\`
   - **Linux**: `~/.local/share/krita/pykrita/`
3. Copy both `krita_vtf.desktop` and the `krita_vtf/` folder (the whole
   folder, including `bin/`) into that pykrita directory. You should end up
   with:
   ```
   pykrita/
     krita_vtf.desktop
     krita_vtf/
       __init__.py
       vtf_extension.py
       vtf_export_dialog.py
       vtf_bindings.py
       bin/linux/libVTFLib13.so
       bin/windows/libVTFLib13.dll
       licenses/
   ```
4. Start Krita. Go to **Settings -> Configure Krita -> Python Plugin
   Manager**, find "VTF Import/Export" in the list, and enable it.
   Restart Krita once when prompted.
5. You'll now find **Export as VTF...** and **Import VTF...** under the
   **File** menu.

## Using it

- **Export as VTF...** flattens the active document and opens a dialog
  with the full option set: target format (DXT1/3/5, RGBA8888, BGRA8888,
  and the rest of the VTF format list), VTF version, mipmap generation +
  filter, thumbnail generation, resize method, normal map conversion, VTF
  texture flags (CLAMPS, NOMIP, etc.), and optional `.vmt` generation.
- Canvas sizes that aren't already a power of two are automatically
  resized to the nearest power of two before saving -- this isn't a
  limitation of this plugin, it's a hard requirement of the VTF format
  itself (the same reason VTFCmd has a `-resize` flag).
- **Import VTF...** decodes any VTF format (compressed or not) back to a
  new Krita document at the texture's top mip level.
- VMT generation writes a minimal, ready-to-edit material file the same
  way VTFEdit Reloaded does -- a sensible starting point, not a full
  material authoring tool. Open the `.vmt` in a text editor afterwards to
  fine-tune it.

## Platform notes

- **Windows & Linux**: fully supported, including DXT compression, via
  the bundled binaries.
- **macOS**: not currently supported. Krita on macOS is otherwise a
  normal standalone build, but VTFLib doesn't have a maintained macOS
  build to bundle. This could be revisited if that changes.

## Known limitations (accurate as of this build)

These come from real bugs/gaps found in the upstream VTFLib fork this
plugin bundles, documented here rather than hidden:

- Mipmap generation, DXT compression, and normal-map generation are all
  implemented independently in this plugin's Python layer rather than by
  calling VTFLib's own all-in-one equivalents, because those upstream
  functions only have an nvDXTLib (Windows-only, proprietary, not
  redistributed) code path in this fork. The end result -- a normal,
  spec-compliant `.vtf` file -- is the same either way.
- A real memory-safety bug in the bundled DXT compressor (it reads a
  full 4x4 pixel block unconditionally, regardless of the requested
  size) is worked around by padding small mip levels up to 4x4 before
  compressing them.
- A validation bug in VTFLib's own image-size calculation (it rejected
  any DXT mip level whose dimensions weren't an exact multiple of 4,
  which is every mip chain's tail end) was patched in the bundled build.

## Rebuilding the binaries from source

If you want to rebuild `libVTFLib13.so`/`.dll` yourself (e.g. to track
upstream changes), the base is panzi/VTFLib with:
- `-DUSE_LIBTXC_DXTN=ON`
- linked against a build of `misyltoad/libtxc_dxtn-cmake`
- the `ComputeImageSize` DXT-multiple-of-4 validation relaxed to only
  reject dimensions >= 4 that are misaligned (see `licenses/` for a note
  on where this was changed, or diff against upstream `VTFFile.cpp`)

Windows builds were cross-compiled with MinGW-w64 (`x86_64-w64-mingw32-gcc`)
rather than requiring MSVC.
