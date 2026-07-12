# vtf_bindings.py
#
# ctypes wrapper around the bundled VTFLib shared library (libVTFLib13.so /
# libVTFLib13.dll), plus high level read/write helpers used by the Krita
# plugin. This module has no Krita/PyQt dependency and can be tested/used
# standalone.
#
# Bundled binary: a build of panzi's VTFLib fork (LGPL) linked against
# libtxc_dxtn (permissive/MIT-style license) for portable S3TC (DXT)
# compression -- no proprietary/Windows-only nvDXTLib required, so DXT
# read+write works identically on Linux and Windows.
#
# Known upstream limitation this module works around: VTFLib's own
# all-in-one "create + generate mipmaps + compress" call only has an
# nvDXTLib code path in this fork, so it fails for DXT-format textures.
# The per-buffer primitives (resize, gamma, convert-to/from-RGBA8888) DO
# have a working libtxc_dxtn path, so we build the mip chain ourselves,
# level by level, using those primitives instead of the broken batch call.

import ctypes
import os
import platform
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def _library_path():
    system = platform.system()
    if system == "Windows":
        return os.path.join(_THIS_DIR, "bin", "windows", "libVTFLib13.dll")
    elif system == "Linux":
        return os.path.join(_THIS_DIR, "bin", "linux", "libVTFLib13.so")
    else:
        raise RuntimeError(
            "The bundled VTFLib binary only covers Windows and Linux "
            "(system reported: {}). macOS is not currently supported."
            .format(system)
        )


class VTFError(RuntimeError):
    """Raised for any failure reported by VTFLib itself."""
    pass


# ---------------------------------------------------------------------------
# Enums (mirrors VTFFormat.h)
# ---------------------------------------------------------------------------

IMAGE_FORMAT = {
    "RGBA8888": 0, "ABGR8888": 1, "RGB888": 2, "BGR888": 3, "RGB565": 4,
    "I8": 5, "IA88": 6, "P8": 7, "A8": 8, "RGB888_BLUESCREEN": 9,
    "BGR888_BLUESCREEN": 10, "ARGB8888": 11, "BGRA8888": 12,
    "DXT1": 13, "DXT3": 14, "DXT5": 15, "BGRX8888": 16, "BGR565": 17,
    "BGRX5551": 18, "BGRA4444": 19, "DXT1_ONEBITALPHA": 20,
    "BGRA5551": 21, "UV88": 22, "UVWQ8888": 23, "RGBA16161616F": 24,
    "RGBA16161616": 25, "UVLX8888": 26,
}
IMAGE_FORMAT_NAME = {v: k for k, v in IMAGE_FORMAT.items()}
IMAGE_FORMAT_NONE = -1

# Formats it's safe/sane to offer for export in a first version. (Some of
# the more exotic ones -- NV_* depth formats, XBox linear formats -- are
# excluded because they aren't meaningful export targets from a paint app.)
EXPORTABLE_FORMATS = [
    "RGBA8888", "ABGR8888", "ARGB8888", "BGRA8888",
    "RGB888", "BGR888", "RGB565", "BGR565",
    "I8", "IA88", "A8",
    "RGB888_BLUESCREEN", "BGR888_BLUESCREEN",
    "BGRX8888", "BGRX5551", "BGRA4444", "BGRA5551",
    "DXT1", "DXT1_ONEBITALPHA", "DXT3", "DXT5",
    "UV88", "UVWQ8888", "UVLX8888",
]

COMPRESSED_FORMATS = {"DXT1", "DXT1_ONEBITALPHA", "DXT3", "DXT5"}

TEXTUREFLAGS = {
    "POINTSAMPLE": 0x00000001, "TRILINEAR": 0x00000002, "CLAMPS": 0x00000004,
    "CLAMPT": 0x00000008, "ANISOTROPIC": 0x00000010, "HINT_DXT5": 0x00000020,
    "NORMAL": 0x00000080, "NOMIP": 0x00000100, "NOLOD": 0x00000200,
    "MINMIP": 0x00000400, "PROCEDURAL": 0x00000800, "RENDERTARGET": 0x00008000,
    "DEPTHRENDERTARGET": 0x00010000, "NODEBUGOVERRIDE": 0x00020000,
    "SINGLECOPY": 0x00040000, "NODEPTHBUFFER": 0x00800000, "CLAMPU": 0x02000000,
    "VERTEXTEXTURE": 0x04000000, "SSBUMP": 0x08000000, "BORDER": 0x20000000,
}

