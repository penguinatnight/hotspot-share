#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure src/ is in python path
src_dir = Path(__file__).resolve().parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from hotspot_share.cli import main

if __name__ == '__main__':
    main()
