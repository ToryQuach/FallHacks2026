from __future__ import unicode_literals

import os
import sys
import ctypes as ct

from mascot import Mascot

# --------------------------------------------------------------- Win32 types
BYTE = ct.c_ubyte
WORD = ct.c_ushort
DWORD = ct.c_ulong
BOOL = ct.c_long
UINT = ct.c_uint
LONG = ct.c_long
ATOM = WORD

HANDLE = ct.c_void_p
HWND = HANDLE
HINSTANCE = HANDLE
HMODULE = HANDLE
HICON = HANDLE
HCURSOR = HANDLE
HBRUSH = HANDLE
HDC = HANDLE
HMENU = HANDLE
HGDIOBJ = HANDLE

LPVOID = ct.c_void_p
LPCWSTR = ct.c_wchar_p

# WPARAM is unsigned and pointer-sized; LPARAM/LRESULT are signed.
if ct.sizeof(ct.c_long) == ct.sizeof(ct.c_void_p):
    WPARAM, LPARAM, LRESULT = ct.c_ulong, ct.c_long, ct.c_long
else:
    WPARAM, LPARAM, LRESULT = ct.c_ulonglong, ct.c_longlong, ct.c_longlong

WNDPROC = ct.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

# -------------------------------------------------------------------- structs
class POINT(ct.Structure):
    _fields_ = (('x', LONG),
                ('y', LONG))

class RECT(ct.Structure):
    _fields_ = (('left', LONG),
                ('top', LONG),
                ('right', LONG),
                ('bottom', LONG))

class RectF(ct.Structure):
    _fields_ = (('x', ct.c_float),
                ('y', ct.c_float),
                ('width', ct.c_float),
                ('height', ct.c_float))

class SIZE(ct.Structure):
    _fields_ = (('cx', LONG),
                ('cy', LONG))

class BITMAPINFOHEADER(ct.Structure):
    _fields_ = (('biSize', DWORD),
                ('biWidth', LONG),
                ('biHeight', LONG),
                ('biPlanes', WORD),
                ('biBitCount', WORD),
                ('biCompression', DWORD),
                ('biSizeImage', DWORD),
                ('biXPelsPerMeter', LONG),
                ('biYPelsPerMeter', LONG),
                ('biClrUsed', DWORD),
                ('biClrImportant', DWORD))

class RGBQUAD(ct.Structure):
    _fields_ = (('rgbBlue', BYTE),
                ('rgbGreen', BYTE),
                ('rgbRed', BYTE),
                ('rgbReserved', BYTE))

class BITMAPINFO(ct.Structure):
    _fields_ = (('bmiHeader', BITMAPINFOHEADER),
                ('bmiColors', RGBQUAD * 1))

class BLENDFUNCTION(ct.Structure):
    _fields_ = (('BlendOp', BYTE),
                ('BlendFlags', BYTE),
                ('SourceConstantAlpha', BYTE),
                ('AlphaFormat', BYTE))

class MSG(ct.Structure):
    _fields_ = (('hwnd', HWND),
                ('message', UINT),
                ('wParam', WPARAM),
                ('lParam', LPARAM),
                ('time', DWORD),
                ('pt', POINT))

class WNDCLASS(ct.Structure):
    _fields_ = (('style', UINT),
                ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ct.c_int),
                ('cbWndExtra', ct.c_int),
                ('hInstance', HINSTANCE),
                ('hIcon', HICON),
                ('hCursor', HCURSOR),
                ('hbrBackground', HBRUSH),
                ('lpszMenuName', LPCWSTR),
                ('lpszClassName', LPCWSTR))

class PAINTSTRUCT(ct.Structure):
    _fields_ = (('hdc', HDC),
                ('fErase', BOOL),
                ('rcPaint', RECT),
                ('fRestore', BOOL),
                ('fIncUpdate', BOOL),
                ('rgbReserved', BYTE * 32))

class GdiplusStartupInput(ct.Structure):
    _fields_ = (('GdiplusVersion', UINT),
                ('DebugEventCallback', LPVOID),
                ('SuppressBackgroundThread', BOOL),
                ('SuppressExternalCodecs', BOOL))

