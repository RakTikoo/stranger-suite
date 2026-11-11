import sys

try:
    with open("greeting.txt", encoding="utf-8") as f:
        message = f.read().strip()
except FileNotFoundError:
    print("Missing input file: greeting.txt", file=sys.stderr)
    sys.exit(2)

print(message)
