from __future__ import unicode_literals

import sys
import ctypes as ct

from mascot import Mascot

# Generic Windows types built from plain ctypes primitives.
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

# WPARAM is an unsigned pointer-sized type, LPARAM/LRESULT are signed.
if ct.sizeof(ct.c_long) == ct.sizeof(ct.c_void_p):
    WPARAM = ct.c_ulong
    LPARAM = ct.c_long
    LRESULT = ct.c_long
else:
    WPARAM = ct.c_ulonglong
    LPARAM = ct.c_longlong
    LRESULT = ct.c_longlong

class POINT(ct.Structure):
    _fields_ = (('x', LONG),
                ('y', LONG))

class RECT(ct.Structure):
    _fields_ = (('left', LONG),
                ('top', LONG),
                ('right', LONG),
                ('bottom', LONG))

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

def errcheck(result, func, args):
    if result is None or result == 0:
        raise ct.WinError(ct.get_last_error())
    return result

def minusonecheck(result, func, args):
    if result == -1:
        raise ct.WinError(ct.get_last_error())
    return result

WNDPROC = ct.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

def MAKEINTRESOURCE(x):
    return LPCWSTR(x)

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

kernel32 = ct.WinDLL('kernel32', use_last_error=True)
GetModuleHandle = kernel32.GetModuleHandleW
GetModuleHandle.argtypes = LPCWSTR,
GetModuleHandle.restype = HMODULE
GetModuleHandle.errcheck = errcheck

user32 = ct.WinDLL('user32', use_last_error=True)
CreateWindowEx = user32.CreateWindowExW
CreateWindowEx.argtypes = DWORD, LPCWSTR, LPCWSTR, DWORD, ct.c_int, ct.c_int, ct.c_int, ct.c_int, HWND, HMENU, HINSTANCE, LPVOID
CreateWindowEx.restype = HWND
CreateWindowEx.errcheck = errcheck
LoadIcon = user32.LoadIconW
LoadIcon.argtypes = HINSTANCE, LPCWSTR
LoadIcon.restype = HICON
LoadIcon.errcheck = errcheck
LoadCursor = user32.LoadCursorW
LoadCursor.argtypes = HINSTANCE, LPCWSTR
LoadCursor.restype = HCURSOR
LoadCursor.errcheck = errcheck
RegisterClass = user32.RegisterClassW
RegisterClass.argtypes = ct.POINTER(WNDCLASS),
RegisterClass.restype = ATOM
RegisterClass.errcheck = errcheck
ShowWindow = user32.ShowWindow
ShowWindow.argtypes = HWND, ct.c_int
ShowWindow.restype = BOOL
UpdateWindow = user32.UpdateWindow
UpdateWindow.argtypes = HWND,
UpdateWindow.restype = BOOL
UpdateWindow.errcheck = errcheck
GetMessage = user32.GetMessageW
GetMessage.argtypes = ct.POINTER(MSG), HWND, UINT, UINT
GetMessage.restype = BOOL
GetMessage.errcheck = minusonecheck
TranslateMessage = user32.TranslateMessage
TranslateMessage.argtypes = ct.POINTER(MSG),
TranslateMessage.restype = BOOL
DispatchMessage = user32.DispatchMessageW
DispatchMessage.argtypes = ct.POINTER(MSG),
DispatchMessage.restype = LRESULT
BeginPaint = user32.BeginPaint
BeginPaint.argtypes = HWND, ct.POINTER(PAINTSTRUCT)
BeginPaint.restype = HDC
GetClientRect = user32.GetClientRect
GetClientRect.argtypes = HWND, ct.POINTER(RECT)
GetClientRect.restype = BOOL
GetClientRect.errcheck = errcheck
DrawText = user32.DrawTextW
DrawText.argtypes = HDC, LPCWSTR, ct.c_int, ct.POINTER(RECT), UINT
DrawText.restype = ct.c_int
GetSystemMetrics = user32.GetSystemMetrics
GetSystemMetrics.argtypes = ct.c_int,
GetSystemMetrics.restype = ct.c_int
SetForegroundWindow = user32.SetForegroundWindow
SetForegroundWindow.argtypes = HWND,
SetForegroundWindow.restype = BOOL
SetCapture = user32.SetCapture
SetCapture.argtypes = HWND,
SetCapture.restype = HWND
ReleaseCapture = user32.ReleaseCapture
ReleaseCapture.argtypes = ()
ReleaseCapture.restype = BOOL
SetCursor = user32.SetCursor
SetCursor.argtypes = HCURSOR,
SetCursor.restype = HCURSOR
SetProcessDPIAware = user32.SetProcessDPIAware
SetProcessDPIAware.argtypes = ()
SetProcessDPIAware.restype = BOOL
UpdateLayeredWindow = user32.UpdateLayeredWindow
UpdateLayeredWindow.argtypes = HWND, HDC, ct.POINTER(POINT), ct.POINTER(SIZE), HDC, ct.POINTER(POINT), DWORD, ct.POINTER(BLENDFUNCTION), DWORD
UpdateLayeredWindow.restype = BOOL
UpdateLayeredWindow.errcheck = errcheck
EndPaint = user32.EndPaint
EndPaint.argtypes = HWND, ct.POINTER(PAINTSTRUCT)
EndPaint.restype = BOOL
PostQuitMessage = user32.PostQuitMessage
PostQuitMessage.argtypes = ct.c_int,
PostQuitMessage.restype = None
DefWindowProc = user32.DefWindowProcW
DefWindowProc.argtypes = HWND, UINT, WPARAM, LPARAM
DefWindowProc.restype = LRESULT

