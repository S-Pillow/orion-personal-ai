"""Windows handles only. No command-line scanning or PID-only termination."""
import ctypes
from ctypes import wintypes as W
import os


class IdentityUnavailable(RuntimeError):
    pass


class Process:
    def __init__(self, handle):
        self.handle = handle

    @staticmethod
    def api():
        if os.name != "nt":
            raise IdentityUnavailable("Windows is required")
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        k.OpenProcess.restype = W.HANDLE
        k.GetCurrentProcess.restype = W.HANDLE
        k.DuplicateHandle.argtypes = [W.HANDLE, W.HANDLE, W.HANDLE, ctypes.POINTER(W.HANDLE), W.DWORD, W.BOOL, W.DWORD]
        k.DuplicateHandle.restype = W.BOOL
        k.GetProcessId.argtypes = [W.HANDLE]
        k.GetProcessId.restype = W.DWORD
        k.GetProcessTimes.argtypes = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4
        k.GetProcessTimes.restype = W.BOOL
        k.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        k.QueryFullProcessImageNameW.restype = W.BOOL
        k.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        k.WaitForSingleObject.restype = W.DWORD
        k.TerminateProcess.argtypes = [W.HANDLE, W.UINT]
        k.TerminateProcess.restype = W.BOOL
        k.CloseHandle.argtypes = [W.HANDLE]
        k.CloseHandle.restype = W.BOOL
        return k

    @classmethod
    def from_child(cls, child):
        # CPython Windows Popen retains the ORIGINAL CreateProcess handle. Duplicate
        # that handle; never reopen child.pid after creation. Tested by a Windows gate.
        k = cls.api()
        new = W.HANDLE()
        if not k.DuplicateHandle(k.GetCurrentProcess(), int(child._handle),
                                 k.GetCurrentProcess(), ctypes.byref(new), 0, False, 2):
            raise IdentityUnavailable("Cannot retain original process handle")
        return cls(new)

    @classmethod
    def open(cls, pid, terminate=False):
        k = cls.api()
        h = k.OpenProcess(0x1000 | 0x100000 | (1 if terminate else 0), False, pid)
        if not h:
            if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: PID absent
                return None
            raise IdentityUnavailable("Cannot inspect process")
        return cls(h)

    def exited(self):
        result = self.api().WaitForSingleObject(self.handle, 0)
        if result == 0:
            return True
        if result == 258:
            return False
        raise IdentityUnavailable("Cannot determine process exit")

    def identity(self):
        k = self.api()
        times = [W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(self.handle, *(ctypes.byref(t) for t in times)):
            raise IdentityUnavailable("Cannot read process creation time")
        size = W.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if not k.QueryFullProcessImageNameW(self.handle, 0, buf, ctypes.byref(size)):
            raise IdentityUnavailable("Cannot read process image")
        return {"pid": int(k.GetProcessId(self.handle)),
                "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                "image": buf.value}

    def kill_verified(self, expected):
        if self.exited():
            return "absent"
        if not same(self.identity(), expected):
            return "different"
        # The SAME retained handle is used for comparison and termination.
        if not self.api().TerminateProcess(self.handle, 1):
            raise IdentityUnavailable("Termination failed")
        if self.api().WaitForSingleObject(self.handle, 5000) != 0:
            raise IdentityUnavailable("Process exit not verified")
        return "stopped"

    def close(self):
        if self.handle:
            self.api().CloseHandle(self.handle)
            self.handle = None


def same(a, b):
    return (a["pid"] == b["pid"] and a["created"] == b["created"]
            and a["image"].casefold() == b["image"].casefold())


def boot_id():
    """Kernel boot identity derived from Windows kernel BootTime.

    Stable during one Windows boot and changes after Restart.
    No wall-clock/uptime arithmetic is used.
    """
    if os.name != "nt":
        raise IdentityUnavailable("Windows is required")

    n = ctypes.WinDLL("ntdll")
    n.NtQuerySystemInformation.argtypes = [
        W.ULONG,
        W.LPVOID,
        W.ULONG,
        ctypes.POINTER(W.ULONG),
    ]
    n.NtQuerySystemInformation.restype = W.LONG

    # SystemTimeOfDayInformation = 3.
    # SYSTEM_TIMEOFDAY_INFORMATION begins with LARGE_INTEGER BootTime.
    buf = ctypes.create_string_buffer(48)
    used = W.ULONG()

    status = n.NtQuerySystemInformation(
        3,
        buf,
        len(buf),
        ctypes.byref(used),
    )

    if status != 0:
        raise IdentityUnavailable("Cannot establish Windows boot identity")

    value = int.from_bytes(buf.raw[:8], "little", signed=True)

    if value <= 0:
        raise IdentityUnavailable("Invalid Windows boot identity")

    return value
