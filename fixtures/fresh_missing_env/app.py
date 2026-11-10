import os, sys

name = os.environ.get("DEMO_GREETING")
if not name:
    print("Missing env var: DEMO_GREETING", file=sys.stderr)
    sys.exit(2)
print(f"HELLO_{name.upper()}")
