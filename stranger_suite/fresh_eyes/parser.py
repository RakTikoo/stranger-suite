"""Extract setup/run commands from a README, in order, with line numbers.

Only fenced code blocks tagged bash/sh/shell/console (or untagged) are
treated as commands. Each non-empty, non-comment line is one command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ReadmeCommand:
    command: str
    line: int  # 1-based line in the README where this command appears


_CMD_LANGS = {"bash", "sh", "shell", "console", "zsh", ""}


def parse_readme_commands(readme_text):
    commands = []
    in_block = False
    block_is_cmd = False
    for i, raw in enumerate(readme_text.splitlines(), start=1):
        line = raw.rstrip("\n")
        fence = re.match(r"^```(\w*)\s*$", line.strip())
        if fence:
            if not in_block:
                in_block = True
                block_is_cmd = fence.group(1).lower() in _CMD_LANGS
            else:
                in_block = False
                block_is_cmd = False
            continue
        if in_block and block_is_cmd:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("$ "):
                s = s[2:]
            commands.append(ReadmeCommand(command=s, line=i))
    return commands
