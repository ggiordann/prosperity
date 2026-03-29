from prosperity.dashboard.app import run_dashboard
from prosperity.paths import RepoPaths

paths = RepoPaths.discover()
run_dashboard(paths.db_dir / "prosperity.sqlite3", paths.submissions)
