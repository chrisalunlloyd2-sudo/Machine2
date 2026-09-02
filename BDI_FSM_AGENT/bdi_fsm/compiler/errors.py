"""Compilation error — raised at any pipeline stage with position info."""


class CompileError(Exception):
    """A front/middle/back-end failure. Carries an optional line/col."""
    def __init__(self, message, line=None, col=None):
        super().__init__(message)
        self.line = line
        self.col = col
        self.message = message
