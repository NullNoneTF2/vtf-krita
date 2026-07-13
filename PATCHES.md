# Patches applied relative to upstream panzi/VTFLib

The exact diff is in [patches.diff](patches.diff). Two changes are included:

## 1. CMakeLists.txt: relax -Werror

Upstream builds with -Werror for an older GCC toolchain. Newer GCC versions
and MinGW builds can report additional warnings that do not indicate a
functional problem. The patch changes the build flags to -Wno-error -Wno-attributes
so the library can compile cleanly on current toolchains.

## 2. src/VTFFile.cpp: two bug workarounds

### a) Missing S3TC token defines

Some platforms do not provide the GL_COMPRESSED_*_S3TC_DXT*_EXT constants
through GL/gl.h alone. The patch adds guarded fallback definitions using the
standard GL_EXT_texture_compression_s3tc values so the libtxc_dxtn code path
still compiles.

### b) ComputeImageSize() rejects valid mip levels

The original logic rejected some valid DXT mip dimensions before the later
clamping logic could handle them. The patch narrows the rejection to dimensions
that are both at least 4 pixels and still misaligned, which allows valid
smaller mip levels to proceed correctly.

## Notes on the non-patched nvDXT-only paths

Three VTFLib functions are still unavailable without the proprietary
Windows-only nvDXTLib dependency:

- CVTFFile::GenerateMipmaps() for compressed formats
- CVTFFile::Resize()
- CVTFFile::ConvertToNormalMap()

The plugin implements equivalent behavior in Python where needed so that the
same workflow works on non-Windows builds and on builds without nvDXTLib.
