#!/usr/bin/env python3
import sys
from msr605x import main

if __name__ == "__main__":
    # Define track values as arguments.
    sys.argv = [
        sys.argv[0],
        "write",
        "--track1", "GUILH55",
        "--track2", "324345765445",
        "--track3", "975786567898768"
    ]
    main()
