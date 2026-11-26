"""Send ready-made ESC/POS bytes to a thermal printer. Standard library only.

Targets:
  tcp:HOST[:PORT]        LAN or Wi-Fi printer on a private address (port 9100)
  windows:PRINTER NAME   any printer installed in Windows (USB, LAN, Bluetooth), sent RAW
  serial:COM5[@19200]    serial or Bluetooth COM port on Windows
  file:/dev/usb/lp0      Linux device file; accepted only from this till's own settings

Nothing here opens a print dialog. A function returns only when the bytes were
accepted; otherwise it raises PrintError. Accepted is not proof that paper came out.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import sys
import threading
import time

TCP_TIMEOUT = 4.0
SPOOL_TIMEOUT = 12.0


class PrintError(Exception):
    pass


def send(target: str, data: bytes, *, local: bool = False) -> None:
    """Print `data`. `local` marks a target typed into this till's own settings."""
    if not data:
        raise PrintError("There is nothing to print")
    kind, _, rest = (target or "").partition(":")
    kind = kind.lower()
    if not rest:
        raise PrintError("No printer is set up for this till")
    if kind == "tcp":
        _send_tcp(rest, data)
    elif kind == "windows":
        _send_windows(rest, data)
    elif kind == "serial":
        _send_serial(rest, data)
    elif kind == "file" and local:
        _send_file(rest, data)
    else:
        raise PrintError("This printer setting is not allowed")


# ---------------------------------------------------------------- network


def _private_address(host: str, port: int) -> str:
    try:
        found = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        raise PrintError("The printer address could not be found") from exc
    address = found[0][4][0]
    ip = ipaddress.ip_address(address)
    if not (ip.is_private or ip.is_loopback) or ip.is_link_local or ip.is_unspecified:
        raise PrintError("The printer must be on this shop's own network")
    return address


def _send_tcp(rest: str, data: bytes) -> None:
    host, _, port_text = rest.partition(":")
    try:
        port = int(port_text or "9100")
    except ValueError as exc:
        raise PrintError("The printer port is not a number") from exc
    if not 1 <= port <= 65535:
        raise PrintError("The printer port is not valid")
    address = _private_address(host, port)
    try:
        with socket.create_connection((address, port), timeout=TCP_TIMEOUT) as sock:
            _check_printer_status(sock)
            sock.settimeout(TCP_TIMEOUT)
            sock.sendall(data)
    except PrintError:
        raise
    except OSError as exc:
        raise PrintError(f"Could not reach the printer at {host}:{port}") from exc


def _ask_status(sock: socket.socket, query: int) -> int | None:
    """ESC/POS real-time status (DLE EOT n). Many printers answer; silence is not a fault."""
    try:
        sock.sendall(bytes((0x10, 0x04, query)))
        sock.settimeout(0.35)
        reply = sock.recv(1)
    except (socket.timeout, TimeoutError):
        return None
    # A real status byte always has bits 1 and 4 set and bits 0 and 7 clear.
    if len(reply) == 1 and reply[0] & 0x93 == 0x12:
        return reply[0]
    return None


def _check_printer_status(sock: socket.socket) -> None:
    status = _ask_status(sock, 1)
    if status is None:
        return
    paper = _ask_status(sock, 4)
    if paper is not None and paper & 0x60:
        raise PrintError("The printer is out of paper")
    if status & 0x08:
        raise PrintError("The printer is offline. Check the cover, paper and error light")


# ---------------------------------------------------------------- Windows spooler

_JOB_PROBLEMS = (
    (0x00000040, "The printer is out of paper"),
    (0x00000020, "The printer is offline"),
    (0x00000002, "Windows reports a printer error"),
    (0x00000200, "The Windows print queue is blocked"),
    (0x00000400, "The printer needs attention"),
)
_JOB_DONE = 0x00000080 | 0x00001000  # printed, or fully handed to the printer


def job_state(status: int) -> tuple[bool, str | None]:
    """(finished, problem) for a Windows spooler job status."""
    if status & _JOB_DONE:
        return True, None
    for bit, words in _JOB_PROBLEMS:
        if status & bit:
            return False, words
    return False, None


