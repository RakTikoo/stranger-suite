import json
import sys

try:
    with open("config.json", encoding="utf-8") as f:
        config = json.load(f)
except FileNotFoundError:
    print("Missing config file: config.json", file=sys.stderr)
    sys.exit(2)

print(f"HELLO_{config['name'].upper()}")
