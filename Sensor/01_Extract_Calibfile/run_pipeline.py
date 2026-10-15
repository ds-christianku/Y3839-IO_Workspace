import importlib.util
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PIPELINE_STEPS = [
    BASE_DIR / "01_extract_calibration_blob.py",
    BASE_DIR / "02_unpack_calibration_blob.py",
    BASE_DIR / "03_interpret_calibration_blob.py",
]
SIZE_MAP = {
    "size1": 1336 * 699 * 2,
}


def run_step(script_path: Path, *args: str) -> None:
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load script: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "main"):
        raise AttributeError(f"Script {script_path.name} does not define a main() function")

    print(f"\n=== Running {script_path.name} ===")
    module.main(*args)


def resolve_size(size_key: str) -> int:
    key = str(size_key).strip().lower()
    if key not in SIZE_MAP:
        if key in {"size0", "size2"}:
            raise ValueError(
                f"Size preset '{size_key}' is currently not allowed. "
                "Only 'size1' is valid for the current calibration block."
            )
        allowed = ", ".join(sorted(SIZE_MAP))
        raise ValueError(f"Unsupported size preset '{size_key}'. Allowed values: {allowed}")
    return SIZE_MAP[key]


def main(source_path: str | Path, size_key: str) -> int:
    source = Path(source_path)
    if not source.is_absolute():
        source = (BASE_DIR / source).resolve()

    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    size_key = str(size_key).strip().lower()
    calibration_length = resolve_size(size_key)

    for script_path in PIPELINE_STEPS:
        if not script_path.exists():
            raise FileNotFoundError(f"Pipeline step not found: {script_path}")

        if script_path.name == "01_extract_calibration_blob.py":
            run_step(script_path, str(source), size_key)
        else:
            run_step(script_path)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python run_pipeline.py <hyperram_dump.bin> <size0|size1|size2>")
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
