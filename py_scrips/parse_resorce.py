#!/usr/bin/env python3
"""Convert each Godot resource file to one JSON file.

Properties in the ``[resource]`` section and embedded ``[sub_resource]``
sections are exported. JSON-native Godot
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


ASSIGNMENT_RE = re.compile(r"^([^\s=]+)\s*=\s*(.*)$")
EXT_RESOURCE_REF_RE = re.compile(r'^ExtResource\("([^"]+)"\)$')
SUB_RESOURCE_REF_RE = re.compile(r'^SubResource\("([^"]+)"\)$')
HEADER_ATTRIBUTE_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"')
INTEGER_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(
    r"^[+-]?(?:\d+\.\d*|\.\d+|\d+[eE][+-]?\d+|\d+\.\d*[eE][+-]?\d+)$"
)


def parse_value(raw_value: str) -> Any:
    """Convert a simple Godot value and preserve complex expressions."""
    value = raw_value.strip()
    if len(value) >= 3 and value.startswith('&"') and value.endswith('"'):
        try:
            return ast.literal_eval(value[1:])
        except (SyntaxError, ValueError):
            return value[2:-1]
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


def parse_section_header(line: str) -> tuple[str, dict[str, str]] | None:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return None
    section_type = stripped[1:-1].split(maxsplit=1)[0]
    return section_type, dict(HEADER_ATTRIBUTE_RE.findall(stripped))


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


def nest_theme_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """Turn ``Button/styles/normal`` keys into a browsable nested mapping."""
    nested: dict[str, Any] = {}
    for key, value in properties.items():
        target = nested
        parts = key.split("/")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return nested


def resolve_sub_resource(value: Any, sub_resources: dict[str, dict[str, Any]]) -> Any:
    if not isinstance(value, str):
        return value
    match = SUB_RESOURCE_REF_RE.fullmatch(value)
    if not match or match.group(1) not in sub_resources:
        return value
    resource = sub_resources[match.group(1)]
    return {"reference": value, **resource}


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
    current_properties: dict[str, Any] | None = None
    resource_properties: dict[str, Any] = {}
    sub_resources: dict[str, dict[str, Any]] = {}
    pending_key: str | None = None
    pending_parts: list[str] = []
    ext_resources: dict[str, dict[str, str]] = {}

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        ext_resource = parse_ext_resource_header(stripped)
        if ext_resource is not None:
            ext_resources[ext_resource["id"]] = ext_resource
        section = parse_section_header(stripped)
        if section is not None:
            section_type, attributes = section
            if section_type == "resource":
                current_properties = resource_properties
            elif section_type == "sub_resource" and "id" in attributes:
                sub_resource = {
                    "id": attributes["id"],
                    "type": attributes.get("type", ""),
                    "properties": {},
                }
                sub_resources[attributes["id"]] = sub_resource
                current_properties = sub_resource["properties"]
            else:
                current_properties = None
            continue
        if current_properties is None or not stripped or stripped.startswith(";"):
            continue

        if pending_key is not None:
            pending_parts.append(stripped)
            combined = "\n".join(pending_parts)
            if _is_complete_expression(combined):
                current_properties[pending_key] = resolve_texture_reference(
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
            current_properties[key] = resolve_texture_reference(
                parse_value(raw_value), ext_resources
            )
        else:
            pending_key = key
            pending_parts = [raw_value]

    if pending_key is not None:
        raise ValueError(f"Unclosed value in {path} for {pending_key!r}")
    resolved_properties = {
        key: resolve_sub_resource(value, sub_resources)
        for key, value in resource_properties.items()
    }
    result.update(resolved_properties)
    if sub_resources:
        result["_sub_resources"] = sub_resources
    if any("/" in key for key in resolved_properties):
        result["theme_types"] = nest_theme_properties(resolved_properties)
    return result


def iter_resource_files(source_root: Path) -> Iterable[Path]:
    return sorted(
        (
            path
            for path in source_root.rglob("*")
            if path.is_file() and path.suffix.casefold() in {".tres", ".res"}
        ),
        key=lambda path: path.relative_to(source_root).as_posix().casefold(),
    )


def to_snake_case(name: str) -> str:
    """Convert a Resources directory name such as CharacterProfiles to snake_case."""
    first_pass = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", first_pass).lower()


def output_path_for_resource(path: Path, source_root: Path, output_root: Path) -> Path:
    """Return a JSON path that mirrors the resource's relative directory."""
    relative = path.relative_to(source_root)
    directory_parts = [to_snake_case(part) for part in relative.parts[:-1]]
    filename = f"{to_snake_case(relative.stem)}.json"
    return output_root.joinpath(*directory_parts, filename)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse each Godot .tres/.res file below Resources into one JSON file."
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

    resource_files = list(iter_resource_files(source_root))
    expected_outputs: set[Path] = set()
    for path in resource_files:
        output_path = output_path_for_resource(path, source_root, args.output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(parse_tres(path), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        expected_outputs.add(output_path.resolve())
        print(f"{path.relative_to(source_root)} -> {output_path}")

    if args.output_dir.is_dir():
        for output_path in args.output_dir.rglob("*.json"):
            if output_path.resolve() not in expected_outputs:
                output_path.unlink()
                print(f"Removed stale JSON: {output_path}")
        for directory in sorted(args.output_dir.rglob("*"), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()

    print(f"Parsed {len(resource_files)} resource files into {len(expected_outputs)} JSON files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
