"""Input validation shared by every tool that touches the Kasm session shell."""

from __future__ import annotations

import os

_DANGEROUS_COMMAND_PATTERNS = ("|", ";", "&&", "||", "`", "$(", "${", ">>", ">", "<", "..", "\n", "&")


class SecurityError(Exception):
    """Raised when a command or path fails a security check."""


def validate_command(command: str) -> None:
    """Reject commands using shell metacharacters or path-traversal tokens.

    Blocks two categories:
    - Shell chaining/injection metacharacters (|, ;, &&, ||, `, $(...), ${...},
      >>, >, <, newline, &) that enable command chaining or injection.
    - Path-traversal tokens (..) that could escape intended directories.

    This is deliberately conservative: callers needing pipelines must run
    a pre-written script file instead of relying on shell chaining here.
    """
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern in command:
            raise SecurityError(f"command contains disallowed pattern: {pattern!r}")


def validate_path(path: str, allowed_roots: list[str], operation: str = "access") -> None:
    """Reject a path that isn't (after resolving `..`) under one of allowed_roots."""
    normalized = os.path.normpath(path)
    if not os.path.isabs(normalized):
        raise SecurityError(f"path must be absolute for {operation}: {path!r}")
    for root in allowed_roots:
        root_norm = os.path.normpath(root)
        if normalized == root_norm or normalized.startswith(root_norm + os.sep):
            return
    raise SecurityError(f"path {path!r} is outside allowed roots {allowed_roots} for {operation}")
