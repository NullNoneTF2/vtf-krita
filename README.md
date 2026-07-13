# VTF Krita

> Beta / experimental release: this project is a personal, learning-oriented effort and not a polished production tool. I threw this together in the hope it would be useful.

A Krita plugin for importing and exporting Valve Texture Format (.vtf) files, with optional .vmt material generation.

![VTF Krita banner](art/vtf-krita-logo-nomargin.png)

## What this project includes

This repository is intended for experimentation, sharing, and feedback. If you use it, please expect rough edges and be willing to report issues.

This repository contains the source for a Krita plugin with:

- VTF import support
- VTF export support
- optional VMT material export
- cross-platform support for Windows and Linux builds of the bundled native library

The plugin is built around a patched VTFLib fork and a portable DXT/S3TC compression backend, so it can work without the proprietary Windows-only nvDXTLib dependency used by some older builds.

## Disclaimer

This project was assembled with help from Claude. The main contribution from that assistance was the Python-side integration work for the Krita plugin. The VTFLib and libtxc_dxtn components were used as supporting libraries to help link the native code into a working DLL, rather than being authored as part of the AI-assisted portion.

## Project layout

- [CONTRIBUTING.md](CONTRIBUTING.md) — how to report issues or contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — community expectations

- [BUILD.md](BUILD.md) — build instructions for the bundled native library
- [PATCHES.md](PATCHES.md) — notes on the VTFLib changes included here
- [patches.diff](patches.diff) — the patch set used for the bundled VTFLib fork
- [VTFLib](VTFLib) — patched VTFLib source
- [libtxc_dxtn](libtxc_dxtn) — portable DXT/S3TC compression backend
- [licenses](licenses) — license texts for bundled third-party code
- [krita-plugin-source](krita-plugin-source) — the Krita plugin Python sources

## Building and installing

1. Read [BUILD.md](BUILD.md) and build the native library for your platform.
2. Place the resulting shared library in the plugin's expected binary location:
   - Windows: [krita-plugin-source/bin/windows](krita-plugin-source/bin/windows)
   - Linux: [krita-plugin-source/bin/linux](krita-plugin-source/bin/linux)
3. Copy the plugin folder into Krita's Python plugin directory and enable it from Krita's Python Plugin Manager.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening issues or submitting changes.

## License notes

This repository bundles third-party code and license files from:

- VTFLib
- libtxc_dxtn
- the upstream VTF-related source tree this plugin was derived from

Please review the files in [licenses](licenses) before redistribution or commercial use.
