import importlib.util
from pathlib import Path


def load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_benchmark_scripts_can_be_imported():
    repo_root = Path(__file__).resolve().parents[1]
    for rel_path in ["tests/benchmark_performance.py", "tests/performance_benchmark.py"]:
        module = load_module_from_path(repo_root / rel_path)
        assert module is not None
