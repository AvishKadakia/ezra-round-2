from app.db.init_db import init_db
from app.services.queue import run_failed_storage_repair_once, run_recovery_once


def main() -> None:
    init_db()
    recovered = run_recovery_once()
    requeued = run_failed_storage_repair_once()
    print(f"Recovered {recovered} stale processing job/artifact record(s).")
    print(f"Requeued {requeued} failed storage-download artifact(s).")


if __name__ == "__main__":
    main()
