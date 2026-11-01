from config.config import validate_runtime_config
from workers.ingestion_worker import IngestionWorker


def main() -> None:
    """Validate runtime configuration and start the Ingestion worker."""
    validate_runtime_config()
    IngestionWorker().run()


if __name__ == "__main__":
    main()
