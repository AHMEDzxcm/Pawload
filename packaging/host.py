"""Entry point for palwoad-host.exe, the browser pairing helper (console, stdlib only)."""
import sys

from palwoad.native import host_main

if __name__ == "__main__":
    host_main(sys.argv[1:])
