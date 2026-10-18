"""Judge control from a terminal, while run.py is running (same folder).

    python -m scripts.judge disrupt prairie 100     # Prairie can now supply only 100
    python -m scripts.judge restore prairie
    python -m scripts.judge reset                   # everyone back to full capacity
The supplier agents pick this up within ~2 s; the buyer only sees their replies.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supplier import controls
from supplier.profiles import PROFILES


def main():
    args = sys.argv[1:]
    if args[:1] == ["reset"]:
        controls.reset()
        print("All suppliers back to full capacity.")
    elif len(args) >= 2 and args[0] in ("disrupt", "restore") and args[1] in PROFILES:
        cap = int(args[2]) if args[0] == "disrupt" and len(args) > 2 else (0 if args[0] == "disrupt" else None)
        print(controls.set_capacity(args[1], cap))
    else:
        print(__doc__, f"Suppliers: {', '.join(PROFILES)}")


if __name__ == "__main__":
    main()
