from pathlib import Path
import os, json, yaml

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def resolve_dataset(name: str):
    """Return (db_path, meta_path) as Paths.
    Respects DATA_DIR env override; default 'data/' under project root.
    """
    root = project_root()
    reg = yaml.safe_load((root / "benchmark_bundle" / "registry.yaml").read_text(encoding="utf-8"))
    if name not in reg.get("datasets", {}):
        raise KeyError(f"dataset not in registry: {name}")
    entry = reg["datasets"][name]
    data_dir = Path(os.getenv("DATA_DIR", root / "data"))
    db_path = data_dir.parent / entry["path"] if str(entry["path"]).startswith("data/") else Path(entry["path"])
    meta_path = None
    if entry.get("meta"):
        meta_path = data_dir.parent / entry["meta"] if str(entry["meta"]).startswith("data/") else Path(entry["meta"])
    return db_path, meta_path