# ------------------------------------------------------------ error handlers
def errcheck(result, func, args):
    if result is None or result == 0:
        raise ct.WinError(ct.get_last_error())
    return result

def minusonecheck(result, func, args):
    if result == -1:
        raise ct.WinError(ct.get_last_error())
    return result

def gdipcheck(status, func, args):
    # GDI+ returns its own Status codes, not Win32 error codes.
    if status != 0:
        raise RuntimeError('%s failed with GDI+ status %d' % (func.__name__, status))
    return status

def MAKEINTRESOURCE(x):
    return LPCWSTR(x)

def GET_X_LPARAM(lParam):
    return ct.c_short(lParam & 0xFFFF).value

def GET_Y_LPARAM(lParam):
    return ct.c_short((lParam >> 16) & 0xFFFF).value

# ------------------------------------------------------------------ kernel32
kernel32 = ct.WinDLL('kernel32', use_last_error=True)
GetModuleHandle = kernel32.GetModuleHandleW
GetModuleHandle.argtypes = LPCWSTR,
GetModuleHandle.restype = HMODULE
GetModuleHandle.errcheck = errcheck

# -------------------------------------------------------------------- user32
user32 = ct.WinDLL('user32', use_last_error=True)

def bind(lib, name, argtypes, restype, check=None):
    fn = getattr(lib, name)
    fn.argtypes = argtypes
    fn.restype = restype
    if check is not None:
        fn.errcheck = check
    return fn

CreateWindowEx = bind(user32, 'CreateWindowExW',
                      (DWORD, LPCWSTR, LPCWSTR, DWORD, ct.c_int, ct.c_int,
                       ct.c_int, ct.c_int, HWND, HMENU, HINSTANCE, LPVOID),
                      HWND, errcheck)
LoadIcon = bind(user32, 'LoadIconW', (HINSTANCE, LPCWSTR), HICON, errcheck)
LoadCursor = bind(user32, 'LoadCursorW', (HINSTANCE, LPCWSTR), HCURSOR, errcheck)
RegisterClass = bind(user32, 'RegisterClassW', (ct.POINTER(WNDCLASS),), ATOM, errcheck)
ShowWindow = bind(user32, 'ShowWindow', (HWND, ct.c_int), BOOL)
SetForegroundWindow = bind(user32, 'SetForegroundWindow', (HWND,), BOOL)
SetCapture = bind(user32, 'SetCapture', (HWND,), HWND)
ReleaseCapture = bind(user32, 'ReleaseCapture', (), BOOL)
SetCursor = bind(user32, 'SetCursor', (HCURSOR,), HCURSOR)
SetProcessDPIAware = bind(user32, 'SetProcessDPIAware', (), BOOL)
GetSystemMetrics = bind(user32, 'GetSystemMetrics', (ct.c_int,), ct.c_int)
GetMessage = bind(user32, 'GetMessageW', (ct.POINTER(MSG), HWND, UINT, UINT), BOOL, minusonecheck)
TranslateMessage = bind(user32, 'TranslateMessage', (ct.POINTER(MSG),), BOOL)
DispatchMessage = bind(user32, 'DispatchMessageW', (ct.POINTER(MSG),), LRESULT)
DefWindowProc = bind(user32, 'DefWindowProcW', (HWND, UINT, WPARAM, LPARAM), LRESULT)
PostQuitMessage = bind(user32, 'PostQuitMessage', (ct.c_int,), None)
BeginPaint = bind(user32, 'BeginPaint', (HWND, ct.POINTER(PAINTSTRUCT)), HDC)
EndPaint = bind(user32, 'EndPaint', (HWND, ct.POINTER(PAINTSTRUCT)), BOOL)
UpdateLayeredWindow = bind(user32, 'UpdateLayeredWindow',
                           (HWND, HDC, ct.POINTER(POINT), ct.POINTER(SIZE), HDC,
                            ct.POINTER(POINT), DWORD, ct.POINTER(BLENDFUNCTION), DWORD),
                           BOOL, errcheck)
SetTimer = bind(user32, 'SetTimer', (HWND, ct.c_size_t, UINT, LPVOID), ct.c_size_t, errcheck)
KillTimer = bind(user32, 'KillTimer', (HWND, ct.c_size_t), BOOL)

