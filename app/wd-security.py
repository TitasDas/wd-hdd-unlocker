#!/usr/bin/env python3
"""WD My Passport Linux Unlocker: desktop entry point."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wdpassport.ui.app import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
