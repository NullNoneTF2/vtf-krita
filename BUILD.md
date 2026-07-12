# Building libVTFLib13 from source

This builds the exact library the Krita VTF plugin uses:
[panzi's VTFLib fork](https://github.com/panzi/VTFLib) (LGPL) linked against
[libtxc_dxtn](https://github.com/misyltoad/libtxc_dxtn-cmake) for portable
DXT/S3TC compression -- no proprietary nvDXTLib needed, so DXT read+write
works identically on Windows and Linux.

Two small patches are applied to VTFLib's source compared to upstream --
see `PATCHES.md` for exactly what and why. Both are already applied in the
`VTFLib/` folder here, so you don't need to do anything extra; it's just
there so you know what's different if you ever diff against upstream.

---

## Building on Windows (MSYS2 + MinGW-w64)

This is the recommended path -- no Visual Studio needed, and it's exactly
what produced the `.dll` shipped in the plugin.

### 1. Install MSYS2

Download and install from **https://www.msys2.org/** (just run the
installer, defaults are fine).

### 2. Open the right terminal

MSYS2 installs several shortcuts in your Start Menu -- use **"MSYS2 MINGW64"**
specifically (not plain "MSYS2", not "MINGW32", not "UCRT64"). This matters:
picking the wrong one silently builds a 32-bit binary or one linked against
the wrong runtime.

### 3. Install the toolchain

In that MINGW64 terminal:

```bash
pacman -Syu    # if it asks you to close and reopen the terminal and re-run this, do that
pacman -S mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-mesa git make
```

(`mingw-w64-x86_64-mesa` provides `GL/gl.h`, which VTFLib's header needs
purely for a few type definitions -- no actual OpenGL/graphics driver
involved.)

### 4. Build libtxc_dxtn first

From wherever you extracted this source package:

```bash
cd libtxc_dxtn
mkdir build && cd build
cmake .. -G "MSYS Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON
make -j$(nproc)
```

This produces `liblibtxc_dxtn.a` in that `build` folder.

### 5. Build VTFLib against it

```bash
cd ../../VTFLib
mkdir build && cd build
cmake .. -G "MSYS Makefiles" -DCMAKE_BUILD_TYPE=Release \
  -DUSE_LIBTXC_DXTN=ON \
  -DLIBTXC_DXTN_LIBRARY=$(pwd)/../../libtxc_dxtn/build/liblibtxc_dxtn.a \
  -DCMAKE_SHARED_LINKER_FLAGS="-static-libgcc -static-libstdc++"
make -j$(nproc)
```

**The `-DCMAKE_SHARED_LINKER_FLAGS` bit matters.** Without it, the resulting
DLL dynamically depends on `libgcc_s_seh-1.dll` and `libstdc++-6.dll` --
fine on your machine where MSYS2 is installed, but it'll fail to load with
a misleading "could not find module" error on any other Windows machine
that doesn't have MinGW installed. Statically linking those in makes the
DLL fully self-contained.

Your finished DLL is at `VTFLib/build/src/libVTFLib13.dll`. Verify it has
no stray dependencies:

```bash
objdump -p src/libVTFLib13.dll | grep "DLL Name"
```

You should see only `KERNEL32.dll` and `msvcrt.dll`. If you see
`libgcc_s_seh-1.dll` or `libstdc++-6.dll` in there, the linker flags above
didn't take -- double check you're in the MINGW64 (not UCRT64 or MSYS)
terminal and re-run the `cmake ..` configure step.

### 6. Install it into the plugin

Copy `libVTFLib13.dll` into the plugin's
`krita_vtf\bin\windows\libVTFLib13.dll`, overwriting the existing one.

---

## Building on Linux (including Arch, for whenever you get there)

### Arch

```bash
sudo pacman -S base-devel cmake mesa git
```

### Debian/Ubuntu

```bash
sudo apt install build-essential cmake libgl1-mesa-dev git
```

### Build (same on both)

```bash
cd libtxc_dxtn
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON
make -j$(nproc)

cd ../../VTFLib
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release \
  -DUSE_LIBTXC_DXTN=ON \
  -DLIBTXC_DXTN_LIBRARY=$(pwd)/../../libtxc_dxtn/build/liblibtxc_dxtn.a
make -j$(nproc)
```

Output: `VTFLib/build/src/libVTFLib13.so`. Copy it into
`krita_vtf/bin/linux/libVTFLib13.so`.

---

## Sanity-checking your build

Quick Python smoke test (run from wherever `libVTFLib13.dll`/`.so` ended up,
adjust the filename for your platform):

```python
import ctypes
lib = ctypes.CDLL("./libVTFLib13.dll")   # or "./libVTFLib13.so" on Linux
lib.vlInitialize.restype = ctypes.c_bool
print("vlInitialize:", lib.vlInitialize())   # should print True
```

If that prints `True` with no errors, the build is good.