# --------------------------------------------------------------------- gdi32
gdi32 = ct.WinDLL('gdi32', use_last_error=True)

CreateDIBSection = bind(gdi32, 'CreateDIBSection',
                        (HDC, ct.POINTER(BITMAPINFO), UINT, ct.POINTER(ct.c_void_p), HANDLE, DWORD),
                        HANDLE, errcheck)
CreateCompatibleDC = bind(gdi32, 'CreateCompatibleDC', (HDC,), HDC, errcheck)
SelectObject = bind(gdi32, 'SelectObject', (HDC, HGDIOBJ), HGDIOBJ)
DeleteDC = bind(gdi32, 'DeleteDC', (HDC,), BOOL)
DeleteObject = bind(gdi32, 'DeleteObject', (HGDIOBJ,), BOOL)
GdiFlush = bind(gdi32, 'GdiFlush', (), BOOL)

# -------------------------------------------------------------------- gdiplus
gdiplus = ct.WinDLL('gdiplus', use_last_error=True)

GdiplusStartup = bind(gdiplus, 'GdiplusStartup',
                      (ct.POINTER(ct.c_void_p), ct.POINTER(GdiplusStartupInput), LPVOID),
                      ct.c_int, gdipcheck)
GdiplusShutdown = bind(gdiplus, 'GdiplusShutdown', (ct.c_void_p,), None)
GdipCreateBitmapFromFile = bind(gdiplus, 'GdipCreateBitmapFromFile',
                                (LPCWSTR, ct.POINTER(ct.c_void_p)), ct.c_int, gdipcheck)
GdipCreateFromHDC = bind(gdiplus, 'GdipCreateFromHDC',
                         (HDC, ct.POINTER(ct.c_void_p)), ct.c_int, gdipcheck)
GdipGetImageWidth = bind(gdiplus, 'GdipGetImageWidth',
                         (ct.c_void_p, ct.POINTER(UINT)), ct.c_int, gdipcheck)
GdipGetImageHeight = bind(gdiplus, 'GdipGetImageHeight',
                          (ct.c_void_p, ct.POINTER(UINT)), ct.c_int, gdipcheck)
GdipSetInterpolationMode = bind(gdiplus, 'GdipSetInterpolationMode',
                                (ct.c_void_p, ct.c_int), ct.c_int)
GdipDrawImageRectI = bind(gdiplus, 'GdipDrawImageRectI',
                          (ct.c_void_p, ct.c_void_p, ct.c_int, ct.c_int, ct.c_int, ct.c_int),
                          ct.c_int, gdipcheck)
GdipDeleteGraphics = bind(gdiplus, 'GdipDeleteGraphics', (ct.c_void_p,), ct.c_int)
GdipDisposeImage = bind(gdiplus, 'GdipDisposeImage', (ct.c_void_p,), ct.c_int)

GdipSetTextRenderingHint = bind(gdiplus, 'GdipSetTextRenderingHint',
                                (ct.c_void_p, ct.c_int), ct.c_int)
GdipSetClipRectI = bind(gdiplus, 'GdipSetClipRectI',
                        (ct.c_void_p, ct.c_int, ct.c_int, ct.c_int, ct.c_int, ct.c_int), ct.c_int)
GdipFillRectangleI = bind(gdiplus, 'GdipFillRectangleI',
                          (ct.c_void_p, ct.c_void_p, ct.c_int, ct.c_int, ct.c_int, ct.c_int),
                          ct.c_int)
GdipCreateFontFamilyFromName = bind(gdiplus, 'GdipCreateFontFamilyFromName',
                                    (LPCWSTR, ct.c_void_p, ct.POINTER(ct.c_void_p)),
                                    ct.c_int, gdipcheck)
GdipDeleteFontFamily = bind(gdiplus, 'GdipDeleteFontFamily', (ct.c_void_p,), ct.c_int)
GdipCreateFont = bind(gdiplus, 'GdipCreateFont',
                      (ct.c_void_p, ct.c_float, ct.c_int, ct.c_int, ct.POINTER(ct.c_void_p)),
                      ct.c_int, gdipcheck)
