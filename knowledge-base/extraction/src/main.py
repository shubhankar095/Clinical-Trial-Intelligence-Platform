from workers.extraction_worker import ExtractionWorker
from config.config import validate_runtime_config
def main() -> None:

    validate_runtime_config()

    worker = ExtractionWorker()

    worker.run()


if __name__ == "__main__":
    main()