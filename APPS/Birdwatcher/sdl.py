# -*- coding: utf-8 -*-
"""Minimal graphics layer over the system libSDL2, using only ctypes (no pygame).

Built for handheld firmwares that ship Python and SDL2 but not pygame.
"""
import os
import sys
import json
import struct
import ctypes
import ctypes.util
from array import array

# ---------------------------------------------------------------- library loading
_CANDIDATES = [
    os.environ.get('BIRDWATCHER_SDL_LIB', ''),
    'libSDL2-2.0.so.0', 'libSDL2-2.0.so', 'libSDL2.so',
    '/usr/lib/libSDL2-2.0.so.0', '/usr/lib32/libSDL2-2.0.so.0', '/usr/lib/arm-linux-gnueabihf/libSDL2-2.0.so.0',
    '/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0', '/lib/libSDL2-2.0.so.0', '/usr/local/lib/libSDL2-2.0.so.0',
    '/mnt/vendor/lib/libSDL2-2.0.so.0', '/mnt/vendor/lib/libSDL2.so',
]
found = ctypes.util.find_library('SDL2')
if found:
    _CANDIDATES.insert(1, found)

lib = None
LIB_PATH = None
_errors = []
for _c in _CANDIDATES:
    if not _c:
        continue
    try:
        lib = ctypes.CDLL(_c)
        LIB_PATH = _c
        break
    except OSError as _e:
        _errors.append('%s: %s' % (_c, _e))
if lib is None:
    raise ImportError('Cannot find libSDL2. Tried:\n  ' + '\n  '.join(_errors))


class Rect(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int), ('y', ctypes.c_int), ('w', ctypes.c_int), ('h', ctypes.c_int)]


class FPoint(ctypes.Structure):
    _fields_ = [('x', ctypes.c_float), ('y', ctypes.c_float)]


class Point(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int), ('y', ctypes.c_int)]


class Color(ctypes.Structure):
    _fields_ = [('r', ctypes.c_uint8), ('g', ctypes.c_uint8), ('b', ctypes.c_uint8), ('a', ctypes.c_uint8)]


class Vertex(ctypes.Structure):
    _fields_ = [('position', FPoint), ('color', Color), ('tex_coord', FPoint)]


class Version(ctypes.Structure):
    _fields_ = [('major', ctypes.c_uint8), ('minor', ctypes.c_uint8), ('patch', ctypes.c_uint8)]