GdipDeleteFont = bind(gdiplus, 'GdipDeleteFont', (ct.c_void_p,), ct.c_int)
GdipCreateSolidFill = bind(gdiplus, 'GdipCreateSolidFill',
                           (ct.c_uint, ct.POINTER(ct.c_void_p)), ct.c_int, gdipcheck)
GdipDeleteBrush = bind(gdiplus, 'GdipDeleteBrush', (ct.c_void_p,), ct.c_int)
GdipCreateStringFormat = bind(gdiplus, 'GdipCreateStringFormat',
                              (ct.c_int, ct.c_ushort, ct.POINTER(ct.c_void_p)),
                              ct.c_int, gdipcheck)
GdipSetStringFormatFlags = bind(gdiplus, 'GdipSetStringFormatFlags',
                                (ct.c_void_p, ct.c_int), ct.c_int)
GdipSetStringFormatLineAlign = bind(gdiplus, 'GdipSetStringFormatLineAlign',
                                    (ct.c_void_p, ct.c_int), ct.c_int)
GdipDeleteStringFormat = bind(gdiplus, 'GdipDeleteStringFormat', (ct.c_void_p,), ct.c_int)
GdipMeasureString = bind(gdiplus, 'GdipMeasureString',
                         (ct.c_void_p, LPCWSTR, ct.c_int, ct.c_void_p, ct.POINTER(RectF),
                          ct.c_void_p, ct.POINTER(RectF), ct.POINTER(ct.c_int),
                          ct.POINTER(ct.c_int)),
                         ct.c_int, gdipcheck)
GdipDrawString = bind(gdiplus, 'GdipDrawString',
                      (ct.c_void_p, LPCWSTR, ct.c_int, ct.c_void_p, ct.POINTER(RectF),
                       ct.c_void_p, ct.c_void_p),
                      ct.c_int, gdipcheck)

# ------------------------------------------------------------------ constants
IDI_APPLICATION = MAKEINTRESOURCE(32512)
IDC_ARROW = MAKEINTRESOURCE(32512)
IDC_SIZEALL = MAKEINTRESOURCE(32646)

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

BI_RGB = 0
DIB_RGB_COLORS = 0

SM_CXSCREEN = 0
SM_CYSCREEN = 1

SM_CXDRAG = 68
SM_CYDRAG = 69

CS_HREDRAW = 2
CS_VREDRAW = 1

SW_SHOWNORMAL = 1

WM_DESTROY = 2
WM_PAINT = 15
WM_KEYDOWN = 0x0100
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_CAPTURECHANGED = 0x0215
VK_ESCAPE = 0x1B

ERROR_CLASS_ALREADY_EXISTS = 1410

# ------------------------------- tweaks ----------------------------------
# Sprites are 1336x948 PNGs; the default draws them at this fraction of
# natural size. Pass MascotDisplay(scale=...) to override:
# 0.25 = small, 0.5 = half size, 1.0 = full size.
MASCOT_SCALE = 0.35

WM_CHAR = 0x0102
WM_TIMER = 0x0113
CARET_TIMER_ID = 1
CARET_BLINK_MS = 530

TEXT_RENDERING_ANTIALIAS = 4
UNIT_PIXEL = 2
COMBINE_REPLACE = 0
# NoFitBlackBox | MeasureTrailingSpaces | NoWrap | LineLimit | NoClip
STRING_FORMAT_FLAGS = 0x0004 | 0x0800 | 0x1000 | 0x2000 | 0x4000

# Input box per sprite: (left, top, right, bottom) in the PNG's natural pixels,
# keyed by file name. These numbers are estimated from a preview, so check
# them in an image editor and adjust.
INPUT_RECTS = {
    'scroll_input_long.png': (700, 20, 2000, 715),
}
INPUT_PADDING = 40          # natural px of space inside the box edges
INPUT_FONT_PX = 120         # natural px; scaled by MASCOT_SCALE like the sprite
INPUT_TEXT_ARGB = 0xFF131313

# -------------------------------------------------------------------------
INTERPOLATION_HIGH_QUALITY_BICUBIC = 7

# Window handle -> MascotDisplay, so the shared WNDPROC can find its instance.
_instances = {}