MIPMAP_FILTER = {
    "POINT": 0, "BOX": 1, "TRIANGLE": 2, "QUADRATIC": 3, "CUBIC": 4,
    "CATROM": 5, "MITCHELL": 6, "GAUSSIAN": 7, "SINC": 8, "BESSEL": 9,
    "HANNING": 10, "HAMMING": 11, "BLACKMAN": 12, "KAISER": 13,
}

SHARPEN_FILTER = {
    "NONE": 0, "NEGATIVE": 1, "LIGHTER": 2, "DARKER": 3, "CONTRASTMORE": 4,
    "CONTRASTLESS": 5, "SMOOTHEN": 6, "SHARPENSOFT": 7, "SHARPENMEDIUM": 8,
    "SHARPENSTRONG": 9, "FINDEDGES": 10, "CONTOUR": 11, "EDGEDETECT": 12,
    "EDGEDETECTSOFT": 13, "EMBOSS": 14, "MEANREMOVAL": 15, "UNSHARP": 16,
    "XSHARPEN": 17, "WARPSHARP": 18,
}

RESIZE_METHOD = {
    "NEAREST_POWER2": 0, "BIGGEST_POWER2": 1, "SMALLEST_POWER2": 2, "SET": 3,
}

KERNEL_FILTER = {"4X": 0, "3X3": 1, "5X5": 2, "7X7": 3, "9X9": 4, "DUDV": 5}

HEIGHT_CONVERSION_METHOD = {
    "ALPHA": 0, "AVERAGE_RGB": 1, "BIASED_RGB": 2, "RED": 3, "GREEN": 4,
    "BLUE": 5, "MAX_RGB": 6, "COLORSPACE": 7,
}

NORMAL_ALPHA_RESULT = {"NOCHANGE": 0, "HEIGHT": 1, "BLACK": 2, "WHITE": 3}

VTF_VERSIONS = ["7.1", "7.2", "7.3", "7.4", "7.5"]


class SVTFCreateOptions(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("uiVersion", ctypes.c_uint * 2),
        ("ImageFormat", ctypes.c_int),
        ("uiFlags", ctypes.c_uint),
        ("uiStartFrame", ctypes.c_uint),
        ("sBumpScale", ctypes.c_float),
        ("sReflectivity", ctypes.c_float * 3),
        ("bMipmaps", ctypes.c_ubyte),
        ("MipmapFilter", ctypes.c_int),
        ("MipmapSharpenFilter", ctypes.c_int),
        ("bThumbnail", ctypes.c_ubyte),
        ("bReflectivity", ctypes.c_ubyte),
        ("bResize", ctypes.c_ubyte),
        ("ResizeMethod", ctypes.c_int),
        ("ResizeFilter", ctypes.c_int),
        ("ResizeSharpenFilter", ctypes.c_int),
        ("uiResizeWidth", ctypes.c_uint),
        ("uiResizeHeight", ctypes.c_uint),
        ("bResizeClamp", ctypes.c_ubyte),
        ("uiResizeClampWidth", ctypes.c_uint),
        ("uiResizeClampHeight", ctypes.c_uint),
        ("bGammaCorrection", ctypes.c_ubyte),
        ("sGammaCorrection", ctypes.c_float),
        ("bNormalMap", ctypes.c_ubyte),
        ("KernelFilter", ctypes.c_int),
        ("HeightConversionMethod", ctypes.c_int),
        ("NormalAlphaResult", ctypes.c_int),
        ("bNormalMinimumZ", ctypes.c_ubyte),
        ("sNormalScale", ctypes.c_float),
        ("bNormalWrap", ctypes.c_ubyte),
        ("bNormalInvertX", ctypes.c_ubyte),
        ("bNormalInvertY", ctypes.c_ubyte),
        ("bNormalInvertZ", ctypes.c_ubyte),
        ("bSphereMap", ctypes.c_ubyte),
    ]


