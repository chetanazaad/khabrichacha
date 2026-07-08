import os
import platform
import sys

def get_cpu_cores() -> int:
    """Return the number of CPU cores."""
    cores = os.cpu_count()
    return cores if cores is not None else 4

def get_total_ram_gb() -> float:
    """Return the total system memory (RAM) in gigabytes."""
    system = platform.system()
    if system == "Windows":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys / (1024 ** 3)
        except Exception:
            pass
    elif system == "Linux":
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return float(parts[1]) / (1024 * 1024)
        except Exception:
            pass
    elif system == "Darwin":
        try:
            import subprocess
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
            if result.returncode == 0:
                return float(result.stdout.strip()) / (1024 ** 3)
        except Exception:
            pass
    
    return 8.0

def get_gpu_details() -> dict:
    """Return details about the GPU if available (specifically VRAM)."""
    details = {
        "available": False,
        "name": "",
        "vram_gb": 0.0
    }
    try:
        import torch
        if torch.cuda.is_available():
            details["available"] = True
            details["name"] = torch.cuda.get_device_name(0)
            details["vram_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    except Exception:
        pass
    return details
