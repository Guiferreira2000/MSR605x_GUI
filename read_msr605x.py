import sys
from msr605x import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "read"]
    main()
