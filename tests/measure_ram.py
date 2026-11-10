import ctypes
from ctypes import wintypes
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import api.main

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

pmc = PROCESS_MEMORY_COUNTERS_EX()
pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
hProcess = ctypes.windll.kernel32.GetCurrentProcess()

if ctypes.windll.psapi.GetProcessMemoryInfo(hProcess, ctypes.byref(pmc), pmc.cb):
    print(f"FASTAPI + CORE MIDDLEWARE WORKING SET RAM: {pmc.WorkingSetSize / (1024 * 1024):.2f} MB")
    print(f"PRIVATE MEMORY USAGE (RAM): {pmc.PrivateUsage / (1024 * 1024):.2f} MB")
else:
    print("Failed to get process memory info.")
