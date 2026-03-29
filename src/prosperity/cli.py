from __future__ import annotations

from pathlib import Path

import typer

from baselines.baseline_wrappers import list_baselines
from prosperity.backtester.datasets import discover_datasets, resolve_dataset_argument
from prosperity.backtester.runner import BacktesterRunner, BacktestRequest
from prosperity.backtester.smoke import smoke_baseline
from prosperity.db import DatabaseSession, ExperimentRepository
from prosperity.db.models import RunRecord
from prosperity.dsl.mutators import jitter_parameters
from prosperity.dsl.schema import StrategySpec
from prosperity.external.equirag_adapter import prepare_equirag_bundle
from prosperity.external.manual_submission import package_manual_submission
from prosperity.external.playwright_portal import dry_run_upload
from prosperity.generation.generator import generate_candidate_specs
from prosperity.logging import configure_logging
from prosperity.orchestration.jobs import (
    compile_spec_to_artifact,
    evaluate_compiled_strategy,
    ingest_all,
    persist_strategy_record,
)
from prosperity.orchestration.loop import run_loop_once
from prosperity.paths import RepoPaths
from prosperity.settings import load_settings
from prosperity.utils import json_dumps, utcnow_iso

app = typer.Typer(help="Local Prosperity research platform")
baselines_app = typer.Typer(help="Baseline commands")
backtest_app = typer.Typer(help="Backtester commands")
ideas_app = typer.Typer(help="Idea generation commands")
loop_app = typer.Typer(help="Loop commands")
submission_app = typer.Typer(help="Submission packaging commands")
dashboard_app = typer.Typer(help="Dashboard commands")
portal_app = typer.Typer(help="Portal adapter commands")

app.add_typer(baselines_app, name="baselines")
app.add_typer(backtest_app, name="backtest")
app.add_typer(ideas_app, name="ideas")
app.add_typer(loop_app, name="loop")
app.add_typer(submission_app, name="submission")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(portal_app, name="portal")


def _context():
    paths = RepoPaths.discover()
    settings = load_settings(paths)
    configure_logging(settings.log_level, paths.reports)
    return paths, settings


@app.command()
def audit() -> None:
    paths, settings = _context()
    summary = {
        "root": str(paths.root),
        "backtester": str(paths.backtester),
        "db_path": str(paths.db_dir / "prosperity.sqlite3"),
        "research_repos_present": paths.research_repos.exists(),
        "baseline_count": len(list_baselines()),
        "dataset_count": len(discover_datasets(paths)),
        "portal_mode": settings.portal.mode,
    }
    typer.echo(json_dumps(summary))


@app.command()
def ingest(target: str = "all") -> None:
    paths, settings = _context()
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        if target != "all":
            raise typer.BadParameter("Only 'all' is currently supported.")
        count = ingest_all(paths, settings, repo)
    typer.echo(json_dumps({"ingested_documents": count}))


@baselines_app.command("list")
def list_baselines_command() -> None:
    typer.echo(json_dumps({name: str(path) for name, path in list_baselines().items()}))


@baselines_app.command("run")
def run_baseline(name: str, dataset: str = "submission") -> None:
    paths, settings = _context()
    runner = BacktesterRunner(paths, settings)
    result = smoke_baseline(runner, baseline_name=name, dataset=dataset)
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        repo.insert_run(
            RunRecord(
                run_id=result.run_id,
                strategy_id=name,
                dataset_id=dataset,
                trader_path=result.request.trader_path,
                status="completed",
                final_pnl_total=result.summary.total_final_pnl,
                own_trade_count=sum(row.own_trades for row in result.summary.day_results),
                tick_count=sum(row.ticks for row in result.summary.day_results),
                summary_json=result.summary.model_dump_json(indent=2),
                stdout_path=str(paths.runs / result.run_id / "stdout.txt"),
                stderr_path=str(paths.runs / result.run_id / "stderr.txt"),
                created_at=result.created_at,
            )
        )
    typer.echo(result.summary.model_dump_json(indent=2))


@backtest_app.command("datasets")
def list_datasets() -> None:
    paths, _ = _context()
    typer.echo(json_dumps([dataset.model_dump() for dataset in discover_datasets(paths)]))


