"""
Native Windows DWM Frameless Resizing via WM_NCHITTEST.
Provides hardware-accelerated, zero-Python-overhead window border resizing on Windows.
Compatible with Python 2.7 and Python 3.x.
"""

import sys
import ctypes

from hud.core.constants import (
    RESIZE_MARGIN_HORIZONTAL,
    RESIZE_MARGIN_VERTICAL,
)

# Win32 Constants
WM_NCHITTEST = 0x0084
HTNOWHERE = 0
HTCLIENT = 1
HTCAPTION = 2
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

if sys.platform == "win32":
    from ctypes import wintypes
    
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]


class Win32FramelessHelper(object):
    """
    Helper for handling WM_NCHITTEST messages in QWidget.nativeEvent on Windows.
    Enforces a tight 3px vertical / 6px horizontal hit-testing boundary for ultra-compact containers.
    """

    @staticmethod
    def handle_native_event(widget, event_type, message):
        """
        Inspects native Windows message. Returns (is_handled, result_code).
        """
        if sys.platform != "win32" or event_type != "windows_generic_MSG":
            return False, 0

        try:
            msg_ptr = int(message)
            msg = MSG.from_address(msg_ptr)

            if msg.message == WM_NCHITTEST:
                # Screen coordinates from lParam
                x_pos = msg.lParam & 0xFFFF
                if x_pos > 0x7FFF:
                    x_pos -= 0x10000
                y_pos = (msg.lParam >> 16) & 0xFFFF
                if y_pos > 0x7FFF:
                    y_pos -= 0x10000

                geom = widget.frameGeometry()
                margin_x = RESIZE_MARGIN_HORIZONTAL
                margin_y = RESIZE_MARGIN_VERTICAL

                x_left = geom.left()
                x_right = geom.right()
                y_top = geom.top()
                y_bottom = geom.bottom()

                left = x_pos <= x_left + margin_x
                right = x_pos >= x_right - margin_x
                top = y_pos <= y_top + margin_y
                bottom = y_pos >= y_bottom - margin_y

                if top and left:
                    return True, HTTOPLEFT
                elif top and right:
                    return True, HTTOPRIGHT
                elif bottom and left:
                    return True, HTBOTTOMLEFT
                elif bottom and right:
                    return True, HTBOTTOMRIGHT
                elif left:
                    return True, HTLEFT
                elif right:
                    return True, HTRIGHT
                elif top:
                    return True, HTTOP
                elif bottom:
                    return True, HTBOTTOM

        except Exception:
            pass

        return False, 0
