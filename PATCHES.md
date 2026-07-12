# Patches applied vs upstream panzi/VTFLib

The exact diff is in `patches.diff` (generated directly against a fresh
clone of https://github.com/panzi/VTFLib, so you can verify/reapply it
yourself). Two changes, both small:

## 1. `CMakeLists.txt`: relax `-Werror`

Upstream builds with `-Werror`, tuned for an older GCC. Newer GCC (and
MinGW's GCC) flag a few additional warnings upstream didn't have, which
turns into hard build failures under `-Werror` for no functional reason.
Changed to `-Wno-error -Wno-attributes` so the build actually completes.
No behavior change, just lets it compile on current toolchains.

## 2. `src/VTFFile.cpp`: two real bug workarounds

**a) Missing S3TC token defines.** `GL/gl.h` on some platforms (notably
MinGW's) doesn't define the `GL_COMPRESSED_*_S3TC_DXT*_EXT` constants the
libtxc_dxtn code path needs -- they normally come from `glext.h`, which
isn't pulled in here. Added `#ifndef`-guarded fallback defines using the
official `GL_EXT_texture_compression_s3tc` registry values, so it compiles
regardless of what the platform's headers happen to include.

**b) `ComputeImageSize()` rejects valid mip levels.** This function
validates that DXT-format width/height are exact multiples of 4 and
throws (`throw 0`, an uncaught C++ exception -- this crashes the whole
process, not just returns an error) if not. But the same function
*already* clamps any dimension below 4 up to 4 a few lines later, which
means this check contradicts its own fallback logic. Every real mip chain
ends in dimensions like 2x2, 2x1, and 1x1 -- so as written, creating *any*
DXT-compressed texture with a full mip chain crashes the process the
moment it reaches the last few mip levels.

Changed the condition so it only rejects dimensions that are `>= 4` and
still misaligned (a genuine error), while dimensions below 4 fall through
to the clamping logic that was already there for exactly this case.

This is a latent upstream bug, not something specific to the Windows/MinGW
build -- it would crash on Linux too under any code path that calls
`ComputeImageSize`/`Create` directly with a full compressed mip chain
(which is exactly what the Krita plugin's Python layer does, since the
*other* upstream limitation -- see below -- rules out using VTFLib's own
one-call mip+compress pipeline).

## Not a patch, but worth knowing: three NVDXT-only dead ends

These aren't source patches (nothing to fix in the C++ -- the functions
are simply unimplemented without the proprietary, Windows-only nvDXTLib),
but they explain why the Krita plugin's Python layer (`vtf_bindings.py`)
does more work itself than you might expect:

- `CVTFFile::GenerateMipmaps()`'s compressed-format path
- `CVTFFile::Resize()` (used for both explicit resizing and internal mip
  downsampling)
- `CVTFFile::ConvertToNormalMap()`

All three call straight into nvDXTLib with no libtxc_dxtn or other
fallback, so they simply fail (or in one case, before patch 2b, crash) on
any non-Windows-with-nvDXTLib build. The plugin works around all three by
reimplementing the equivalent operation itself in Python (bilinear resize,
per-mip-level DXT compression via the functions that *do* have a
libtxc_dxtn path, and Sobel-filter normal map generation) rather than
patching more C++. The resulting `.vtf` files are identical either way --
this is just about which layer does the work.