@backtest_app.command("run")
def run_backtest(
    trader: str,
    dataset: str = "tutorial",
    day: int | None = None,
    persist: bool = False,
) -> None:
    paths, settings = _context()
    runner = BacktesterRunner(paths, settings)
    result = runner.run(
        BacktestRequest(
            trader_path=str(Path(trader).resolve()),
            dataset=resolve_dataset_argument(dataset),
            day=day,
            persist=persist,
            products_mode=settings.backtester.default_products_mode,
        )
    )
    typer.echo(result.summary.model_dump_json(indent=2))


@ideas_app.command("generate")
def generate_ideas(count: int = 2) -> None:
    paths, _ = _context()
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        families = [row["family"] for row in repo.list_strategies()]
        specs = generate_candidate_specs(families, count=count)
    typer.echo(json_dumps([spec.model_dump(mode="json") for spec in specs]))


@ideas_app.command("mutate")
def mutate_idea(strategy_id: str) -> None:
    paths, _ = _context()
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        row = repo.get_strategy(strategy_id)
        if row is None:
            raise typer.BadParameter(f"Unknown strategy id: {strategy_id}")
        spec = StrategySpec.model_validate_json(row["spec_json"])
        mutated = jitter_parameters(spec)
    typer.echo(mutated.model_dump_json(indent=2))


@app.command()
def compile(strategy_id: str) -> None:
    paths, _ = _context()
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        row = repo.get_strategy(strategy_id)
        if row is None:
            raise typer.BadParameter(f"Unknown strategy id: {strategy_id}")
        spec = StrategySpec.model_validate_json(row["spec_json"])
        compiled_path = compile_spec_to_artifact(paths, spec)
        persist_strategy_record(repo, spec, compiled_path, stage="compiled", notes="CLI compile")
    typer.echo(json_dumps({"compiled_path": str(compiled_path)}))


@app.command()
def evaluate(strategy_id: str) -> None:
    paths, settings = _context()
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        row = repo.get_strategy(strategy_id)
        if row is None:
            raise typer.BadParameter(f"Unknown strategy id: {strategy_id}")
        spec = StrategySpec.model_validate_json(row["spec_json"])
        compiled_path = Path(row["code_path"])
        result = evaluate_compiled_strategy(paths, settings, repo, spec, compiled_path)
    typer.echo(json_dumps(result))


@submission_app.command("package")
def package_submission(strategy_id: str) -> None:
    paths, _ = _context()
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        row = repo.get_strategy(strategy_id)
        if row is None:
            raise typer.BadParameter(f"Unknown strategy id: {strategy_id}")
        spec = StrategySpec.model_validate_json(row["spec_json"])
        compiled_path = Path(row["code_path"])
        package_dir = package_manual_submission(
            paths.submissions,
            strategy_id,
            compiled_path,
            metadata=spec.model_dump(mode="json"),
            explanation=f"Manual packaging for {strategy_id} at {utcnow_iso()}",
        )
    typer.echo(json_dumps({"package_dir": str(package_dir)}))


@portal_app.command("dry-run")
def portal_dry_run(strategy_id: str) -> None:
    paths, _ = _context()
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        row = repo.get_strategy(strategy_id)
        if row is None:
            raise typer.BadParameter(f"Unknown strategy id: {strategy_id}")
        spec = StrategySpec.model_validate_json(row["spec_json"])
        compiled_path = Path(row["code_path"])
        package_dir = package_manual_submission(
            paths.submissions,
            strategy_id,
            compiled_path,
            metadata=spec.model_dump(mode="json"),
            explanation=f"Portal dry-run package for {strategy_id} at {utcnow_iso()}",
        )
    typer.echo(
        json_dumps(
            {
                "package_dir": str(package_dir),
                "playwright": dry_run_upload(package_dir),
                "equirag": prepare_equirag_bundle(package_dir, enabled=False),
            }
        )
    )


@loop_app.command("once")
def loop_once() -> None:
    typer.echo(json_dumps(run_loop_once()))


@loop_app.command("daemon")
def loop_daemon(sleep_seconds: int = 1800) -> None:
    from prosperity.orchestration.scheduler import run_daemon

    run_daemon(lambda: print(json_dumps(run_loop_once())), sleep_seconds)


@dashboard_app.command("serve")
def serve_dashboard() -> None:
    import subprocess
    import sys

    paths, _ = _context()
    script_path = paths.root / "scripts" / "serve_dashboard.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(script_path)], check=False)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
