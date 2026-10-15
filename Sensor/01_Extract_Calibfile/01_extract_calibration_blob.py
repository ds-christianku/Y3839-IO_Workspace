import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OFFSET = 16_777_216
OUTPUT = BASE_DIR / "CalibrationBlob_from_HyperRAM.bin"
SIZE_MAP = {
    "size1": 1336 * 699 * 2,
}


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


def main(source_path: str | Path, size_key: str) -> None:
    source = Path(source_path)
    if not source.is_absolute():
        source = (BASE_DIR / source).resolve()

    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    calibration_length = resolve_size(size_key)
    raw = source.read_bytes()
    if OFFSET >= len(raw):
        raise ValueError(
            f"Offset {OFFSET} exceeds file size {len(raw)} bytes. "
            "The calibration block is not present at this location."
        )

    end = OFFSET + calibration_length
    if end > len(raw):
        raise ValueError(
            f"Requested calibration length {calibration_length} bytes exceeds "
            f"available data from offset {OFFSET} to file end {len(raw)} bytes."
        )

    blob = raw[OFFSET:end]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(blob)

    print(f"Source file: {source}")
    print(f"Source size: {len(raw)} bytes")
    print(f"Offset: {OFFSET} bytes")
    print(f"Calibration length: {calibration_length} bytes")
    print(f"Extracted blob size: {len(blob)} bytes")
    print(f"Output file: {OUTPUT}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python 01_extract_calibration_blob.py <hyperram_dump.bin> <size0|size1|size2>")
    main(sys.argv[1], sys.argv[2])