def _windowProc(hwnd, message, wParam, lParam):
    display = _instances.get(hwnd)
    if display is not None:
        return display.handleMessage(hwnd, message, wParam, lParam)
    return DefWindowProc(hwnd, message, wParam, lParam)

# Kept alive for the process lifetime; WNDCLASS stores only a pointer to it.
_windowProcCallback = WNDPROC(_windowProc)

class MascotDisplay(object):
    """Fullscreen, always-on-top, per-pixel-alpha window showing a mascot.

    Create one and call run() to start it; Esc closes the window.
    """

    def __init__(self, scale=MASCOT_SCALE, title='Python Window', className='MainWin', onSubmit=None):
        self.scale = scale
        self.title = title
        self.className = className

        self.mascot = Mascot()
        self.currentSprite = None   # sprite path currently on screen
        self.spriteCache = {}       # PNG path -> GDI+ bitmap handle
        self.sizeAllCursor = None

        # Where the sprite sits in window coordinates.
        self.mascotX = 0
        self.mascotY = 0

        # States
        self.previousState = self.mascot.getState()
        self.isScrolling = False

        # Drag state, in window coordinates.
        self.dragging = False
        self.dragMoved = False
        self.dragStartX = 0
        self.dragStartY = 0
        self.dragMascotX = 0
        self.dragMascotY = 0

        # Text input
        self.onSubmit = onSubmit        # callback(text) fired on Enter
        self.inputText = ''
        self.caretOn = True
        self.fontPx = INPUT_FONT_PX * scale
        self._pendingHigh = None        # first half of a surrogate pair
        self._fontFamily = None
        self._font = None
        self._textBrush = None
        self._textFormat = None

        # Per-pixel-alpha surface the layered window is composed from.
        self.hwnd = None
        self.surfaceBitmap = None
        self.surfaceDC = None
        self.surfaceBits = None
        self.surfaceWidth = 0
        self.surfaceHeight = 0

        self._gdiplusToken = None

    # ------------------------------------------------------------- lifecycle
    def run(self):
        """Create the window, pump messages until it closes, return exit code."""
        # System DPI awareness keeps the sprite pixel-accurate on scaled displays.
        SetProcessDPIAware()
        self._startGdiplus()
        try:
            self._createTextResources()
            self.sizeAllCursor = LoadCursor(None, IDC_SIZEALL)
            wndclass = self._registerClass()
            self._createSurface()
            self._createWindow(wndclass)
            SetTimer(self.hwnd, CARET_TIMER_ID, CARET_BLINK_MS, None)
            
            self.sizeAllCursor = LoadCursor(None, IDC_SIZEALL)
            wndclass = self._registerClass()
            self._createSurface()
            self._createWindow(wndclass)

            # Start with the sprite centered on screen.
            self.currentSprite = self.mascot.getNextImage()
            drawW, drawH = self._spriteSize(self.currentSprite)
            self.mascotX = (self.surfaceWidth - drawW) // 2
            self.mascotY = (self.surfaceHeight - drawH) // 2
            self._present()

            ShowWindow(self.hwnd, SW_SHOWNORMAL)
            # Borderless windows don't always take focus on their own; needed
            # for Esc.
            SetForegroundWindow(self.hwnd)

            return self._messageLoop()
        finally:
            self._shutdown()

    def _startGdiplus(self):
        token = ct.c_void_p()
        startup = GdiplusStartupInput()
        startup.GdiplusVersion = 1
        GdiplusStartup(ct.byref(token), ct.byref(startup), None)
        self._gdiplusToken = token

    def _shutdown(self):
        if self.hwnd is not None:
            KillTimer(self.hwnd, CARET_TIMER_ID)
            _instances.pop(self.hwnd, None)
            self.hwnd = None

        for bitmap in self.spriteCache.values():
            GdipDisposeImage(bitmap)
        self.spriteCache.clear()

        if self._gdiplusToken is not None:
            GdiplusShutdown(self._gdiplusToken)
            self._gdiplusToken = None

        if self.surfaceDC is not None:
            DeleteDC(self.surfaceDC)
            self.surfaceDC = None
        if self.surfaceBitmap is not None:
            DeleteObject(self.surfaceBitmap)
            self.surfaceBitmap = None
        self.surfaceBits = None

    def _messageLoop(self):
        msg = MSG()
        while GetMessage(ct.byref(msg), None, 0, 0) != 0:
            TranslateMessage(ct.byref(msg))
            DispatchMessage(ct.byref(msg))
        return msg.wParam

    # ---------------------------------------------------------------- window
    def _registerClass(self):
        # The client area is never GDI-painted: the window is composed from the
        # per-pixel-alpha surface, so no background brush.
        wndclass = WNDCLASS()
        wndclass.style         = CS_HREDRAW | CS_VREDRAW
        wndclass.lpfnWndProc   = _windowProcCallback
        wndclass.cbClsExtra    = 0
        wndclass.cbWndExtra    = 0
        wndclass.hInstance     = GetModuleHandle(None)
        wndclass.hIcon         = LoadIcon(None, IDI_APPLICATION)
        wndclass.hCursor       = LoadCursor(None, IDC_ARROW)
        wndclass.hbrBackground = None
        wndclass.lpszMenuName  = None
        wndclass.lpszClassName = self.className
        try:
            RegisterClass(ct.byref(wndclass))
        except OSError as exc:
            # A second display in the same process reuses the window class.
            if exc.winerror != ERROR_CLASS_ALREADY_EXISTS:
                raise
        return wndclass

    def _createWindow(self, wndclass):
        # Borderless, screen-sized, layered and always on top.
        self.hwnd = CreateWindowEx(WS_EX_LAYERED | WS_EX_TOPMOST,
                                   wndclass.lpszClassName,
                                   self.title,
                                   WS_POPUP,
                                   0, 0, self.surfaceWidth, self.surfaceHeight,
                                   None, None, wndclass.hInstance, None)
        _instances[self.hwnd] = self

    def _createSurface(self):
        """32-bit top-down DIB; zeroed pixels are fully transparent."""
        self.surfaceWidth = GetSystemMetrics(SM_CXSCREEN)
        self.surfaceHeight = GetSystemMetrics(SM_CYSCREEN)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ct.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.surfaceWidth
        bmi.bmiHeader.biHeight = -self.surfaceHeight  # negative = top-down rows
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        bits = ct.c_void_p()
        self.surfaceBitmap = CreateDIBSection(None, ct.byref(bmi), DIB_RGB_COLORS,
                                              ct.byref(bits), None, 0)
        self.surfaceDC = CreateCompatibleDC(None)
        SelectObject(self.surfaceDC, self.surfaceBitmap)
        self.surfaceBits = bits

    # ---------------------------------------------------------------- sprites
    def _loadSprite(self, path):
        """Load a sprite PNG into a cached GDI+ bitmap (keeps its alpha)."""
        bitmap = self.spriteCache.get(path)
        if bitmap is None:
            bitmap = ct.c_void_p()
            GdipCreateBitmapFromFile(path, ct.byref(bitmap))
            self.spriteCache[path] = bitmap
        return bitmap

    def _bitmapSize(self, bitmap):
        """On-screen size of a sprite bitmap after self.scale."""
        width = UINT()
        height = UINT()
        GdipGetImageWidth(bitmap, ct.byref(width))
        GdipGetImageHeight(bitmap, ct.byref(height))
        return int(width.value * self.scale), int(height.value * self.scale)

    def _spriteSize(self, path):
        return self._bitmapSize(self._loadSprite(path))

    def _drawSprite(self, hdc, path, x, y):
        """Draw one sprite at (x, y), scaled by self.scale."""
        bitmap = self._loadSprite(path)
        drawW, drawH = self._bitmapSize(bitmap)

        graphics = ct.c_void_p()
        GdipCreateFromHDC(hdc, ct.byref(graphics))
        GdipSetInterpolationMode(graphics, INTERPOLATION_HIGH_QUALITY_BICUBIC)
        GdipDrawImageRectI(graphics, bitmap, x, y, drawW, drawH)
        GdipDeleteGraphics(graphics)

    def _setSprite(self, path):
        """Swap the current sprite, keeping its center fixed on screen."""
        if not path:
            return
        path = str(path)
        if self.currentSprite is None:
            self.currentSprite = path
            return

        oldW, oldH = self._spriteSize(self.currentSprite)
        cx = self.mascotX + oldW // 2
        cy = self.mascotY + oldH // 2

        self.currentSprite = path
        newW, newH = self._spriteSize(path)

        # _moveMascot measures the sprite in self.currentSprite, so set that
        # first. It also clamps the result to stay fully on screen.
        self._moveMascot(cx - newW // 2, cy - newH // 2)

    # ------------------------------------------------------------ composition
    def _moveMascot(self, x, y):
        """Move the sprite, keeping it on screen. Returns True if it moved."""
        drawW, drawH = self._spriteSize(self.currentSprite)
        x = min(max(x, 0), max(0, self.surfaceWidth - drawW))
        y = min(max(y, 0), max(0, self.surfaceHeight - drawH))
        if (x, y) == (self.mascotX, self.mascotY):
            return False
        self.mascotX, self.mascotY = x, y
        return True

    def _present(self):
        """Render the current frame into the alpha surface and compose it."""
        # Clear to transparent; the sprite supplies every visible pixel, so its
        # soft edges blend against nothing and no background color can bleed in.
        ct.memset(self.surfaceBits, 0, self.surfaceWidth * self.surfaceHeight * 4)
        self._drawSprite(self.surfaceDC, self.currentSprite, self.mascotX, self.mascotY)
        GdiFlush()  # make sure every batched GDI call landed in the DIB

        size = SIZE(self.surfaceWidth, self.surfaceHeight)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        UpdateLayeredWindow(self.hwnd, None, None, ct.byref(size), self.surfaceDC,
                            ct.byref(src), 0, ct.byref(blend), ULW_ALPHA)

    def _onClick(self):
        """Called on a click that wasn't a drag."""
        self.isScrolling = not self.isScrolling

        if self.isScrolling:
            self.previousState = self.mascot.getState()
            self.mascot.setState(Mascot.SCROLL)
        else:
            self.mascot.setState(self.previousState)

        self._setSprite(self.mascot.getNextImage())
        self._present()

    # --------------------------------------------------------------- messages
    def handleMessage(self, hwnd, message, wParam, lParam):
        if message == WM_PAINT:
            # The window has no GDI content; validate the update region and
            # re-compose the layered surface (this also advances the frame).
            ps = PAINTSTRUCT()
            BeginPaint(hwnd, ct.byref(ps))
            self.currentSprite = self.mascot.getNextImage()
            self._present()
            EndPaint(hwnd, ct.byref(ps))
            return 0
        elif message == WM_LBUTTONDOWN:
            # Per-pixel alpha means this only fires over the mascot itself.
            SetCapture(hwnd)
            self.dragging = True
            self.dragMoved = False
            self.dragStartX = GET_X_LPARAM(lParam)
            self.dragStartY = GET_Y_LPARAM(lParam)
            self.dragMascotX = self.mascotX
            self.dragMascotY = self.mascotY
            return 0
        elif message == WM_MOUSEMOVE and self.dragging:
            dx = GET_X_LPARAM(lParam) - self.dragStartX
            dy = GET_Y_LPARAM(lParam) - self.dragStartY
            if not self.dragMoved:
                if (abs(dx) > GetSystemMetrics(SM_CXDRAG) or
                        abs(dy) > GetSystemMetrics(SM_CYDRAG)):
                    self.dragMoved = True
            if self.dragMoved:
                SetCursor(self.sizeAllCursor)
                if self._moveMascot(self.dragMascotX + dx, self.dragMascotY + dy):
                    self._present()
            return 0
        elif message == WM_LBUTTONUP:
            if self.dragging:
                wasClick = not self.dragMoved
                self.dragging = False
                ReleaseCapture()
                if wasClick:
                    self._onClick()
            return 0
        elif message == WM_CAPTURECHANGED:
            self.dragging = False
            return 0
        elif message == WM_DESTROY or (message == WM_KEYDOWN and wParam == VK_ESCAPE):
            PostQuitMessage(0)
            return 0

        return DefWindowProc(hwnd, message, wParam, lParam)

def main():
    return MascotDisplay().run()

if __name__ == '__main__':
    sys.exit(main())