def _resize_rgba(rgba_bytes, src_w, src_h, dst_w, dst_h):
    """Resize an RGBA8888 buffer with bilinear interpolation.

    VTFLib's own vlImageResize() turns out to have the same problem as the
    batch mipmap+DXT call: this fork's implementation is entirely
    nvDXTLib-only with no libtxc_dxtn (or any other) fallback, so it simply
    fails on Linux/Windows builds without the proprietary library. Rather
    than pull in another native dependency, we do resizing ourselves here.
    Uses numpy if it happens to be importable (faster), otherwise falls
    back to a pure-Python implementation -- no external dependency is
    required either way.
    """
    if (src_w, src_h) == (dst_w, dst_h):
        return bytes(rgba_bytes)

    try:
        import numpy as np

        src = np.frombuffer(rgba_bytes, dtype=np.uint8).reshape(
            src_h, src_w, 4).astype(np.float32)

        # Precompute source coordinates for each destination pixel.
        xs = (np.arange(dst_w) + 0.5) * (src_w / dst_w) - 0.5
        ys = (np.arange(dst_h) + 0.5) * (src_h / dst_h) - 0.5
        xs = np.clip(xs, 0, src_w - 1)
        ys = np.clip(ys, 0, src_h - 1)

        x0 = np.floor(xs).astype(np.int32)
        x1 = np.clip(x0 + 1, 0, src_w - 1)
        y0 = np.floor(ys).astype(np.int32)
        y1 = np.clip(y0 + 1, 0, src_h - 1)

        wx = (xs - x0).reshape(1, dst_w, 1)
        wy = (ys - y0).reshape(dst_h, 1, 1)

        top = src[y0][:, x0] * (1 - wx) + src[y0][:, x1] * wx
        bottom = src[y1][:, x0] * (1 - wx) + src[y1][:, x1] * wx
        out = top * (1 - wy) + bottom * wy
        return out.round().astype(np.uint8).tobytes()
    except ImportError:
        pass

    # Pure-Python fallback: fine for typical texture sizes; not fast for
    # very large images, but requires nothing beyond the standard library.
    out = bytearray(dst_w * dst_h * 4)
    x_ratio = src_w / dst_w
    y_ratio = src_h / dst_h
    for dy in range(dst_h):
        sy = (dy + 0.5) * y_ratio - 0.5
        sy = min(max(sy, 0), src_h - 1)
        y0 = int(sy)
        y1 = min(y0 + 1, src_h - 1)
        wy = sy - y0
        row0_base = y0 * src_w * 4
        row1_base = y1 * src_w * 4
        out_row_base = dy * dst_w * 4
        for dx in range(dst_w):
            sx = (dx + 0.5) * x_ratio - 0.5
            sx = min(max(sx, 0), src_w - 1)
            x0 = int(sx)
            x1 = min(x0 + 1, src_w - 1)
            wx = sx - x0
            i00 = row0_base + x0 * 4
            i01 = row0_base + x1 * 4
            i10 = row1_base + x0 * 4
            i11 = row1_base + x1 * 4
            o = out_row_base + dx * 4
            for c in range(4):
                top = rgba_bytes[i00 + c] * (1 - wx) + rgba_bytes[i01 + c] * wx
                bot = rgba_bytes[i10 + c] * (1 - wx) + rgba_bytes[i11 + c] * wx
                out[o + c] = int(round(top * (1 - wy) + bot * wy))
    return bytes(out)


def _height_from_rgba(r, g, b, a, method):
    if method == "ALPHA":
        return a
    if method == "AVERAGE_RGB":
        return (r + g + b) / 3.0
    if method == "BIASED_RGB":
        return r * 0.3 + g * 0.59 + b * 0.11
    if method == "RED":
        return r
    if method == "GREEN":
        return g
    if method == "BLUE":
        return b
    if method == "MAX_RGB":
        return max(r, g, b)
    return (r + g + b) / 3.0  # COLORSPACE / fallback


