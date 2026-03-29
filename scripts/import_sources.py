from prosperity.db import DatabaseSession, ExperimentRepository
from prosperity.orchestration.jobs import ingest_all
from prosperity.paths import RepoPaths
from prosperity.settings import load_settings


def main() -> None:
    paths = RepoPaths.discover()
    settings = load_settings(paths)
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        ingested = ingest_all(paths, settings, repo)
        print({"ingested_documents": ingested})


if __name__ == "__main__":
    main()
