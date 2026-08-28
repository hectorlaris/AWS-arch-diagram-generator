"""Custom exceptions for the Mermaid parser component."""


class MermaidSyntaxError(Exception):
    """Raised when the Mermaid input contains invalid syntax.

    Attributes:
        line: Approximate line number of the error.
        column: Approximate column position.
        detail: Description of the syntax issue.
    """

    def __init__(self, line: int, column: int, detail: str) -> None:
        """Initialize MermaidSyntaxError with location and description.

        Args:
            line: Approximate line number of the error.
            column: Approximate column position.
            detail: Description of the syntax issue.
        """
        self.line = line
        self.column = column
        self.detail = detail
        super().__init__(
            f"Syntax error at line {line}, col {column}: {detail}"
        )
