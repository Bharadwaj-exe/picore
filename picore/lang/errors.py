"""Errors raised while reading mathematical input."""


class ParseError(ValueError):
    """Input is not a math expression Pi Core understands.

    ``pos`` is the 0-based character index of the problem in the original text
    (when known), so the UI can point at it.
    """

    def __init__(self, message, pos=None):
        super().__init__(message)
        self.message = message
        self.pos = pos

    def __str__(self):
        if self.pos is None:
            return self.message
        return f"{self.message} (at character {self.pos + 1})"