def _generate_normal_map(rgba_bytes, w, h, height_method="AVERAGE_RGB",
                          scale=2.0, wrap=False, invert_x=False,
                          invert_y=False, alpha_result="NOCHANGE"):
    """Standard Sobel-filter height-to-normal-map conversion. VTFLib's own
    ConvertToNormalMap() has no implementation at all without nvDXTLib in
    this fork (not even a degraded fallback), so this replaces it entirely
    rather than working around a partial implementation."""
    try:
        import numpy as np

        arr = np.frombuffer(rgba_bytes, dtype=np.uint8).reshape(h, w, 4).astype(np.float32)
        r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
        if height_method == "ALPHA":
            height = a
        elif height_method == "BIASED_RGB":
            height = r * 0.3 + g * 0.59 + b * 0.11
        elif height_method == "RED":
            height = r
        elif height_method == "GREEN":
            height = g
        elif height_method == "BLUE":
            height = b
        elif height_method == "MAX_RGB":
            height = np.maximum(np.maximum(r, g), b)
        else:
            height = (r + g + b) / 3.0
        height = height / 255.0

        mode = "wrap" if wrap else "edge"
        hl = np.pad(height, ((0, 0), (1, 0)), mode=mode)[:, :-1]
        hr = np.pad(height, ((0, 0), (0, 1)), mode=mode)[:, 1:]
        hu = np.pad(height, ((1, 0), (0, 0)), mode=mode)[:-1, :]
        hd = np.pad(height, ((0, 1), (0, 0)), mode=mode)[1:, :]

        dx = (hr - hl) * scale
        dy = (hd - hu) * scale
        if invert_x:
            dx = -dx
        if invert_y:
            dy = -dy

        nz = np.ones_like(height)
        length = np.sqrt(dx * dx + dy * dy + nz * nz)
        nx, ny, nz = -dx / length, -dy / length, nz / length

        out = np.empty((h, w, 4), dtype=np.uint8)
        out[..., 0] = np.clip((nx * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
        out[..., 1] = np.clip((ny * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
        out[..., 2] = np.clip((nz * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
        if alpha_result == "HEIGHT":
            out[..., 3] = (height * 255).astype(np.uint8)
        elif alpha_result == "BLACK":
            out[..., 3] = 0
        elif alpha_result == "WHITE":
            out[..., 3] = 255
        else:
            out[..., 3] = a.astype(np.uint8)
        return out.tobytes()
    except ImportError:
        pass

    # Pure-Python fallback -- fine for typical texture sizes.
    def px(x, y):
        if wrap:
            x, y = x % w, y % h
        else:
            x, y = min(max(x, 0), w - 1), min(max(y, 0), h - 1)
        i = (y * w + x) * 4
        return rgba_bytes[i], rgba_bytes[i + 1], rgba_bytes[i + 2], rgba_bytes[i + 3]

    out = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            r_l, g_l, b_l, a_l = px(x - 1, y)
            r_r, g_r, b_r, a_r = px(x + 1, y)
            r_u, g_u, b_u, a_u = px(x, y - 1)
            r_d, g_d, b_d, a_d = px(x, y + 1)
            hl = _height_from_rgba(r_l, g_l, b_l, a_l, height_method) / 255.0
            hr = _height_from_rgba(r_r, g_r, b_r, a_r, height_method) / 255.0
            hu = _height_from_rgba(r_u, g_u, b_u, a_u, height_method) / 255.0
            hd = _height_from_rgba(r_d, g_d, b_d, a_d, height_method) / 255.0
            dx = (hr - hl) * scale
            dy = (hd - hu) * scale
            if invert_x:
                dx = -dx
            if invert_y:
                dy = -dy
            length = (dx * dx + dy * dy + 1.0) ** 0.5
            nx, ny, nz = -dx / length, -dy / length, 1.0 / length
            i = (y * w + x) * 4
            out[i + 0] = max(0, min(255, int(round((nx * 0.5 + 0.5) * 255))))
            out[i + 1] = max(0, min(255, int(round((ny * 0.5 + 0.5) * 255))))
            out[i + 2] = max(0, min(255, int(round((nz * 0.5 + 0.5) * 255))))
            if alpha_result == "HEIGHT":
                r0, g0, b0, a0 = px(x, y)
                out[i + 3] = int(round(
                    _height_from_rgba(r0, g0, b0, a0, height_method)))
            elif alpha_result == "BLACK":
                out[i + 3] = 0
            elif alpha_result == "WHITE":
                out[i + 3] = 255
            else:
                out[i + 3] = px(x, y)[3]
    return bytes(out)


_lib = None


def _load_library():
    global _lib
    if _lib is not None:
        return _lib

    path = _library_path()
    if not os.path.exists(path):
        raise VTFError(
            "Bundled VTFLib binary not found at {}. The plugin install "
            "may be incomplete.".format(path)
        )

    lib = ctypes.CDLL(path)

    lib.vlInitialize.restype = ctypes.c_bool
    lib.vlShutdown.restype = None
    lib.vlGetLastError.restype = ctypes.c_char_p

    lib.vlCreateImage.restype = ctypes.c_bool
    lib.vlCreateImage.argtypes = [ctypes.POINTER(ctypes.c_uint)]
    lib.vlBindImage.restype = ctypes.c_bool
    lib.vlBindImage.argtypes = [ctypes.c_uint]
    lib.vlDeleteImage.restype = None
    lib.vlDeleteImage.argtypes = [ctypes.c_uint]

    lib.vlImageCreate.restype = ctypes.c_bool
    lib.vlImageCreate.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
        ctypes.c_uint, ctypes.c_int, ctypes.c_bool, ctypes.c_bool,
        ctypes.c_bool,
    ]
    lib.vlImageCreateDefaultCreateStructure.argtypes = [
        ctypes.POINTER(SVTFCreateOptions)
    ]
    lib.vlImageDestroy.restype = None

    lib.vlImageLoad.restype = ctypes.c_bool
    lib.vlImageLoad.argtypes = [ctypes.c_char_p, ctypes.c_bool]
    lib.vlImageSave.restype = ctypes.c_bool
    lib.vlImageSave.argtypes = [ctypes.c_char_p]

    lib.vlImageGetWidth.restype = ctypes.c_uint
    lib.vlImageGetHeight.restype = ctypes.c_uint
    lib.vlImageGetFrameCount.restype = ctypes.c_uint
    lib.vlImageGetFaceCount.restype = ctypes.c_uint
    lib.vlImageGetMipmapCount.restype = ctypes.c_uint
    lib.vlImageGetFormat.restype = ctypes.c_int

    lib.vlImageGetData.restype = ctypes.POINTER(ctypes.c_ubyte)
    lib.vlImageGetData.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint
    ]
    lib.vlImageSetData.restype = None
    lib.vlImageSetData.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
        ctypes.POINTER(ctypes.c_ubyte),
    ]

    lib.vlImageSetFlags.restype = None
    lib.vlImageSetFlags.argtypes = [ctypes.c_uint]
    lib.vlImageGetFlags.restype = ctypes.c_uint

    lib.vlImageComputeMipmapCount.restype = ctypes.c_uint
    lib.vlImageComputeMipmapCount.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_uint
    ]
    lib.vlImageComputeMipmapDimensions.restype = None
    lib.vlImageComputeMipmapDimensions.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
        ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
        ctypes.POINTER(ctypes.c_uint),
    ]
    lib.vlImageComputeImageSize.restype = ctypes.c_uint
    lib.vlImageComputeImageSize.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
        ctypes.c_int,
    ]

    lib.vlImageConvertToRGBA8888.restype = ctypes.c_bool
    lib.vlImageConvertToRGBA8888.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_uint, ctypes.c_uint, ctypes.c_int,
    ]
    lib.vlImageConvertFromRGBA8888.restype = ctypes.c_bool
    lib.vlImageConvertFromRGBA8888.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_ubyte),
        ctypes.c_uint, ctypes.c_uint, ctypes.c_int,
    ]

    lib.vlImageCorrectImageGamma.restype = None
    lib.vlImageCorrectImageGamma.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint, ctypes.c_uint,
        ctypes.c_float,
    ]
    lib.vlImageGenerateThumbnail.restype = ctypes.c_bool

    if not lib.vlInitialize():
        raise VTFError("vlInitialize() failed")

    _lib = lib
    return _lib


