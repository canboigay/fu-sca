import importlib
import pathlib
import sys

# Ensure project root is on path
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Basic smoke tests that modules import without executing scans

def test_import_core_modules():
    # Avoid importing heavy modules that require API deps (llm/utils/agent)
    modules = [
        'planner',
        'proxy',
        'parser',
        'scanner',
'tools',
    ]
    for m in modules:
        importlib.import_module(m)


def test_readme_exists():
    assert pathlib.Path('README.md').exists()