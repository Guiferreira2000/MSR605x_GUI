#!/usr/bin/env python3
import sys
from msr605x import main

if __name__ == "__main__":
    # Define track values as arguments.
    sys.argv = [
        sys.argv[0],
        "write",
        "--track1", "GUILHERMEFERREIRA",
        "--track2", "2024122820250328",
        "--track3", "0000000000000005",
        "--coercivity", "hi"
    ]
    main()