gdi32 = ct.WinDLL('gdi32', use_last_error=True)
GetStockObject = gdi32.GetStockObject
GetStockObject.argtypes = ct.c_int,
GetStockObject.restype = HGDIOBJ
CreateDIBSection = gdi32.CreateDIBSection
CreateDIBSection.argtypes = HDC, ct.POINTER(BITMAPINFO), UINT, ct.POINTER(ct.c_void_p), HANDLE, DWORD
CreateDIBSection.restype = HANDLE
CreateDIBSection.errcheck = errcheck
CreateCompatibleDC = gdi32.CreateCompatibleDC
CreateCompatibleDC.argtypes = HDC,
CreateCompatibleDC.restype = HDC
CreateCompatibleDC.errcheck = errcheck
SelectObject = gdi32.SelectObject
SelectObject.argtypes = HDC, HGDIOBJ
SelectObject.restype = HGDIOBJ
DeleteDC = gdi32.DeleteDC
DeleteDC.argtypes = HDC,
DeleteDC.restype = BOOL
DeleteObject = gdi32.DeleteObject
DeleteObject.argtypes = HGDIOBJ,
DeleteObject.restype = BOOL
GdiFlush = gdi32.GdiFlush
GdiFlush.argtypes = ()
GdiFlush.restype = BOOL

# GDI+ is used only to blit the mascot sprite (a PNG with an alpha channel).
gdiplus = ct.WinDLL('gdiplus', use_last_error=True)

class GdiplusStartupInput(ct.Structure):
    _fields_ = (('GdiplusVersion', UINT),
                ('DebugEventCallback', LPVOID),
                ('SuppressBackgroundThread', BOOL),
                ('SuppressExternalCodecs', BOOL))

def gdipcheck(status, func, args):
    # GDI+ returns its own Status codes, not Win32 error codes.
    if status != 0:
        raise RuntimeError('%s failed with GDI+ status %d' % (func.__name__, status))
    return status

