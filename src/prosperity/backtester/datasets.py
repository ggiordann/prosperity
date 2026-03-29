from __future__ import annotations

from pydantic import BaseModel

from prosperity.paths import RepoPaths
from prosperity.utils import sha256_file


class DatasetInfo(BaseModel):
    dataset_id: str
    path: str
    source: str
    kind: str
    round_name: str
    day: int | None = None
    hash: str | None = None


def discover_datasets(paths: RepoPaths) -> list[DatasetInfo]:
    datasets: list[DatasetInfo] = []

    for csv_path in sorted((paths.root / "imcdata").glob("*.csv")):
        datasets.append(
            DatasetInfo(
                dataset_id=csv_path.stem,
                path=str(csv_path),
                source="repo_imcdata",
                kind="csv",
                round_name="tutorial",
                hash=sha256_file(csv_path),
            )
        )

    dataset_root = paths.backtester / "datasets"
    if dataset_root.exists():
        for path in sorted(dataset_root.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix.lower() not in {".csv", ".log", ".json"}:
                continue
            round_name = path.parent.name
            datasets.append(
                DatasetInfo(
                    dataset_id=f"{round_name}:{path.stem}",
                    path=str(path),
                    source="rust_backtester",
                    kind=path.suffix.lower().lstrip("."),
                    round_name=round_name,
                    hash=sha256_file(path),
                )
            )
    return datasets


def resolve_dataset_argument(dataset_name: str) -> str:
    aliases = {
        "submission": "datasets/tutorial/submission.log",
        "tutorial": "tutorial",
        "latest": "latest",
    }
    return aliases.get(dataset_name, dataset_name)
