#!/usr/bin/env python3
"""Convert Godot ``.tres`` resource properties to grouped JSON files.

Only properties in the ``[resource]`` section are exported. JSON-native Godot
values (strings, integers, floats, booleans and null) are converted to their
native JSON representation. Direct references to Texture2D external resources
are expanded with their type, uid, path and id. Other Godot expressions, such
as ExtResource(), Rect2(), Color() and typed arrays, are kept as strings so no
information is lost.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable


ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
EXT_RESOURCE_REF_RE = re.compile(r'^ExtResource\("([^"]+)"\)$')
HEADER_ATTRIBUTE_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"')
INTEGER_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(
    r"^[+-]?(?:\d+\.\d*|\.\d+|\d+[eE][+-]?\d+|\d+\.\d*[eE][+-]?\d+)$"
)


def parse_value(raw_value: str) -> Any:
    """Convert a simple Godot value and preserve complex expressions."""
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            # Godot may support escapes unknown to Python; preserve them.
            return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    if value in {"null", "nil"}:
        return None
    if INTEGER_RE.fullmatch(value):
        return int(value)
    if FLOAT_RE.fullmatch(value):
        return float(value)
    return value


def parse_ext_resource_header(line: str) -> dict[str, str] | None:
    """Parse an ``[ext_resource ...]`` declaration into its attributes."""
    stripped = line.strip()
    if not stripped.startswith("[ext_resource ") or not stripped.endswith("]"):
        return None
    attributes = dict(HEADER_ATTRIBUTE_RE.findall(stripped))
    return attributes if "id" in attributes else None


def resolve_texture_reference(
    value: Any, ext_resources: dict[str, dict[str, str]]
) -> Any:
    """Expand a direct Texture2D ExtResource reference and preserve other values."""
    if not isinstance(value, str):
        return value
    match = EXT_RESOURCE_REF_RE.fullmatch(value)
    if not match:
        return value
    resource = ext_resources.get(match.group(1))
    if resource is None or resource.get("type") != "Texture2D":
        return value
    return {
        "reference": value,
        "type": resource["type"],
        "uid": resource.get("uid", ""),
        "path": resource.get("path", "").removeprefix("res://"),
        "id": resource["id"],
    }


def _is_complete_expression(value: str) -> bool:
    """Return whether brackets and quoted strings in an expression are closed."""
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    in_string = False
    escaped = False

    for char in value:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != pairs[char]:
                return True  # Let Godot-invalid input pass through unchanged.
    return not in_string and not stack


def parse_tres(path: Path) -> dict[str, Any]:
    """Parse the exported properties from one Godot resource file."""
    result: dict[str, Any] = {"_source": path.name}
    in_resource = False
    pending_key: str | None = None
    pending_parts: list[str] = []
    ext_resources: dict[str, dict[str, str]] = {}

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        ext_resource = parse_ext_resource_header(stripped)
        if ext_resource is not None:
            ext_resources[ext_resource["id"]] = ext_resource
        if stripped.startswith("[") and stripped.endswith("]"):
            in_resource = stripped == "[resource]"
            continue
        if not in_resource or not stripped or stripped.startswith(";"):
            continue

        if pending_key is not None:
            pending_parts.append(stripped)
            combined = "\n".join(pending_parts)
            if _is_complete_expression(combined):
                result[pending_key] = resolve_texture_reference(
                    parse_value(combined), ext_resources
                )
                pending_key = None
                pending_parts = []
            continue

        match = ASSIGNMENT_RE.match(line)
        if not match:
            continue
        key, raw_value = match.groups()
        if _is_complete_expression(raw_value):
            result[key] = resolve_texture_reference(
                parse_value(raw_value), ext_resources
            )
        else:
            pending_key = key
            pending_parts = [raw_value]

    if pending_key is not None:
        raise ValueError(f"Unclosed value in {path} for {pending_key!r}")
    return result


def iter_resource_files(source_root: Path) -> Iterable[Path]:
    return sorted(
        (path for path in source_root.rglob("*.tres") if path.is_file()),
        key=lambda path: path.relative_to(source_root).as_posix().casefold(),
    )


def to_snake_case(name: str) -> str:
    """Convert a Resources directory name such as CharacterProfiles to snake_case."""
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def group_resource_files(source_root: Path) -> dict[str, list[Path]]:
    """Group files by their first directory below Resources."""
    groups: dict[str, list[Path]] = {}
    for path in iter_resource_files(source_root):
        relative = path.relative_to(source_root)
        group_name = relative.parts[0] if len(relative.parts) > 1 else "resources"
        groups.setdefault(to_snake_case(group_name), []).append(path)
    return groups


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse Godot .tres files below a Resources directory into JSON."
    )
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=Path("_game/Resources"),
        help="Resources directory (default: _game/Resources)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        type=Path,
        default=Path("data/generated/resources"),
        help="Output directory (default: data/generated/resources)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_root = args.source.resolve()
    if not source_root.is_dir():
        raise SystemExit(f"Resources directory not found: {source_root}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    groups = group_resource_files(source_root)
    for group_name, files in groups.items():
        records = [parse_tres(path) for path in files]
        output_path = args.output_dir / f"{group_name}.json"
        output_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        total += len(records)
        print(f"{group_name}: {len(records)} files -> {output_path}")
    print(f"Parsed {total} files into {len(groups)} JSON files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
