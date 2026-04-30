from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = ROOT / "backend" / "storage"
RAW_ROOT = STORAGE_ROOT / "raw"


def remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def main() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    remove_if_exists(STORAGE_ROOT / "ims.db")
    remove_if_exists(STORAGE_ROOT / "ims.db-shm")
    remove_if_exists(STORAGE_ROOT / "ims.db-wal")

    for raw_file in RAW_ROOT.glob("*.jsonl"):
        raw_file.unlink()

    print("Demo state reset. The next app start begins with an empty incident store.")


if __name__ == "__main__":
    main()
