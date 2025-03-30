#!/usr/bin/env python3
import sys
from msr605x import main

if __name__ == "__main__":
    # For testing the erase command, set the arguments accordingly.
    # Change "erase" to "write" (and provide track data) if you want to test writing.
    sys.argv = [
        sys.argv[0],
        "erase",
        "--tracks", "2,3"
    ]
    main()
