"""Service resolution logic for mapping node labels to diagrams.aws classes.

Implements a two-tier resolution strategy:
  Tier 1 — Static mapping table lookup
  Tier 2 — Dynamic introspection of diagrams.aws submodules at runtime

Falls back to diagrams.aws.general.General when no match is found,
and handles ambiguous matches by selecting the first alphabetical class.
"""

import functools
import importlib
import inspect
import pkgutil
from typing import Callable, Optional, Type, Union

from app.api.models import WarningEntry
from app.mapper.normalizer import normalize_service_name, extract_service_candidates
from app.mapper.overrides import (
    is_image_reference,
    lookup_override,
    resolve_icon_path,
)
from app.mapper.static_map import STATIC_SERVICE_MAP


def _make_custom_icon_factory(icon_path: str) -> Callable:
    """Build a node factory that renders using a custom image icon.

    Returns a callable with the same call signature as a diagrams node
    class ( factory(label) -> node ), so the renderer can treat custom
    image nodes uniformly with regular diagrams classes. The callable wraps
    diagrams.custom.Custom, pre-binding the icon file path.

    Args:
        icon_path: Absolute path to the custom icon image file.

    Returns:
        A callable that accepts a label and returns a Custom node instance.
    """
    from diagrams.custom import Custom

    def _factory(label: str) -> Custom:
        return Custom(label, icon_path)

    # Preserve a readable name for logging/debugging.
    _factory.__name__ = "CustomIcon"
    return _factory


# Module-level cache for dynamically discovered diagrams.aws classes.
# Maps normalized class name -> list of (fully_qualified_name, class) tuples.
_dynamic_cache: Optional[dict[str, list[tuple[str, Type]]]] = None


def _build_dynamic_cache() -> dict[str, list[tuple[str, Type]]]:
    """Introspect all diagrams.aws submodules and build a lookup cache.

    Walks the diagrams.aws package tree, imports each submodule, and
    collects all public classes. Returns a mapping of normalized class
    names to lists of (fully_qualified_name, class) tuples.

    Returns:
        Dictionary mapping normalized names to candidate classes.
    """
    cache: dict[str, list[tuple[str, Type]]] = {}

    try:
        import diagrams.aws as aws_pkg
    except ImportError:
        return cache

    package_path = aws_pkg.__path__
    package_prefix = aws_pkg.__name__ + "."

    for importer, modname, ispkg in pkgutil.walk_packages(
        package_path, prefix=package_prefix
    ):
        try:
            module = importlib.import_module(modname)
        except (ImportError, Exception):
            continue

        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Only include classes defined in diagrams.aws submodules
            if not hasattr(obj, "__module__"):
                continue
            if not obj.__module__.startswith("diagrams.aws"):
                continue

            fqn = f"{obj.__module__}.{name}"
            normalized = normalize_service_name(name)

            if normalized not in cache:
                cache[normalized] = []

            # Avoid duplicates (same class imported in multiple places)
            existing_fqns = [entry[0] for entry in cache[normalized]]
            if fqn not in existing_fqns:
                cache[normalized].append((fqn, obj))

    return cache


def _get_dynamic_cache() -> dict[str, list[tuple[str, Type]]]:
    """Get or lazily initialize the dynamic class cache.

    Returns:
        The cached dictionary of normalized names to class candidates.
    """
    global _dynamic_cache
    if _dynamic_cache is None:
        _dynamic_cache = _build_dynamic_cache()
    return _dynamic_cache


def _import_class_from_path(import_path: str) -> Type:
    """Import a class given its fully-qualified dotted path.

    Args:
        import_path: Dotted path like 'diagrams.aws.compute.Lambda'.

    Returns:
        The class object.

    Raises:
        ImportError: If the module or class cannot be found.
        AttributeError: If the class doesn't exist in the module.
    """
    module_path, class_name = import_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _get_general_fallback() -> Type:
    """Import and return the diagrams.aws.general.General fallback class.

    Returns:
        The General class from diagrams.aws.general.
    """
    return _import_class_from_path("diagrams.aws.general.General")