def _check(lib, ok, action):
    if not ok:
        err = lib.vlGetLastError()
        msg = err.decode("utf-8", "replace") if err else "(no error message)"
        raise VTFError("{} failed: {}".format(action, msg))


class _BoundImage(object):
    """Context manager: creates a fresh VTFLib image handle, binds it, and
    deletes it on exit. Only one handle needs to be bound at a time for our
    calls, but multiple handles can coexist -- vlBindImage() just switches
    which one subsequent calls act on."""

    def __init__(self, lib):
        self.lib = lib
        self.handle = ctypes.c_uint()

    def __enter__(self):
        _check(self.lib, self.lib.vlCreateImage(ctypes.byref(self.handle)),
               "vlCreateImage")
        self.bind()
        return self

    def bind(self):
        _check(self.lib, self.lib.vlBindImage(self.handle), "vlBindImage")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lib.vlDeleteImage(self.handle)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_vtf(path):
    """Read a .vtf file and return a dict:
        {
            "width": int, "height": int,
            "format": str (e.g. "DXT5"),
            "rgba": bytes  (top mip level, frame 0 / face 0 / slice 0,
                            always decoded to RGBA8888 regardless of the
                            file's internal storage format),
            "frame_count": int, "face_count": int, "mipmap_count": int,
        }
    """
    lib = _load_library()
    with _BoundImage(lib):
        _check(lib, lib.vlImageLoad(path.encode("utf-8"), False),
               "vlImageLoad({})".format(path))

        width = lib.vlImageGetWidth()
        height = lib.vlImageGetHeight()
        fmt = lib.vlImageGetFormat()
        frame_count = lib.vlImageGetFrameCount()
        face_count = lib.vlImageGetFaceCount()
        mipmap_count = lib.vlImageGetMipmapCount()

        data_ptr = lib.vlImageGetData(0, 0, 0, 0)
        if not data_ptr:
            raise VTFError("VTF file has no image data")

        if fmt == IMAGE_FORMAT["RGBA8888"]:
            size = width * height * 4
            rgba = bytes(bytearray(data_ptr[:size]))
        else:
            size = width * height * 4
            out_buf = (ctypes.c_ubyte * size)()
            _check(
                lib,
                lib.vlImageConvertToRGBA8888(data_ptr, out_buf, width,
                                              height, fmt),
                "vlImageConvertToRGBA8888",
            )
            rgba = bytes(bytearray(out_buf))

        return {
            "width": width,
            "height": height,
            "format": IMAGE_FORMAT_NAME.get(fmt, "UNKNOWN({})".format(fmt)),
            "rgba": rgba,
            "frame_count": frame_count,
            "face_count": face_count,
            "mipmap_count": mipmap_count,
        }


