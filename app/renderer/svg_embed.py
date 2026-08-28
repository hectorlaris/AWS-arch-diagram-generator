"""Post-processing to make rendered SVGs self-contained.

Graphviz emits SVG files that reference icon images by absolute file-system
path (e.g. an <image xlink:href="C:/.../resources/aws/.../s3.png"/> element).
Such SVGs only display icons while those PNG files remain at that exact path,
and browsers block local file references for security. This module rewrites
those references to embedded base64 data URIs so the SVG is fully portable
and renders icons anywhere.
"""

import base64
import mimetypes
import re
from pathlib import Path


# Matches the href attribute of an <image> element, capturing the path.
# Handles both xlink:href and plain href, single or double quotes.
_IMAGE_HREF_PATTERN = re.compile(
    r"(?P<attr>(?:xlink:)?href)=(?P<quote>[\"\'])(?P<path>[^\"\']+?)(?P=quote)"
)


def _to_data_uri(image_path: Path) -> str:
    """Encode an image file as a base64 data URI.

    Args:
        image_path: Path to the local image file.

    Returns:
        A data URI string, e.g. "data:image/png;base64,....".
    """
    mime, _ = mimetypes.guess_type(str(image_path))
    if mime is None:
        mime = "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def embed_svg_images(svg_path: Path) -> int:
    """Rewrite local image references in an SVG to embedded data URIs.

    Reads the SVG at svg_path, replaces every <image> href that points to an
    existing local file with a base64 data URI, and writes the result back.
    References that are already data URIs, remote URLs, or point to missing
    files are left unchanged.

    Args:
        svg_path: Path to the SVG file to process (modified in place).

    Returns:
        The number of image references that were embedded.
    """
    if not svg_path.exists():
        return 0

    content = svg_path.read_text(encoding="utf-8")
    embedded_count = 0

    def _replace(match: re.Match) -> str:
        nonlocal embedded_count
        raw_path = match.group("path")

        # Skip already-embedded or remote references
        if raw_path.startswith(("data:", "http://", "https://")):
            return match.group(0)

        # Normalize the referenced path (Graphviz may mix / and \ separators)
        candidate = Path(raw_path.replace("\\", "/"))
        if not candidate.exists() or not candidate.is_file():
            return match.group(0)

        try:
            data_uri = _to_data_uri(candidate)
        except OSError:
            return match.group(0)

        embedded_count += 1
        attr = match.group("attr")
        quote = match.group("quote")
        return f"{attr}={quote}{data_uri}{quote}"

    new_content = _IMAGE_HREF_PATTERN.sub(_replace, content)

    if embedded_count:
        svg_path.write_text(new_content, encoding="utf-8")

    return embedded_count
