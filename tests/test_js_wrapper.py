import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import Tools


def test_wrap_js_no_change_for_arrow():
    t = Tools()
    code = "() => document.title"
    assert t._wrap_js_for_playwright(code) == code


def test_wrap_js_converts_return():
    t = Tools()
    code = "return document.title"
    wrapped = t._wrap_js_for_playwright(code)
    assert wrapped.startswith("() => ")
    assert "document.title" in wrapped


def test_wrap_js_simple_expression_kept():
    t = Tools()
    code = "document.title"
    assert t._wrap_js_for_playwright(code) == code


def test_safe_mode_blocks_mutations():
    t = Tools(safe=True)
    assert t.click(None, '#id').startswith('SAFE_MODE')
    assert t.fill(None, '#id', 'x').startswith('SAFE_MODE')
    assert t.submit(None, '#id').startswith('SAFE_MODE')
    assert t.python_interpreter('print("hi")').startswith('SAFE_MODE')