def write_vtf(path, width, height, rgba_bytes, options=None):
    """Write a single 2D image (RGBA8888 bytes, top-left origin, row-major)
    out as a .vtf file.

    options (all optional, sane defaults applied):
        format: str, one of EXPORTABLE_FORMATS (default "DXT5")
        version: str, one of VTF_VERSIONS (default "7.4")
        flags: list[str] of TEXTUREFLAGS keys
        generate_mipmaps: bool (default True)
        mipmap_filter: str, one of MIPMAP_FILTER keys (default "TRIANGLE")
        mipmap_sharpen: str, one of SHARPEN_FILTER keys (default "NONE")
        generate_thumbnail: bool (default True)
        resize: None, or dict {
            "method": one of RESIZE_METHOD keys,
            "width": int, "height": int,           # only used for "SET"
            "filter": one of MIPMAP_FILTER keys,
            "sharpen": one of SHARPEN_FILTER keys,
        }
        gamma_correct: bool, gamma: float (default 2.2)
        normal_map: None, or dict {
            "kernel": one of KERNEL_FILTER keys,
            "height_method": one of HEIGHT_CONVERSION_METHOD keys,
            "alpha_result": one of NORMAL_ALPHA_RESULT keys,
            "scale": float, "wrap": bool,
            "invert_x": bool, "invert_y": bool,
        }
        bumpmap_scale: float
    """
    o = dict(options or {})
    o.setdefault("format", "DXT5")
    o.setdefault("version", "7.4")
    o.setdefault("flags", [])
    o.setdefault("generate_mipmaps", True)
    o.setdefault("mipmap_filter", "TRIANGLE")
    o.setdefault("mipmap_sharpen", "NONE")
    o.setdefault("generate_thumbnail", True)
    o.setdefault("resize", None)
    o.setdefault("gamma_correct", False)
    o.setdefault("gamma", 2.2)
    o.setdefault("normal_map", None)
    o.setdefault("bumpmap_scale", 1.0)

    if o["format"] not in IMAGE_FORMAT:
        raise ValueError("Unknown format: {}".format(o["format"]))
    dest_format = IMAGE_FORMAT[o["format"]]

    lib = _load_library()

    src = (ctypes.c_ubyte * len(rgba_bytes)).from_buffer_copy(rgba_bytes)
    cur_w, cur_h = width, height

    # ---- optional resize -------------------------------------------------
    resize = o["resize"]
    if resize:
        method = resize.get("method", "NEAREST_POWER2")
        rfilter = MIPMAP_FILTER[resize.get("filter", "TRIANGLE")]
        rsharpen = SHARPEN_FILTER[resize.get("sharpen", "NONE")]

        def next_pow2(n):
            p = 1
            while p < n:
                p *= 2
            return p

        if method == "SET":
            new_w = resize["width"]
            new_h = resize["height"]
        else:
            pw, ph = next_pow2(cur_w), next_pow2(cur_h)
            if method == "NEAREST_POWER2":
                def nearest(n, p):
                    lower = p // 2 if p > 1 else 1
                    return p if (p - n) < (n - lower) else lower
                new_w, new_h = nearest(cur_w, pw), nearest(cur_h, ph)
            elif method == "BIGGEST_POWER2":
                new_w, new_h = pw, ph
            else:  # SMALLEST_POWER2
                new_w = pw // 2 if pw > cur_w and pw > 1 else pw
                new_h = ph // 2 if ph > cur_h and ph > 1 else ph
                new_w, new_h = max(new_w, 1), max(new_h, 1)

        if (new_w, new_h) != (cur_w, cur_h):
            resized_bytes = _resize_rgba(bytes(bytearray(src)), cur_w, cur_h,
                                          new_w, new_h)
            src = (ctypes.c_ubyte * len(resized_bytes)).from_buffer_copy(
                resized_bytes)
            cur_w, cur_h = new_w, new_h

    # ---- optional gamma correction ---------------------------------------
    if o["gamma_correct"]:
        lib.vlImageCorrectImageGamma(src, cur_w, cur_h,
                                      ctypes.c_float(o["gamma"]))

    # ---- optional normal map conversion -----------------------------------
    if o["normal_map"]:
        nm = o["normal_map"]
        out_bytes = _generate_normal_map(
            bytes(bytearray(src)), cur_w, cur_h,
            height_method=nm.get("height_method", "AVERAGE_RGB"),
            scale=nm.get("scale", 2.0),
            wrap=bool(nm.get("wrap", False)),
            invert_x=bool(nm.get("invert_x", False)),
            invert_y=bool(nm.get("invert_y", False)),
            alpha_result=nm.get("alpha_result", "NOCHANGE"),
        )
        src = (ctypes.c_ubyte * len(out_bytes)).from_buffer_copy(out_bytes)

    # VTFLib hard-rejects non-power-of-two textures at creation time --
    # this isn't a workaround for a bug, it's an actual constraint of the
    # VTF format (the same reason VTFCmd has a -resize flag at all). If the
    # user's chosen options didn't already land on power-of-two dimensions
    # (e.g. no resize was requested, or a plain paint-app canvas size was
    # passed straight through), silently correct to the nearest power of
    # two rather than letting the save fail outright.
    def _is_pow2(n):
        return n > 0 and (n & (n - 1)) == 0

    if not (_is_pow2(cur_w) and _is_pow2(cur_h)):
        def next_pow2(n):
            p = 1
            while p < n:
                p *= 2
            return p

        def nearest_pow2(n):
            p = next_pow2(n)
            lower = p // 2 if p > 1 else 1
            return p if (p - n) < (n - lower) else lower

        new_w, new_h = nearest_pow2(cur_w), nearest_pow2(cur_h)
        resized_bytes = _resize_rgba(bytes(bytearray(src)), cur_w, cur_h,
                                      new_w, new_h)
        src = (ctypes.c_ubyte * len(resized_bytes)).from_buffer_copy(
            resized_bytes)
        cur_w, cur_h = new_w, new_h

    # ---- build the mip chain ourselves (works around the fork's ---------
    # ---- nvDXTLib-only batch mip+compress limitation) --------------------
    mipmap_count = 1
    if o["generate_mipmaps"]:
        mipmap_count = lib.vlImageComputeMipmapCount(cur_w, cur_h, 1)

    mfilter = MIPMAP_FILTER[o["mipmap_filter"]]
    msharpen = SHARPEN_FILTER[o["mipmap_sharpen"]]

    level_buffers = []  # list of (w, h, ctypes buffer in dest_format)
    for level in range(mipmap_count):
        mw, mh = ctypes.c_uint(), ctypes.c_uint()
        md = ctypes.c_uint()
        lib.vlImageComputeMipmapDimensions(
            cur_w, cur_h, 1, level, ctypes.byref(mw), ctypes.byref(mh),
            ctypes.byref(md),
        )
        lvl_w, lvl_h = mw.value, mh.value

        if level == 0:
            level_rgba = src
        else:
            resized_bytes = _resize_rgba(bytes(bytearray(src)), cur_w, cur_h,
                                          lvl_w, lvl_h)
            level_rgba = (ctypes.c_ubyte * len(resized_bytes)).from_buffer_copy(
                resized_bytes)

        conv_w, conv_h, conv_rgba = lvl_w, lvl_h, level_rgba
        if o["format"] in COMPRESSED_FORMATS and (lvl_w < 4 or lvl_h < 4):
            # The bundled DXT compressor (tx_compress_dxtn) always reads a
            # full 4x4 pixel block regardless of the logical mip size, so
            # calling it directly on a smaller buffer over-reads past the
            # end of the buffer and reliably crashes the process. Every
            # mip chain ends up here eventually (mips go all the way down
            # to 1x1), so this isn't an edge case -- pad up to 4x4 first;
            # VTFLib's own image-size math already treats anything below
            # a full block as one block's worth of storage, so this
            # matches what the file format expects for that mip level.
            conv_w, conv_h = max(lvl_w, 4), max(lvl_h, 4)
            conv_rgba = _resize_rgba(bytes(bytearray(level_rgba)), lvl_w,
                                      lvl_h, conv_w, conv_h)
            conv_rgba = (ctypes.c_ubyte * len(conv_rgba)).from_buffer_copy(
                conv_rgba)

        dest_size = lib.vlImageComputeImageSize(conv_w, conv_h, 1, 1,
                                                  dest_format)
        dest_buf = (ctypes.c_ubyte * dest_size)()
        _check(
            lib,
            lib.vlImageConvertFromRGBA8888(conv_rgba, dest_buf, conv_w,
                                            conv_h, dest_format),
            "vlImageConvertFromRGBA8888 (mip level {})".format(level),
        )
        level_buffers.append((lvl_w, lvl_h, dest_buf))

    # ---- assemble the final VTF image object and save --------------------
    with _BoundImage(lib) as img:
        _check(
            lib,
            lib.vlImageCreate(cur_w, cur_h, 1, 1, 1, dest_format,
                               bool(o["generate_thumbnail"]),
                               bool(o["generate_mipmaps"]), True),
            "vlImageCreate",
        )

        for level, (lvl_w, lvl_h, buf) in enumerate(level_buffers):
            lib.vlImageSetData(0, 0, 0, level, buf)

        flag_bits = 0
        for name in o["flags"]:
            flag_bits |= TEXTUREFLAGS[name]
        if o["normal_map"]:
            flag_bits |= TEXTUREFLAGS["NORMAL"]
        lib.vlImageSetFlags(flag_bits)

        if o["bumpmap_scale"] != 1.0:
            lib.vlImageSetBumpmapScale = getattr(
                lib, "vlImageSetBumpmapScale", None)
            if lib.vlImageSetBumpmapScale:
                lib.vlImageSetBumpmapScale.argtypes = [ctypes.c_float]
                lib.vlImageSetBumpmapScale(ctypes.c_float(o["bumpmap_scale"]))

        if o["generate_thumbnail"]:
            try:
                _check(lib, lib.vlImageGenerateThumbnail(),
                       "vlImageGenerateThumbnail")
            except VTFError:
                # Thumbnail generation is cosmetic (a tiny preview image
                # embedded in the header) -- don't fail the whole export
                # over it.
                pass

        _check(lib, lib.vlImageSave(path.encode("utf-8")),
               "vlImageSave({})".format(path))


def write_vmt(path, base_texture_vtf_path, shader="LightmappedGeneric",
              extra_params=None):
    """Write a minimal .vmt material file pointing at the exported texture,
    the same way tools like VTFEdit Reloaded do: a basic starting point
    that's expected to be hand-tuned afterwards, not a full material
    authoring pipeline.
    """
    lines = ['"{}"'.format(shader), "{"]
    lines.append('\t"$basetexture" "{}"'.format(base_texture_vtf_path))
    for key, value in (extra_params or {}).items():
        lines.append('\t"{}" "{}"'.format(key, value))
    lines.append("}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
