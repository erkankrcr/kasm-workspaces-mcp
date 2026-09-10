import pytest

from kasm_mcp.security.validation import SecurityError, validate_command, validate_path


@pytest.mark.parametrize(
    "command",
    [
        "cat /etc/passwd | grep root",
        "ls; rm -rf /",
        "echo a && echo b",
        "echo a || echo b",
        "echo `whoami`",
        "echo $(whoami)",
        "cat file >> out.txt",
        "cat file > out.txt",
        "cat < file",
        "cd ../../etc",
    ],
)
def test_validate_command_rejects_dangerous_patterns(command):
    with pytest.raises(SecurityError):
        validate_command(command)


@pytest.mark.parametrize(
    "command",
    ["nmap -sV 10.0.0.1", "whoami", "chromium https://example.com", "ls -la /home/kasm-user"],
)
def test_validate_command_allows_plain_commands(command):
    validate_command(command)  # must not raise


def test_validate_path_allows_within_root():
    validate_path("/home/kasm-user/results.txt", ["/home/kasm-user", "/tmp"])


def test_validate_path_rejects_outside_roots():
    with pytest.raises(SecurityError):
        validate_path("/etc/passwd", ["/home/kasm-user", "/tmp"])


def test_validate_path_rejects_traversal_even_if_prefix_matches():
    with pytest.raises(SecurityError):
        validate_path("/home/kasm-user/../../etc/passwd", ["/home/kasm-user"])
