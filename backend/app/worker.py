from app.db.init_db import init_db
from app.services.queue import run_worker_forever


def main() -> None:
    init_db()
    run_worker_forever()


if __name__ == "__main__":
    main()