GdiplusStartup = gdiplus.GdiplusStartup
GdiplusStartup.argtypes = ct.POINTER(ct.c_void_p), ct.POINTER(GdiplusStartupInput), LPVOID
GdiplusStartup.restype = ct.c_int
GdiplusStartup.errcheck = gdipcheck
GdiplusShutdown = gdiplus.GdiplusShutdown
GdiplusShutdown.argtypes = ct.c_void_p,
GdiplusShutdown.restype = None
GdipCreateBitmapFromFile = gdiplus.GdipCreateBitmapFromFile
GdipCreateBitmapFromFile.argtypes = LPCWSTR, ct.POINTER(ct.c_void_p)
GdipCreateBitmapFromFile.restype = ct.c_int
GdipCreateBitmapFromFile.errcheck = gdipcheck
GdipCreateFromHDC = gdiplus.GdipCreateFromHDC
GdipCreateFromHDC.argtypes = HDC, ct.POINTER(ct.c_void_p)
GdipCreateFromHDC.restype = ct.c_int
GdipCreateFromHDC.errcheck = gdipcheck
GdipGetImageWidth = gdiplus.GdipGetImageWidth
GdipGetImageWidth.argtypes = ct.c_void_p, ct.POINTER(UINT)
GdipGetImageWidth.restype = ct.c_int
GdipGetImageWidth.errcheck = gdipcheck
GdipGetImageHeight = gdiplus.GdipGetImageHeight
GdipGetImageHeight.argtypes = ct.c_void_p, ct.POINTER(UINT)
GdipGetImageHeight.restype = ct.c_int
GdipGetImageHeight.errcheck = gdipcheck
GdipSetInterpolationMode = gdiplus.GdipSetInterpolationMode
GdipSetInterpolationMode.argtypes = ct.c_void_p, ct.c_int
GdipSetInterpolationMode.restype = ct.c_int
GdipDrawImageRectI = gdiplus.GdipDrawImageRectI
GdipDrawImageRectI.argtypes = ct.c_void_p, ct.c_void_p, ct.c_int, ct.c_int, ct.c_int, ct.c_int
GdipDrawImageRectI.restype = ct.c_int
GdipDrawImageRectI.errcheck = gdipcheck
GdipDeleteGraphics = gdiplus.GdipDeleteGraphics
GdipDeleteGraphics.argtypes = ct.c_void_p,
GdipDeleteGraphics.restype = ct.c_int
GdipDisposeImage = gdiplus.GdipDisposeImage
GdipDisposeImage.argtypes = ct.c_void_p,
GdipDisposeImage.restype = ct.c_int

CW_USEDEFAULT = ct.c_int(0x80000000).value
IDI_APPLICATION = MAKEINTRESOURCE(32512)

WS_OVERLAPPED  = 0x00000000
WS_CAPTION     = 0x00C00000
WS_SYSMENU     = 0x00080000
WS_THICKFRAME  = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

WS_OVERLAPPEDWINDOW = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
assert WS_OVERLAPPEDWINDOW == 0x00CF0000

# Borderless window with no caption; used for fullscreen.
WS_POPUP = 0x80000000
assert WS_POPUP == 0x80000000

WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

BI_RGB = 0
DIB_RGB_COLORS = 0

SM_CXSCREEN = 0
SM_CYSCREEN = 1

CS_HREDRAW = 2
CS_VREDRAW = 1

IDC_ARROW = MAKEINTRESOURCE(32512)
IDC_SIZEALL = MAKEINTRESOURCE(32646)

SW_SHOWNORMAL = 1

WM_PAINT = 15
WM_DESTROY = 2
WM_KEYDOWN = 0x0100
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_CAPTURECHANGED = 0x0215
VK_ESCAPE = 0x1B
DT_SINGLELINE = 32
DT_CENTER = 1
DT_VCENTER = 4

# ------------------------------- tweaks ----------------------------------
# Sprites are 1336x948 PNGs; draw them at this fraction of natural size.
# 0.25 = small, 0.5 = half size, 1.0 = full size.
MASCOT_SCALE = 0.35
# -------------------------------------------------------------------------
INTERPOLATION_HIGH_QUALITY_BICUBIC = 7

mascot = None
currentSprite = None  # sprite path currently on screen
spriteCache = {}      # PNG path -> GDI+ bitmap handle

# Where the sprite sits in window coordinates.
mascotX = 0
mascotY = 0

# Drag state, in window coordinates.
dragging = False
dragStartX = 0
dragStartY = 0
dragMascotX = 0
dragMascotY = 0

# Per-pixel-alpha surface the layered window is composed from.
surfaceBitmap = None
surfaceDC = None
surfaceBits = None
surfaceWidth = 0
surfaceHeight = 0

