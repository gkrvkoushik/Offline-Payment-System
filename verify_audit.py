"""Convenience CLI script for standalone independent audit verification."""

import sys
from offline_payment.audit.verify_cli import main

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
