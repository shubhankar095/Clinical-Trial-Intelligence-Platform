import runpy
from unittest.mock import Mock

import config.config
import workers.extraction_worker

import main


def test_main_validates_config_and_runs_worker(
    monkeypatch,
):
    validate_mock = Mock()
    worker = Mock()
    worker_factory = Mock(
        return_value=worker
    )

    monkeypatch.setattr(
        main,
        "validate_runtime_config",
        validate_mock,
    )

    monkeypatch.setattr(
        main,
        "ExtractionWorker",
        worker_factory,
    )

    main.main()

    validate_mock.assert_called_once_with()
    worker_factory.assert_called_once_with()
    worker.run.assert_called_once_with()


def test_module_entry_point_runs_main(
    monkeypatch,
):
    monkeypatch.setenv(
        "CANONICAL_DOCUMENT_BUCKET",
        "canonical-bucket",
    )

    monkeypatch.setenv(
        "DOCUMENT_UPLOADED_QUEUE_URL",
        (
            "https://example.invalid/"
            "extraction-queue"
        ),
    )

    worker = Mock()

    worker_factory = Mock(
        return_value=worker
    )

    monkeypatch.setattr(
        workers.extraction_worker,
        "ExtractionWorker",
        worker_factory,
    )

    runpy.run_module(
        "main",
        run_name="__main__",
    )

    worker_factory.assert_called_once_with()
    worker.run.assert_called_once_with()