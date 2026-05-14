"""Tests for AST-based code validation."""


def test_accepts_function_def(app_module):
    assert app_module._validate_code("def f(x): return x") is None


def test_accepts_class_def(app_module):
    assert app_module._validate_code("class A:\n    pass") is None


def test_accepts_imports_and_assignments(app_module):
    code = "import torch\nfrom torch import nn\nA = 1\n"
    assert app_module._validate_code(code) is None


def test_rejects_top_level_for(app_module):
    err = app_module._validate_code("for i in range(3):\n    pass")
    assert err is not None and "For" in err


def test_rejects_top_level_if(app_module):
    err = app_module._validate_code("if True:\n    pass")
    assert err is not None and "If" in err


def test_rejects_top_level_while(app_module):
    err = app_module._validate_code("while True:\n    pass")
    assert err is not None and "While" in err


def test_reports_syntax_error(app_module):
    err = app_module._validate_code("def f(:\n    pass")
    assert err is not None and "Syntax error" in err
