# Patches applied relative to upstream panzi/VTFLib

The exact diff is in [patches.diff](patches.diff). Three changes are included:

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

## 3. CMakeLists.txt: statically link the MinGW runtime on Windows

When built with MinGW-w64 GCC, libVTFLib13.dll dynamically depended on
libgcc_s_seh-1.dll, libstdc++-6.dll, and libwinpthread-1.dll from the
toolchain's runtime. Those DLLs only exist on a machine with a matching
MSYS2/MinGW install (such as the CI build runner), so the plugin failed to
load for end users with a "Could not find module ... (or one of its
dependencies)" ctypes error, even though libVTFLib13.dll itself was present.
The patch adds `-static-libgcc -static-libstdc++` plus a whole-archive static
link of `winpthread` to `CMAKE_EXE_LINKER_FLAGS`/`CMAKE_SHARED_LINKER_FLAGS`
on Windows GNU builds, so the shipped DLL carries its own runtime and has no
external dependency on the build toolchain being installed.

## Notes on the non-patched nvDXT-only paths

Three VTFLib functions are still unavailable without the proprietary
Windows-only nvDXTLib dependency:

- CVTFFile::GenerateMipmaps() for compressed formats
- CVTFFile::Resize()
- CVTFFile::ConvertToNormalMap()

The plugin implements equivalent behavior in Python where needed so that the
same workflow works on non-Windows builds and on builds without nvDXTLib.

## v0.2.0 - 2026-07-14

- Fix: Exported VTF version honored from the export dialog (no longer stuck at 7.2).
- Feature: Import preserves source alpha as a bound transparency mask when possible; fallback to a separate `Alpha Mask` layer.
- UI: Export dialog adds `Full Options` toggle to show advanced formats and a `Use Defaults` button.
- UX: Export dialog option values persist via `QSettings` and auto-save on change.
- Feature: Animated VTF import prompts to edit a single frame or export all frames to a folder.
- Feature: Create Animated VTF from Frames, new menu action to build animated VTFs from an ordered frames folder.
- Feature: Animated VTF export supports compressed formats (DXT1/DXT5) with per-frame, per-mipmap conversion.
- UX: Exports run in background threads with progress dialogs and cancel support to avoid freezing Krita for long exports.
- Misc: Added `EXPORTABLE_FORMATS_CORE` / `EXPORTABLE_FORMATS_FULL` to simplify the default Export UI.