def _send_windows(name: str, data: bytes) -> None:
    if sys.platform != "win32":
        raise PrintError("Windows printer names work only on a Windows till")
    import ctypes
    from ctypes import wintypes

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]

    class JOB_INFO_1(ctypes.Structure):
        _fields_ = [
            ("JobId", wintypes.DWORD),
            ("pPrinterName", wintypes.LPWSTR),
            ("pMachineName", wintypes.LPWSTR),
            ("pUserName", wintypes.LPWSTR),
            ("pDocument", wintypes.LPWSTR),
            ("pDatatype", wintypes.LPWSTR),
            ("pStatus", wintypes.LPWSTR),
            ("Status", wintypes.DWORD),
            ("Priority", wintypes.DWORD),
            ("Position", wintypes.DWORD),
            ("TotalPages", wintypes.DWORD),
            ("PagesPrinted", wintypes.DWORD),
            ("Submitted", wintypes.WORD * 8),
        ]

    spool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    spool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    spool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    spool.StartDocPrinterW.restype = wintypes.DWORD
    spool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    spool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    spool.EndPagePrinter.argtypes = [wintypes.HANDLE]
    spool.EndDocPrinter.argtypes = [wintypes.HANDLE]
    spool.GetJobW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    spool.SetJobW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    spool.ClosePrinter.argtypes = [wintypes.HANDLE]

    handle = wintypes.HANDLE()
    if not spool.OpenPrinterW(name, ctypes.byref(handle), None):
        raise PrintError(f'Windows has no printer called "{name}"')
    try:
        info = DOC_INFO_1("RIBDIGI receipt", None, "RAW")
        job_id = spool.StartDocPrinterW(handle, 1, ctypes.byref(info))
        if not job_id:
            raise PrintError("Windows would not start the print job")
        written = wintypes.DWORD(0)
        ok = spool.StartPagePrinter(handle)
        if ok:
            ok = spool.WritePrinter(handle, data, len(data), ctypes.byref(written))
            spool.EndPagePrinter(handle)
        spool.EndDocPrinter(handle)
        if not ok or written.value != len(data):
            spool.SetJobW(handle, job_id, 0, None, 5)  # delete
            raise PrintError("Windows did not accept the whole receipt")

        # The spooler accepts a job even when the printer is switched off, so wait
        # for the job to leave the queue before calling it printed.
        deadline = time.monotonic() + SPOOL_TIMEOUT
        problem = None
        while time.monotonic() < deadline:
            needed = wintypes.DWORD(0)
            spool.GetJobW(handle, job_id, 1, None, 0, ctypes.byref(needed))
            if not needed.value:
                if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: the job has left the queue
                    return
                time.sleep(0.2)
                continue
            buffer = ctypes.create_string_buffer(needed.value)
            if not spool.GetJobW(handle, job_id, 1, buffer, needed.value, ctypes.byref(needed)):
                continue
            finished, found = job_state(JOB_INFO_1.from_buffer(buffer).Status)
            if finished:
                return
            problem = found or problem
            time.sleep(0.25)
        # Take it out of the queue, so it cannot print later on top of a retry.
        spool.SetJobW(handle, job_id, 0, None, 5)
        raise PrintError(problem or f'"{name}" did not print. Check that it is switched on and connected')
    finally:
        spool.ClosePrinter(handle)


# ---------------------------------------------------------------- serial and device files


def _send_serial(rest: str, data: bytes) -> None:
    match = re.fullmatch(r"(?i)(COM[1-9][0-9]{0,2})(?:@(\d{4,6}))?", rest)
    if not match:
        raise PrintError("The serial port must look like COM5 or COM5@19200")
    if sys.platform != "win32":
        raise PrintError("COM ports work only on a Windows till. Use file:/dev/… on Linux")
    port, baud = match.group(1).upper(), match.group(2)
    if baud:
        import subprocess

        # `port` and `baud` matched a strict pattern above; no shell is involved.
        subprocess.run(
            ["mode.com", f"{port}:", f"baud={baud}", "parity=n", "data=8", "stop=1"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    _send_file(f"\\\\.\\{port}", data)


def _send_file(path: str, data: bytes) -> None:
    failure: list[BaseException] = []

    def write() -> None:
        try:
            with open(path, "wb", buffering=0) as handle:
                view = memoryview(data)
                while view:
                    count = handle.write(view)
                    if not count:
                        raise OSError("short write")
                    view = view[count:]
        except OSError as exc:
            failure.append(exc)

    # A port with nothing listening can block for ever.
    worker = threading.Thread(target=write, daemon=True)
    worker.start()
    worker.join(SPOOL_TIMEOUT)
    if worker.is_alive():
        raise PrintError("The printer port did not respond")
    if failure:
        raise PrintError("Could not write to the printer port")
