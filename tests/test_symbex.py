import pathlib
import pytest
import textwrap
from click.testing import CliRunner

from symbex.cli import cli


@pytest.fixture
def directory_full_of_code(tmpdir):
    for path, content in (
        ("foo.py", "def foo1():\n    pass\n\n@decorated\ndef foo2():\n    pass\n\n"),
        ("bar.py", "class BarClass:\n    pass\n\n"),
        ("nested/baz.py", "def baz():\n    pass\n\n"),
        ("nested/error.py", "def baz_error()" + "bug:\n    pass\n\n"),
        (
            "methods.py",
            textwrap.dedent(
                """
        class MyClass:
            def __init__(self, a):
                self.a = a

            def method1(self, a=1):
                pass
        """
            ),
        ),
    ):
        p = pathlib.Path(tmpdir / path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, "utf-8")
    return tmpdir


@pytest.mark.parametrize(
    "args,expected",
    (
        (["foo1", "--silent"], "# File: foo.py Line: 1\ndef foo1():\n    pass\n\n"),
        (
            ["foo*", "--silent"],
            "# File: foo.py Line: 1\ndef foo1():\n    pass\n\n# File: foo.py Line: 4\n@decorated\ndef foo2():\n    pass\n\n",
        ),
        (
            ["BarClass", "--silent"],
            "# File: bar.py Line: 1\nclass BarClass:\n    pass\n\n",
        ),
        (
            ["baz", "--silent"],
            "# File: nested/baz.py Line: 1\ndef baz():\n    pass\n\n",
        ),
        # The -f option
        (
            ["baz", "-f", "nested/baz.py", "--silent"],
            "# File: nested/baz.py Line: 1\ndef baz():\n    pass\n\n",
        ),
        # The -d option
        (
            ["baz", "-d", "nested", "--silent"],
            "# File: nested/baz.py Line: 1\ndef baz():\n    pass\n\n",
        ),
        # Classes
        (
            ["MyClass", "--silent"],
            "# File: methods.py Line: 2\n"
            "class MyClass:\n"
            "    def __init__(self, a):\n"
            "        self.a = a\n"
            "\n"
            "    def method1(self, a=1):\n"
            "        pass\n"
            "\n",
        ),
        (
            ["MyClass.__init__", "--silent"],
            "# File: methods.py Class: MyClass Line: 3\n"
            "    def __init__(self, a):\n"
            "        self.a = a\n"
            "\n",
        ),
        (
            ["MyClass.*", "--silent"],
            "# File: methods.py Class: MyClass Line: 3\n"
            "    def __init__(self, a):\n"
            "        self.a = a\n"
            "\n"
            "# File: methods.py Class: MyClass Line: 6\n"
            "    def method1(self, a=1):\n"
            "        pass\n"
            "\n",
        ),
        (
            ["*.method*", "--silent"],
            "# File: methods.py Class: MyClass Line: 6\n"
            "    def method1(self, a=1):\n"
            "        pass\n"
            "\n",
        ),
    ),
)
def test_fixture(directory_full_of_code, monkeypatch, args, expected):
    runner = CliRunner()
    monkeypatch.chdir(directory_full_of_code)
    result = runner.invoke(cli, args, catch_exceptions=False)
    assert result.exit_code == 0
    assert result.stdout == expected


@pytest.mark.parametrize(
    "args,expected",
    (
        (
            ["foo*", "--silent"],
            "# File: foo.py Line: 1\n"
            "def foo1()\n"
            "\n"
            "# File: foo.py Line: 5\n"
            "def foo2()",
        ),
        (["BarClass", "--silent"], "# File: bar.py Line: 1\n" "class BarClass"),
        (["baz", "--silent"], ("# File: nested/baz.py Line: 1\n" "def baz()")),
    ),
)
def test_symbex_symbols(directory_full_of_code, monkeypatch, args, expected):
    runner = CliRunner()
    monkeypatch.chdir(directory_full_of_code)
    result = runner.invoke(cli, args + ["-s"], catch_exceptions=False)
    assert result.exit_code == 0
    # Here expected is just the first two lines
    assert result.stdout.strip() == expected


def test_errors(directory_full_of_code, monkeypatch):
    # Test without --silent to see errors
    runner = CliRunner(mix_stderr=False)
    monkeypatch.chdir(directory_full_of_code)
    result = runner.invoke(cli, ["baz"], catch_exceptions=False)
    assert result.exit_code == 0
    assert result.stdout == (
        "# File: nested/baz.py Line: 1\n" "def baz():\n" "    pass\n\n"
    )
    # This differs between different Python versions
    assert result.stderr.startswith("# Syntax error in nested/error.py:")
