"""Custom exceptions for the Diagram Renderer component."""


class RenderError(Exception):
    """Raised when Graphviz fails to produce diagram output.

    Attributes:
        cause: Description of the rendering failure.
    """

    def __init__(self, cause: str) -> None:
        """Initialize RenderError with a cause description.

        Args:
            cause: Description of the rendering failure.
        """
        self.cause = cause
        super().__init__(f"Rendering failed: {cause}")