VP = ctypes.c_void_p
_sig = {
    'SDL_Init': (ctypes.c_int, [ctypes.c_uint32]),
    'SDL_Quit': (None, []),
    'SDL_GetError': (ctypes.c_char_p, []),
    'SDL_GetVersion': (None, [ctypes.POINTER(Version)]),
    'SDL_SetHint': (ctypes.c_int, [ctypes.c_char_p, ctypes.c_char_p]),
    'SDL_CreateWindow': (VP, [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]),
    'SDL_DestroyWindow': (None, [VP]),
    'SDL_CreateRenderer': (VP, [VP, ctypes.c_int, ctypes.c_uint32]),
    'SDL_DestroyRenderer': (None, [VP]),
    'SDL_RenderSetLogicalSize': (ctypes.c_int, [VP, ctypes.c_int, ctypes.c_int]),
    'SDL_RenderTargetSupported': (ctypes.c_int, [VP]),
    'SDL_ShowCursor': (ctypes.c_int, [ctypes.c_int]),
    'SDL_SetRenderDrawColor': (ctypes.c_int, [VP, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]),
    'SDL_SetRenderDrawBlendMode': (ctypes.c_int, [VP, ctypes.c_int]),
    'SDL_RenderClear': (ctypes.c_int, [VP]),
    'SDL_RenderPresent': (None, [VP]),
    'SDL_RenderFillRect': (ctypes.c_int, [VP, ctypes.POINTER(Rect)]),
    'SDL_RenderFillRects': (ctypes.c_int, [VP, ctypes.POINTER(Rect), ctypes.c_int]),
    'SDL_RenderDrawRect': (ctypes.c_int, [VP, ctypes.POINTER(Rect)]),
    'SDL_RenderDrawLine': (ctypes.c_int, [VP, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
    'SDL_RenderDrawLines': (ctypes.c_int, [VP, ctypes.POINTER(Point), ctypes.c_int]),
    'SDL_RenderSetClipRect': (ctypes.c_int, [VP, ctypes.POINTER(Rect)]),
    'SDL_RenderCopy': (ctypes.c_int, [VP, VP, ctypes.POINTER(Rect), ctypes.POINTER(Rect)]),
    'SDL_SetRenderTarget': (ctypes.c_int, [VP, VP]),
    'SDL_RenderReadPixels': (ctypes.c_int, [VP, ctypes.POINTER(Rect), ctypes.c_uint32, VP, ctypes.c_int]),
    'SDL_CreateTexture': (VP, [VP, ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_int]),
    'SDL_CreateTextureFromSurface': (VP, [VP, VP]),
    'SDL_DestroyTexture': (None, [VP]),
    'SDL_SetTextureBlendMode': (ctypes.c_int, [VP, ctypes.c_int]),
    'SDL_SetTextureColorMod': (ctypes.c_int, [VP, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]),
    'SDL_RWFromFile': (VP, [ctypes.c_char_p, ctypes.c_char_p]),
    'SDL_LoadBMP_RW': (VP, [VP, ctypes.c_int]),
    'SDL_FreeSurface': (None, [VP]),
    'SDL_PollEvent': (ctypes.c_int, [VP]),
    'SDL_NumJoysticks': (ctypes.c_int, []),
    'SDL_JoystickOpen': (VP, [ctypes.c_int]),
    'SDL_JoystickName': (ctypes.c_char_p, [VP]),
    'SDL_JoystickNumButtons': (ctypes.c_int, [VP]),
    'SDL_JoystickNumAxes': (ctypes.c_int, [VP]),
    'SDL_JoystickNumHats': (ctypes.c_int, [VP]),
    'SDL_GetTicks': (ctypes.c_uint32, []),
    'SDL_Delay': (None, [ctypes.c_uint32]),
}
for _n, (_r, _a) in _sig.items():
    _f = getattr(lib, _n)
    _f.restype = _r
    _f.argtypes = _a

HAS_LINESF = hasattr(lib, 'SDL_RenderDrawLinesF')
if HAS_LINESF:
    lib.SDL_RenderDrawLinesF.restype = ctypes.c_int
    lib.SDL_RenderDrawLinesF.argtypes = [VP, ctypes.POINTER(FPoint), ctypes.c_int]
HAS_GEOMETRY = hasattr(lib, 'SDL_RenderGeometry')
if HAS_GEOMETRY:
    lib.SDL_RenderGeometry.restype = ctypes.c_int
    lib.SDL_RenderGeometry.argtypes = [VP, VP, ctypes.POINTER(Vertex), ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int]


def version():
    v = Version()
    lib.SDL_GetVersion(ctypes.byref(v))
    return '%d.%d.%d' % (v.major, v.minor, v.patch)


def error():
    e = lib.SDL_GetError()
    return e.decode('utf-8', 'replace') if e else ''


# constants
INIT_VIDEO, INIT_JOYSTICK, INIT_EVENTS = 0x20, 0x200, 0x4000
WIN_FULLSCREEN, WIN_FULLSCREEN_DESKTOP, WIN_SHOWN = 0x1, 0x1001, 0x4
REN_SOFTWARE, REN_ACCEL, REN_TARGET = 0x1, 0x2, 0x8
BLEND_NONE, BLEND_BLEND, BLEND_ADD = 0, 1, 2
FMT_ARGB8888, FMT_RGBA32 = 0x16362004, 0x16762004
TEX_TARGET = 2
EV_QUIT, EV_KEYDOWN, EV_KEYUP = 0x100, 0x300, 0x301
EV_JAXIS, EV_JHAT, EV_JBDOWN, EV_JBUP, EV_JADDED = 0x600, 0x602, 0x603, 0x604, 0x605
EV_TARGETS_RESET, EV_DEVICE_RESET = 0x2000, 0x2001
K_UP, K_DOWN, K_LEFT, K_RIGHT = 0x40000052, 0x40000051, 0x40000050, 0x4000004F
K_RETURN, K_ESCAPE, K_SPACE, K_BACKSPACE = 13, 27, 32, 8
K_LSHIFT, K_RSHIFT = 0x400000E1, 0x400000E5


class Texture:
    __slots__ = ('ptr', 'w', 'h')

    def __init__(self, ptr, w, h):
        self.ptr, self.w, self.h = ptr, w, h

    def destroy(self):
        if self.ptr:
            lib.SDL_DestroyTexture(self.ptr)
            self.ptr = None


class Gfx:
    """Window + renderer. All coordinates are logical 640x480 pixels."""

    def __init__(self, w=640, h=480, title='app', windowed=False):
        self.W, self.H = w, h
        lib.SDL_SetHint(b'SDL_RENDER_SCALE_QUALITY', b'0')
        if lib.SDL_Init(INIT_VIDEO | INIT_JOYSTICK | INIT_EVENTS) != 0:
            raise RuntimeError('SDL_Init: ' + error())
        self.win = None
        flags_list = [0] if windowed else [WIN_FULLSCREEN_DESKTOP, WIN_FULLSCREEN, 0]
        for fl in flags_list:
            self.win = lib.SDL_CreateWindow(title.encode(), 0x1FFF0000, 0x1FFF0000, w, h, fl | WIN_SHOWN)
            if self.win:
                break
        if not self.win:
            raise RuntimeError('SDL_CreateWindow: ' + error())
        self.ren = None
        for fl in (REN_ACCEL | REN_TARGET, REN_ACCEL, REN_SOFTWARE | REN_TARGET, REN_SOFTWARE):
            self.ren = lib.SDL_CreateRenderer(self.win, -1, fl)
            if self.ren:
                break
        if not self.ren:
            raise RuntimeError('SDL_CreateRenderer: ' + error())
        lib.SDL_RenderSetLogicalSize(self.ren, w, h)
        lib.SDL_ShowCursor(0)
        self.can_target = bool(lib.SDL_RenderTargetSupported(self.ren))
        self.cur_target = None
        self.tw, self.th = w, h
        self.joys = []
        self.open_joysticks()
        self._ev = (ctypes.c_uint8 * 64)()
        self._rect = Rect()
        self._blend = -1

    # ---------- state
    def open_joysticks(self):
        self.joys = []
        for i in range(lib.SDL_NumJoysticks()):
            j = lib.SDL_JoystickOpen(i)
            if j:
                self.joys.append(j)

    def joystick_info(self):
        out = []
        for j in self.joys:
            name = lib.SDL_JoystickName(j)
            out.append(((name or b'?').decode('utf-8', 'replace'), lib.SDL_JoystickNumButtons(j),
                        lib.SDL_JoystickNumAxes(j), lib.SDL_JoystickNumHats(j)))
        return out

    def color(self, c):
        a = c[3] if len(c) > 3 else 255
        bm = BLEND_BLEND if a < 255 else BLEND_NONE
        if bm != self._blend:
            lib.SDL_SetRenderDrawBlendMode(self.ren, bm)
            self._blend = bm
        lib.SDL_SetRenderDrawColor(self.ren, c[0], c[1], c[2], a)

    def new_target(self, w, h):
        if not self.can_target:
            return None
        t = lib.SDL_CreateTexture(self.ren, FMT_ARGB8888, TEX_TARGET, w, h)
        return Texture(t, w, h) if t else None

    def target(self, tex):
        lib.SDL_SetRenderTarget(self.ren, tex.ptr if tex else None)
        self.cur_target = tex
        self.tw, self.th = (tex.w, tex.h) if tex else (self.W, self.H)
        self._blend = -1

    def set_clip(self, r):
        if r is None:
            lib.SDL_RenderSetClipRect(self.ren, None)
        else:
            rr = Rect(int(r[0]), int(r[1]), int(r[2]), int(r[3]))
            lib.SDL_RenderSetClipRect(self.ren, ctypes.byref(rr))

    # ---------- primitives
    def clear(self, c):
        self.color(c)
        lib.SDL_RenderClear(self.ren)

    def fill(self, c, r=None):
        if r is None:
            r = (0, 0, self.tw, self.th)
        self.color(c)
        rr = self._rect
        rr.x, rr.y, rr.w, rr.h = int(r[0]), int(r[1]), int(r[2]), int(r[3])
        lib.SDL_RenderFillRect(self.ren, ctypes.byref(rr))

    def fill_rects(self, c, rects):
        if not rects:
            return
        self.color(c)
        arr = (Rect * len(rects))(*[Rect(int(a), int(b), int(w), int(h)) for a, b, w, h in rects])
        lib.SDL_RenderFillRects(self.ren, arr, len(rects))

    def rect(self, c, r):
        self.color(c)
        rr = self._rect
        rr.x, rr.y, rr.w, rr.h = int(r[0]), int(r[1]), int(r[2]), int(r[3])
        lib.SDL_RenderDrawRect(self.ren, ctypes.byref(rr))

    def line(self, c, a, b):
        self.color(c)
        lib.SDL_RenderDrawLine(self.ren, int(a[0]), int(a[1]), int(b[0]), int(b[1]))

    def lines_flat(self, c, flat):
        """flat = [x0, y0, x1, y1, ...]"""
        n = len(flat) // 2
        if n < 2:
            return
        self.color(c)
        if HAS_LINESF:
            buf = array('f', flat)
            ptr = ctypes.cast((ctypes.c_float * len(buf)).from_buffer(buf), ctypes.POINTER(FPoint))
            lib.SDL_RenderDrawLinesF(self.ren, ptr, n)
        else:
            buf = array('i', [int(v) for v in flat])
            ptr = ctypes.cast((ctypes.c_int * len(buf)).from_buffer(buf), ctypes.POINTER(Point))
            lib.SDL_RenderDrawLines(self.ren, ptr, n)

    def lines(self, c, pts, closed=False):
        flat = []
        for x, y in pts:
            flat.append(x)
            flat.append(y)
        if closed and pts:
            flat.append(pts[0][0])
            flat.append(pts[0][1])
        self.lines_flat(c, flat)

    def circle(self, c, cx, cy, r, step_px=4):
        import math
        n = max(24, min(720, int(2 * math.pi * r / step_px)))
        flat = []
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            flat.append(cx + r * math.cos(a))
            flat.append(cy + r * math.sin(a))
        self.lines_flat(c, flat)

    def disc(self, c, cx, cy, r):
        import math
        rows = []
        y0 = max(0, int(cy - r))
        y1 = min(self.th, int(cy + r) + 1)
        for y in range(y0, y1):
            dy = y + 0.5 - cy
            if abs(dy) > r:
                continue
            hw = math.sqrt(r * r - dy * dy)
            xa = max(0, int(cx - hw))
            xb = min(self.tw, int(cx + hw) + 1)
            if xb > xa:
                rows.append((xa, y, xb - xa, 1))
        self.fill_rects(c, rows)

    def triangles(self, c, pts):
        """pts: list of vertices, three per triangle."""
        if HAS_GEOMETRY:
            n = len(pts)
            col = Color(c[0], c[1], c[2], 255)
            verts = (Vertex * n)()
            for i, (x, y) in enumerate(pts):
                verts[i].position.x = x
                verts[i].position.y = y
                verts[i].color = col
            if self._blend != BLEND_NONE:
                lib.SDL_SetRenderDrawBlendMode(self.ren, BLEND_NONE)
                self._blend = BLEND_NONE
            lib.SDL_RenderGeometry(self.ren, None, verts, n, None, 0)
        else:
            for i in range(0, len(pts), 3):
                self.lines(c, pts[i:i + 3], True)

    def blit(self, tex, x, y, blend=BLEND_NONE, mod=None):
        if not tex or not tex.ptr:
            return
        lib.SDL_SetTextureBlendMode(tex.ptr, blend)
        if mod:
            lib.SDL_SetTextureColorMod(tex.ptr, mod[0], mod[1], mod[2])
        rr = self._rect
        rr.x, rr.y, rr.w, rr.h = int(x), int(y), tex.w, tex.h
        lib.SDL_RenderCopy(self.ren, tex.ptr, None, ctypes.byref(rr))

    def copy(self, tex, src, dst):
        lib.SDL_RenderCopy(self.ren, tex.ptr, ctypes.byref(Rect(*src)), ctypes.byref(Rect(*dst)))

    def load_bmp(self, path):
        rw = lib.SDL_RWFromFile(path.encode(), b'rb')
        if not rw:
            raise RuntimeError('Cannot open %s: %s' % (path, error()))
        surf = lib.SDL_LoadBMP_RW(rw, 1)
        if not surf:
            raise RuntimeError('BMP %s: %s' % (path, error()))
        off = 16 if ctypes.sizeof(ctypes.c_void_p) == 8 else 8
        w, h = struct.unpack_from('ii', ctypes.string_at(surf, off + 8), off)
        t = lib.SDL_CreateTextureFromSurface(self.ren, surf)
        lib.SDL_FreeSurface(surf)
        return Texture(t, w, h)

    def present(self):
        lib.SDL_RenderPresent(self.ren)

    def read_pixels(self):
        buf = (ctypes.c_uint8 * (self.W * self.H * 4))()
        lib.SDL_RenderReadPixels(self.ren, None, FMT_RGBA32, buf, self.W * 4)
        return bytes(buf)

    # ---------- normalised events
    def events(self):
        out = []
        ev = self._ev
        while lib.SDL_PollEvent(ctypes.byref(ev)):
            raw = bytes(ev)
            t = struct.unpack_from('I', raw, 0)[0]
            if t == EV_QUIT:
                out.append(('quit',))
            elif t in (EV_KEYDOWN, EV_KEYUP):
                rep = raw[13]
                sym = struct.unpack_from('i', raw, 20)[0]
                out.append(('key', t == EV_KEYDOWN, sym, rep))
            elif t in (EV_JBDOWN, EV_JBUP):
                out.append(('jbtn', t == EV_JBDOWN, raw[12]))
            elif t == EV_JHAT:
                out.append(('hat', raw[13]))
            elif t == EV_JAXIS:
                out.append(('axis', raw[12], struct.unpack_from('h', raw, 16)[0]))
            elif t == EV_JADDED:
                self.open_joysticks()
            elif t in (EV_TARGETS_RESET, EV_DEVICE_RESET):
                out.append(('reset',))
        return out

    def quit(self):
        try:
            lib.SDL_DestroyRenderer(self.ren)
            lib.SDL_DestroyWindow(self.win)
        finally:
            lib.SDL_Quit()


class Font:
    """Monospace font from a BMP atlas (white on black) plus JSON metrics.

    Each distinct string is composed once into a cached texture and drawn with additive
    blending and colour modulation, so the atlas's black background never shows.
    """

    def __init__(self, gfx, base_path):
        self.g = gfx
        with open(base_path + '.json') as fh:
            m = json.load(fh)
        self.adv, self.cell_h, self.ascent, self.cols = m['adv'], m['h'], m['ascent'], m['cols']
        self.index = {ch: i for i, ch in enumerate(m['chars'])}
        self.atlas = gfx.load_bmp(base_path + '.bmp')
        self.cache = {}

    def width(self, s):
        return len(s) * self.adv

    def _make(self, s):
        g = self.g
        w = max(1, len(s) * self.adv)
        tex = g.new_target(w, self.cell_h)
        if tex is None:
            return None
        prev = g.cur_target
        g.target(tex)
        lib.SDL_SetRenderDrawBlendMode(g.ren, BLEND_NONE)
        lib.SDL_SetRenderDrawColor(g.ren, 0, 0, 0, 255)
        lib.SDL_RenderClear(g.ren)
        lib.SDL_SetTextureBlendMode(self.atlas.ptr, BLEND_NONE)
        lib.SDL_SetTextureColorMod(self.atlas.ptr, 255, 255, 255)
        q = self.index.get('?', 0)
        src, dst = Rect(0, 0, self.adv, self.cell_h), Rect(0, 0, self.adv, self.cell_h)
        for i, ch in enumerate(s):
            k = self.index.get(ch, q)
            src.x, src.y = (k % self.cols) * self.adv, (k // self.cols) * self.cell_h
            dst.x = i * self.adv
            lib.SDL_RenderCopy(g.ren, self.atlas.ptr, ctypes.byref(src), ctypes.byref(dst))
        g.target(prev)
        return tex

    def draw(self, s, x, y_base, col, align='left'):
        """Draws s with its baseline at y_base. Returns the width."""
        if not s:
            return 0
        w = len(s) * self.adv
        if align == 'right':
            x -= w
        elif align == 'center':
            x -= w // 2
        top = y_base - self.ascent
        tex = self.cache.get(s)
        if tex is None:
            if len(self.cache) > 600:
                self.flush()
            tex = self._make(s)
            if tex is None:  # no render targets: glyph by glyph
                self._draw_direct(s, x, top, col)
                return w
            self.cache[s] = tex
        self.g.blit(tex, x, top, BLEND_ADD, col)
        return w

    def _draw_direct(self, s, x, top, col):
        g = self.g
        lib.SDL_SetTextureBlendMode(self.atlas.ptr, BLEND_ADD)
        lib.SDL_SetTextureColorMod(self.atlas.ptr, col[0], col[1], col[2])
        q = self.index.get('?', 0)
        src, dst = Rect(0, 0, self.adv, self.cell_h), Rect(0, int(top), self.adv, self.cell_h)
        for i, ch in enumerate(s):
            k = self.index.get(ch, q)
            src.x, src.y = (k % self.cols) * self.adv, (k // self.cols) * self.cell_h
            dst.x = int(x) + i * self.adv
            lib.SDL_RenderCopy(g.ren, self.atlas.ptr, ctypes.byref(src), ctypes.byref(dst))

    def flush(self):
        for t in self.cache.values():
            t.destroy()
        self.cache.clear()
