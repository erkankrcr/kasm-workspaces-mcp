import kasm_mcp


def test_package_has_version():
    assert isinstance(kasm_mcp.__version__, str)
    assert kasm_mcp.__version__
