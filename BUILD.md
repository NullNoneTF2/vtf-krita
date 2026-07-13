# Building libVTFLib13 from source

These instructions build the native library used by the Krita VTF plugin.
The build uses [panzi's VTFLib fork](https://github.com/panzi/VTFLib) (LGPL)
linked against [libtxc_dxtn](https://github.com/misyltoad/libtxc_dxtn-cmake)
for portable DXT/S3TC compression. This avoids the proprietary nvDXTLib
dependency and keeps DXT read/write support consistent on Windows and Linux.

Two small patches are already applied in the [VTFLib](VTFLib) directory.
See [PATCHES.md](PATCHES.md) for details.

---

## Building on Windows (MSYS2 + MinGW-w64)

This is the recommended path because it produces a self-contained DLL without
requiring Visual Studio.

### 1. Install MSYS2

Download and install MSYS2 from https://www.msys2.org/ and use the default
settings.

### 2. Open the correct terminal

Use the MSYS2 MINGW64 terminal. This matters because the wrong terminal can
produce a 32-bit build or a binary linked against the wrong runtime.

### 3. Install the toolchain

In the MINGW64 terminal, run:

```bash
pacman -Syu
pacman -S mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-mesa git make
```

The Mesa package provides GL/gl.h for a few VTFLib type definitions.

### 4. Build libtxc_dxtn first

From the repository root:

```bash
cd libtxc_dxtn
mkdir build && cd build
cmake .. -G "MSYS Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON
make -j$(nproc)
```

This produces liblibtxc_dxtn.a in the build directory.

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

The shared-linker flags are important because they make the resulting DLL
self-contained instead of depending on MinGW runtime DLLs.

The finished DLL is at VTFLib/build/src/libVTFLib13.dll. Verify it has no
unexpected dependencies:

```bash
objdump -p src/libVTFLib13.dll | grep "DLL Name"
```

You should see only KERNEL32.dll and msvcrt.dll.

### 6. Install it into the plugin

Copy libVTFLib13.dll into the plugin's binary folder, replacing the existing
file at krita_vtf/bin/windows/libVTFLib13.dll.

---

## Building on Linux

### Arch

```bash
sudo pacman -S base-devel cmake mesa git
```

### Debian/Ubuntu

```bash
sudo apt install build-essential cmake libgl1-mesa-dev git
```

### Build steps

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

The output library is VTFLib/build/src/libVTFLib13.so. Copy it to
krita_vtf/bin/linux/libVTFLib13.so.

---

## Sanity-checking the build

A simple Python smoke test:

```python
import ctypes
lib = ctypes.CDLL("./libVTFLib13.dll")   # or "./libVTFLib13.so" on Linux
lib.vlInitialize.restype = ctypes.c_bool
print("vlInitialize:", lib.vlInitialize())   # should print True
```

If this prints True without errors, the build is working.
