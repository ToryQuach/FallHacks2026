from __future__ import unicode_literals

import sys
import ctypes as ct

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
SetProcessDPIAware = user32.SetProcessDPIAware
SetProcessDPIAware.argtypes = ()
SetProcessDPIAware.restype = BOOL
SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
SetLayeredWindowAttributes.argtypes = HWND, DWORD, BYTE, DWORD
SetLayeredWindowAttributes.restype = BOOL
SetLayeredWindowAttributes.errcheck = errcheck
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
LWA_COLORKEY = 0x00000001

SM_CXSCREEN = 0
SM_CYSCREEN = 1

# COLORREF is 0x00BBGGRR, so white is 0x00FFFFFF.
COLOR_WHITE = 0x00FFFFFF

CS_HREDRAW = 2
CS_VREDRAW = 1

IDC_ARROW = MAKEINTRESOURCE(32512)
WHITE_BRUSH = 0

SW_SHOWNORMAL = 1

WM_PAINT = 15
WM_DESTROY = 2
WM_KEYDOWN = 0x0100
VK_ESCAPE = 0x1B
DT_SINGLELINE = 32
DT_CENTER = 1
DT_VCENTER = 4

def MainWin():
    # Opt into per-monitor DPI so the text stays crisp on scaled displays.
    SetProcessDPIAware()

    # Define Window Class
    wndclass = WNDCLASS()
    wndclass.style         = CS_HREDRAW | CS_VREDRAW
    wndclass.lpfnWndProc   = WNDPROC(WndProc)
    wndclass.cbClsExtra    = 0
    wndclass.cbWndExtra    = 0
    wndclass.hInstance     = GetModuleHandle(None)
    wndclass.hIcon         = LoadIcon(None, IDI_APPLICATION)
    wndclass.hCursor       = LoadCursor(None, IDC_ARROW)
    wndclass.hbrBackground = GetStockObject(WHITE_BRUSH)
    wndclass.lpszMenuName  = None
    wndclass.lpszClassName = 'MainWin'

    # Register Window Class
    RegisterClass(ct.byref(wndclass))

    # Create Window. WS_EX_LAYERED is required for SetLayeredWindowAttributes.
    # WS_POPUP + screen-sized rect = borderless fullscreen. Swap WS_POPUP for
    # WS_OVERLAPPEDWINDOW (and the rect for CW_USEDEFAULT) for a normal window.
    screen_w = GetSystemMetrics(SM_CXSCREEN)
    screen_h = GetSystemMetrics(SM_CYSCREEN)

    hwnd = CreateWindowEx(WS_EX_LAYERED,
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

    # Make every white pixel transparent (color key), leaving the rest opaque.
    SetLayeredWindowAttributes(hwnd, COLOR_WHITE, 0, LWA_COLORKEY)

    # Show Window
    user32.ShowWindow(hwnd, SW_SHOWNORMAL)
    user32.UpdateWindow(hwnd)
    # Borderless windows don't always take focus on their own; needed for Esc.
    SetForegroundWindow(hwnd)

    # Pump Messages
    msg = MSG()
    while GetMessage(ct.byref(msg), None, 0, 0) != 0:
        TranslateMessage(ct.byref(msg))
        DispatchMessage(ct.byref(msg))

    return msg.wParam

def WndProc(hwnd, message, wParam, lParam):
    ps = PAINTSTRUCT()
    rect = RECT()

    if message == WM_PAINT:
        hdc = BeginPaint(hwnd, ct.byref(ps))
        GetClientRect(hwnd, ct.byref(rect))
        EndPaint(hwnd, ct.byref(ps))
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
