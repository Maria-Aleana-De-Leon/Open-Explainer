"""User-facing errors. Every error says what went wrong and how to fix it."""


class OexError(Exception):
    def __init__(self, message: str, fix: str = ""):
        super().__init__(message)
        self.message = message
        self.fix = fix

    def __str__(self) -> str:
        return f"{self.message}\n  fix: {self.fix}" if self.fix else self.message


class ValidationError(OexError):
    """A project file does not match its schema. `problems` lists every issue found, not just the first."""

    def __init__(self, source: str, problems: list[str]):
        self.problems = problems
        body = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"{source}: {len(problems)} problem(s)\n{body}")