def resolve_service(
    node_label: str,
) -> tuple[Optional[Type], Optional[WarningEntry]]:
    """Resolve a node label to a diagrams.aws class.

    Uses a layered strategy:
      0. Check the user-configured overrides file (highest precedence).
      1. Normalize the label and look up in the static service map
         (includes both AWS and non-AWS icons).
      2. If not found, search all diagrams.aws submodules dynamically.

    Handles three outcomes:
      - Exact match (1 result): returns (class, None)
      - Ambiguous match (2+ results): returns (first alphabetical, warning)
      - No match: returns (General fallback, warning)

    Args:
        node_label: The display label of the Mermaid node.

    Returns:
        A tuple of (resolved_class, warning).
        If resolved exactly: (class, None)
        If ambiguous: (first_alphabetical_class, warning_with_alternatives)
        If unresolved: (General_class, warning_with_reason)
    """
    # Generate candidate normalized names from the label
    candidates = extract_service_candidates(node_label)
    # Also include the simple full normalization
    normalized = normalize_service_name(node_label)
    if normalized not in candidates:
        candidates.append(normalized)

    # Tier 0: User-configured overrides take highest precedence
    override_value = lookup_override(node_label)
    if override_value:
        # Custom image icon reference
        if is_image_reference(override_value):
            icon_path = resolve_icon_path(override_value)
            if icon_path is not None:
                return (_make_custom_icon_factory(str(icon_path)), None)
            # Image file missing; fall through to normal resolution.
        else:
            # Dotted diagrams class path
            try:
                cls = _import_class_from_path(override_value)
                return (cls, None)
            except (ImportError, AttributeError, ValueError):
                # Invalid override path; fall through to normal resolution
                pass

    # Tier 1: Static map lookup - try each candidate
    for candidate in candidates:
        if candidate in STATIC_SERVICE_MAP:
            import_path = STATIC_SERVICE_MAP[candidate]
            try:
                cls = _import_class_from_path(import_path)
                return (cls, None)
            except (ImportError, AttributeError):
                pass

    # Tier 1 fallback: try the plain normalized form
    if normalized in STATIC_SERVICE_MAP:
        import_path = STATIC_SERVICE_MAP[normalized]
        try:
            cls = _import_class_from_path(import_path)
            return (cls, None)
        except (ImportError, AttributeError):
            # Static map entry is broken; fall through to dynamic resolution
            pass

    # Tier 2: Dynamic resolution via diagrams.aws introspection
    cache = _get_dynamic_cache()

    # Try each candidate against the dynamic cache
    for candidate in candidates:
        if candidate in cache:
            cache_entries = cache[candidate]
            if len(cache_entries) == 1:
                return (cache_entries[0][1], None)
            # Multiple matches - sort and pick first
            sorted_entries = sorted(cache_entries, key=lambda c: c[0])
            selected_fqn, selected_cls = sorted_entries[0]
            alternatives = [fqn for fqn, _ in sorted_entries[1:6]]
            warning = WarningEntry(
                node_label=node_label,
                reason="Ambiguous match: multiple AWS services match this label",
                selected_service=selected_fqn,
                alternatives=alternatives,
            )
            return (selected_cls, warning)

    # No match found — fallback to General
    fallback_cls = _get_general_fallback()
    warning = WarningEntry(
        node_label=node_label,
        reason="No matching AWS service found in diagrams.aws provider hierarchy",
        selected_service="diagrams.aws.general.General",
        alternatives=None,
    )
    return (fallback_cls, warning)


def clear_cache() -> None:
    """Clear the dynamic resolution cache.

    Useful for testing or when the diagrams package is updated at runtime.
    """
    global _dynamic_cache
    _dynamic_cache = None