def loadSprite(path):
    """Load a sprite PNG into a cached GDI+ bitmap (keeps its alpha channel)."""
    bitmap = spriteCache.get(path)
    if bitmap is not None:
        return bitmap

    bitmap = ct.c_void_p()
    GdipCreateBitmapFromFile(path, ct.byref(bitmap))
    spriteCache[path] = bitmap
    return bitmap

def GET_X_LPARAM(lParam):
    return ct.c_short(lParam & 0xFFFF).value

def GET_Y_LPARAM(lParam):
    return ct.c_short((lParam >> 16) & 0xFFFF).value

def mascotSize(path):
    """On-screen size of one sprite after MASCOT_SCALE."""
    bitmap = loadSprite(path)
    width = UINT()
    height = UINT()
    GdipGetImageWidth(bitmap, ct.byref(width))
    GdipGetImageHeight(bitmap, ct.byref(height))
    return int(width.value * MASCOT_SCALE), int(height.value * MASCOT_SCALE)

def drawSprite(hdc, path, x, y):
    """Draw one sprite at (x, y), scaled by MASCOT_SCALE."""
    bitmap = loadSprite(path)
    drawW, drawH = mascotSize(path)

    graphics = ct.c_void_p()
    GdipCreateFromHDC(hdc, ct.byref(graphics))
    GdipSetInterpolationMode(graphics, INTERPOLATION_HIGH_QUALITY_BICUBIC)
    GdipDrawImageRectI(graphics, bitmap, x, y, drawW, drawH)
    GdipDeleteGraphics(graphics)

def createSurface(width, height):
    """32-bit top-down DIB; zeroed pixels are fully transparent."""
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ct.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height  # negative height = top-down rows
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    bits = ct.c_void_p()
    dib = CreateDIBSection(None, ct.byref(bmi), DIB_RGB_COLORS, ct.byref(bits), None, 0)
    dc = CreateCompatibleDC(None)
    SelectObject(dc, dib)
    return dib, dc, bits

def moveMascot(x, y):
    """Move the sprite, keeping it fully on screen. Returns True if it moved."""
    global mascotX, mascotY
    drawW, drawH = mascotSize(currentSprite)
    x = min(max(x, 0), max(0, surfaceWidth - drawW))
    y = min(max(y, 0), max(0, surfaceHeight - drawH))
    if (x, y) == (mascotX, mascotY):
        return False
    mascotX, mascotY = x, y
    return True

def present(hwnd):
    """Render the current frame into the alpha surface and compose it on screen."""
    # Clear to transparent; the sprite supplies every visible pixel, so its
    # soft edges blend against nothing and no background color can bleed in.
    ct.memset(surfaceBits, 0, surfaceWidth * surfaceHeight * 4)
    drawSprite(surfaceDC, currentSprite, mascotX, mascotY)
    GdiFlush()  # make sure every batched GDI call landed in the DIB

    size = SIZE(surfaceWidth, surfaceHeight)
    src = POINT(0, 0)
    blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
    UpdateLayeredWindow(hwnd, None, None, ct.byref(size), surfaceDC,
                        ct.byref(src), 0, ct.byref(blend), ULW_ALPHA)

