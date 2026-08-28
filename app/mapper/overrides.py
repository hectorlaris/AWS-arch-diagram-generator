"""User-configurable label-to-icon override mapping.

Overrides let the user pin specific node labels to exact diagrams classes,
taking precedence over the static and dynamic resolution tiers. This is the
recommended way to handle nodes that are not AWS services (process/flow
concepts, third-party tools, or ambiguous labels) without risking false
positives from automatic matching.

The overrides file is an optional JSON document mapping node labels to
fully-qualified diagrams class paths, for example:

    {
      "Manual Approval": "diagrams.programming.flowchart.Decision",
      "Source": "diagrams.programming.flowchart.StartEnd",
      "Pipeline stopped": "diagrams.programming.flowchart.StartEnd",
      "DevOps Email": "diagrams.aws.engagement.SimpleEmailServiceSesEmail"
    }

Lookup is attempted first by exact label, then by a normalized (lowercased,
delimiter-stripped) form so minor formatting differences still match.
"""

import importlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.mapper.normalizer import normalize_service_name


logger = logging.getLogger(__name__)


# Default location: overrides.json in the current working directory.
# Can be overridden via the DIAGRAM_OVERRIDES_PATH environment variable.
_DEFAULT_OVERRIDES_FILENAME = "overrides.json"

# Directory holding user-provided custom icon images. Overridable via the
# DIAGRAM_ICONS_DIR environment variable.
_DEFAULT_ICONS_DIRNAME = "assets/icons"

# Recognized image file extensions for custom icons.
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".gif", ".bmp")

# Cache: maps override file path -> loaded dict (raw + normalized keys).
_overrides_cache: Optional[Dict[str, str]] = None
_cached_path: Optional[str] = None


def _resolve_overrides_path() -> Path:
    """Determine the path to the overrides JSON file.

    Returns:
        Path to the overrides file (may not exist).
    """
    env_path = os.environ.get("DIAGRAM_OVERRIDES_PATH")
    if env_path:
        return Path(env_path)
    return Path.cwd() / _DEFAULT_OVERRIDES_FILENAME


def _resolve_icons_dir() -> Path:
    """Determine the directory that holds custom icon images.

    Returns:
        Path to the icons directory (may not exist).
    """
    env_dir = os.environ.get("DIAGRAM_ICONS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.cwd() / _DEFAULT_ICONS_DIRNAME


def is_image_reference(value: str) -> bool:
    """Return True if an override value refers to a custom image file.

    A value is treated as an image if it ends with a known image extension
    (case-insensitive). Otherwise it is treated as a dotted diagrams class
    path.

    Args:
        value: The override value from the JSON file.

    Returns:
        True if the value should be resolved as a custom image icon.
    """
    return value.lower().endswith(_IMAGE_EXTENSIONS)


def resolve_icon_path(value: str) -> Optional[Path]:
    """Resolve an override image value to an absolute icon file path.

    The value is interpreted as a filename relative to the icons directory
    (assets/icons by default). Absolute paths and paths containing directory
    separators are honored as-is for flexibility.

    Args:
        value: The image reference from the overrides file.

    Returns:
        The resolved Path if the image file exists, otherwise None.
    """
    candidate = Path(value)

    # Absolute path or a path with its own directory components: use as-is.
    if candidate.is_absolute() or candidate.parent != Path("."):
        resolved = candidate
    else:
        # Bare filename: look inside the icons directory.
        resolved = _resolve_icons_dir() / candidate

    if resolved.exists() and resolved.is_file():
        return resolved
    return None


def load_overrides() -> Dict[str, str]:
    """Load the override mapping from disk, with caching.

    Reads the overrides JSON file if present and builds a lookup dict that
    includes both the raw labels and their normalized forms as keys. Returns
    an empty dict if the file is missing or invalid.

    Returns:
        Dictionary mapping labels (raw and normalized) to import paths.
    """
    global _overrides_cache, _cached_path

    path = _resolve_overrides_path()
    path_str = str(path)

    # Return cache if the path has not changed and cache is populated
    if _overrides_cache is not None and _cached_path == path_str:
        return _overrides_cache

    result: Dict[str, str] = {}

    if path.exists() and path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}

        if isinstance(raw, dict):
            for label, import_path in raw.items():
                if not isinstance(label, str) or not isinstance(import_path, str):
                    logger.warning(
                        "Ignoring overrides entry with non-string key/value: "
                        "%r -> %r",
                        label,
                        import_path,
                    )
                    continue
                # Store both the exact label and its normalized form
                result[label] = import_path
                normalized = normalize_service_name(label)
                if normalized and normalized not in result:
                    result[normalized] = import_path

            # Validate that each configured path resolves to a real class,
            # warning about any that do not so typos surface immediately.
            invalid = validate_overrides(raw)
            for bad_label, bad_path, reason in invalid:
                logger.warning(
                    "Overrides entry %r -> %r is invalid (%s); this node "
                    "will fall back to the generic icon.",
                    bad_label,
                    bad_path,
                    reason,
                )

    _overrides_cache = result
    _cached_path = path_str
    return result


def validate_overrides(
    raw: Dict[str, str],
) -> List[Tuple[str, str, str]]:
    """Check that each override path points to an importable class.

    Args:
        raw: The raw label -> import path mapping loaded from JSON.

    Returns:
        A list of (label, import_path, reason) tuples for entries whose
        path could not be resolved to a real diagrams class. An empty list
        means every entry is valid.
    """
    problems: List[Tuple[str, str, str]] = []

    for label, value in raw.items():
        if not isinstance(label, str) or not isinstance(value, str):
            continue

        # Custom image reference: validate the file exists.
        if is_image_reference(value):
            if resolve_icon_path(value) is None:
                problems.append(
                    (label, value, "custom icon image file not found")
                )
            continue

        # Otherwise treat as a dotted diagrams class path.
        if "." not in value:
            problems.append((label, value, "not a dotted class path"))
            continue

        module_path, class_name = value.rsplit(".", 1)
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            problems.append(
                (label, value, f"module '{module_path}' not found")
            )
            continue

        if not hasattr(module, class_name):
            problems.append(
                (label, value, f"class '{class_name}' not found")
            )

    return problems


def lookup_override(node_label: str) -> Optional[str]:
    """Look up an override import path for a node label.

    Tries an exact label match first, then a normalized match.

    Args:
        node_label: The display label of the Mermaid node.

    Returns:
        The fully-qualified diagrams class path if an override exists,
        otherwise None.
    """
    overrides = load_overrides()
    if not overrides:
        return None

    # Exact match
    if node_label in overrides:
        return overrides[node_label]

    # Normalized match
    normalized = normalize_service_name(node_label)
    return overrides.get(normalized)


def clear_overrides_cache() -> None:
    """Clear the cached overrides mapping.

    Useful for testing or after the overrides file is modified at runtime.
    """
    global _overrides_cache, _cached_path
    _overrides_cache = None
    _cached_path = None
