import runpy
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.unit


def fake_package(name):
    module = ModuleType(name)
    module.__path__ = []
    return module


def test_main_entry_and_callable_use_isolated_dependencies(monkeypatch):
    config_package = fake_package("config")
    config_module = ModuleType("config.config")
    config_module.validate_runtime_config = Mock()
    worker_package = fake_package("workers")
    worker_module = ModuleType("workers.ingestion_worker")
    worker = Mock()
    worker_module.IngestionWorker = Mock(return_value=worker)
    monkeypatch.setitem(sys.modules, "config", config_package)
    monkeypatch.setitem(sys.modules, "config.config", config_module)
    monkeypatch.setitem(sys.modules, "workers", worker_package)
    monkeypatch.setitem(sys.modules, "workers.ingestion_worker", worker_module)

    result = runpy.run_path("src/main.py", run_name="ingestion_entry")
    result["main"]()

    assert config_module.validate_runtime_config.call_count == 1
    worker.run.assert_called_once_with()

    config_module.validate_runtime_config.reset_mock()
    worker.run.reset_mock()
    runpy.run_path("src/main.py", run_name="__main__")

    config_module.validate_runtime_config.assert_called_once_with()
    worker.run.assert_called_once_with()