def MainWin():
    global mascot, currentSprite, mascotX, mascotY
    global surfaceBitmap, surfaceDC, surfaceBits, surfaceWidth, surfaceHeight

    # Opt into per-monitor DPI so the text stays crisp on scaled displays.
    SetProcessDPIAware()

    # Start GDI+ and the mascot before the window needs to paint.
    gdiplusToken = ct.c_void_p()
    gdiplusStartup = GdiplusStartupInput()
    gdiplusStartup.GdiplusVersion = 1
    GdiplusStartup(ct.byref(gdiplusToken), ct.byref(gdiplusStartup), None)
    mascot = Mascot()

    # Define Window Class
    # The client area is never GDI-painted: the window is composed from the
    # per-pixel-alpha surface instead, so no background brush is needed.
    wndclass = WNDCLASS()
    wndclass.style         = CS_HREDRAW | CS_VREDRAW
    wndclass.lpfnWndProc   = WNDPROC(WndProc)
    wndclass.cbClsExtra    = 0
    wndclass.cbWndExtra    = 0
    wndclass.hInstance     = GetModuleHandle(None)
    wndclass.hIcon         = LoadIcon(None, IDI_APPLICATION)
    wndclass.hCursor       = LoadCursor(None, IDC_ARROW)
    wndclass.hbrBackground = None
    wndclass.lpszMenuName  = None
    wndclass.lpszClassName = 'MainWin'

    # Register Window Class
    RegisterClass(ct.byref(wndclass))

    # Create Window. WS_EX_LAYERED is required for UpdateLayeredWindow;
    # WS_EX_TOPMOST pins the mascot above every other window.
    # WS_POPUP + screen-sized rect = borderless fullscreen. Swap WS_POPUP for
    # WS_OVERLAPPEDWINDOW (and the rect for CW_USEDEFAULT) for a normal window.
    screen_w = GetSystemMetrics(SM_CXSCREEN)
    screen_h = GetSystemMetrics(SM_CYSCREEN)

    hwnd = CreateWindowEx(WS_EX_LAYERED | WS_EX_TOPMOST,
                          wndclass.lpszClassName,
                          'Python Window',
                          WS_POPUP,
                          0,
                          0,
                          screen_w,
                          screen_h,
                          None,
                          None,
                          wndclass.hInstance,
                          None)

    # Compose from a per-pixel-alpha surface: transparent where there is no
    # art, so edges stay clean instead of picking up a background color.
    surfaceBitmap, surfaceDC, surfaceBits = createSurface(screen_w, screen_h)
    surfaceWidth, surfaceHeight = screen_w, screen_h

    # Start with the sprite centered on screen.
    currentSprite = mascot.getNextImage()
    drawW, drawH = mascotSize(currentSprite)
    mascotX = (surfaceWidth - drawW) // 2
    mascotY = (surfaceHeight - drawH) // 2
    present(hwnd)

    # Show Window
    user32.ShowWindow(hwnd, SW_SHOWNORMAL)
    # Borderless windows don't always take focus on their own; needed for Esc.
    SetForegroundWindow(hwnd)

    # Pump Messages
    msg = MSG()
    while GetMessage(ct.byref(msg), None, 0, 0) != 0:
        TranslateMessage(ct.byref(msg))
        DispatchMessage(ct.byref(msg))

    for bitmap in spriteCache.values():
        GdipDisposeImage(bitmap)
    spriteCache.clear()
    GdiplusShutdown(gdiplusToken)
    DeleteDC(surfaceDC)
    DeleteObject(surfaceBitmap)

    return msg.wParam

def WndProc(hwnd, message, wParam, lParam):
    global currentSprite, dragging
    global dragStartX, dragStartY, dragMascotX, dragMascotY

    ps = PAINTSTRUCT()

    if message == WM_PAINT:
        # The window has no GDI content; validate the update region and
        # re-compose the layered surface (this also advances the frame).
        BeginPaint(hwnd, ct.byref(ps))
        currentSprite = mascot.getNextImage()
        present(hwnd)
        EndPaint(hwnd, ct.byref(ps))
        return 0
    elif message == WM_LBUTTONDOWN:
        # Per-pixel alpha means this only fires over the mascot itself.
        SetCapture(hwnd)
        dragging = True
        dragStartX = GET_X_LPARAM(lParam)
        dragStartY = GET_Y_LPARAM(lParam)
        dragMascotX = mascotX
        dragMascotY = mascotY
        return 0
    elif message == WM_MOUSEMOVE and dragging:
        SetCursor(LoadCursor(None, IDC_SIZEALL))
        if moveMascot(dragMascotX + GET_X_LPARAM(lParam) - dragStartX,
                      dragMascotY + GET_Y_LPARAM(lParam) - dragStartY):
            present(hwnd)
        return 0
    elif message == WM_LBUTTONUP:
        if dragging:
            dragging = False
            ReleaseCapture()
        return 0
    elif message == WM_CAPTURECHANGED:
        dragging = False
        return 0
    elif message == WM_KEYDOWN and wParam == VK_ESCAPE:
        PostQuitMessage(0)
        return 0
    elif message == WM_DESTROY:
        PostQuitMessage(0)
        return 0

    return DefWindowProc(hwnd, message, wParam, lParam)

if __name__=='__main__':
    sys.exit(MainWin())
