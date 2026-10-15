from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "CalibrationBlob_from_HyperRAM.bin"
PACKED_OUTPUT = BASE_DIR / "CalibrationBlob_from_HyperRAM_12bits.txt"
UNPACKED_OUTPUT = BASE_DIR / "CalibrationBlob_from_HyperRAM_16bit.txt"
UNPACKED_BINARY_OUTPUT = BASE_DIR / "CalibrationBlob_from_HyperRAM_16bit.bin"
PACKED_MAGIC_WORDS = [0x0953, 0x06E7, 0x0265, 0x0677, 0x0279]
UNPACKED_MAGIC_WORDS = [0x5379, 0x6E65, 0x7267, 0x7902]


def depack_words(words):
    """Reconstruct the logical header sequence from the raw packed HyperRAM words.

    The observed stream is encoded as 16-bit little-endian words, where each word keeps
    a leading zero nibble that is stripped, the word order is reversed, and the final
    byte stream is then read backwards before regrouping as big-endian words.
    """
    compact = []
    for word in reversed(words):
        hex_word = f"{word:04x}"
        compact.append(hex_word[1:] if hex_word.startswith("0") else hex_word)

    compact_stream = "".join(compact)
    decoded_bytes = bytes.fromhex(compact_stream)
    reversed_bytes = decoded_bytes[::-1]

    unpacked_words = [
        int.from_bytes(reversed_bytes[i : i + 2], byteorder="big", signed=False)
        for i in range(0, len(reversed_bytes), 2)
        if len(reversed_bytes[i : i + 2]) == 2
    ]
    return unpacked_words


def words_to_bytes(words):
    return b"".join(word.to_bytes(2, byteorder="big", signed=False) for word in words)


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Source file not found: {SOURCE}")

    data = SOURCE.read_bytes()
    if len(data) % 2 != 0:
        raise ValueError(
            f"The source blob has an odd number of bytes ({len(data)}), "
            "so it cannot be split into 16-bit words exactly."
        )

    packed_words = [int.from_bytes(data[i : i + 2], byteorder="little", signed=False) for i in range(0, len(data), 2)]
    packed_hex = [f"{word:04x}" for word in packed_words]
    packed_lines = [f"{index:06d}: {word_hex}" for index, word_hex in enumerate(packed_hex, start=1)]
    PACKED_OUTPUT.write_text("\n".join(packed_lines) + "\n", encoding="ascii")

    unpacked_words = depack_words(packed_words)
    unpacked_hex = [f"{word:04x}" for word in unpacked_words]
    unpacked_lines = [f"{index:06d}: {word_hex}" for index, word_hex in enumerate(unpacked_hex, start=1)]
    UNPACKED_OUTPUT.write_text("\n".join(unpacked_lines) + "\n", encoding="ascii")
    UNPACKED_BINARY_OUTPUT.write_bytes(words_to_bytes(unpacked_words))

    print(f"Source file: {SOURCE}")
    print(f"Packed input bytes: {len(data)}")
    print(f"Packed word count: {len(packed_words)}")
    print(f"Packed output file: {PACKED_OUTPUT}")
    print(f"Unpacked word count: {len(unpacked_words)}")
    print(f"Unpacked output file: {UNPACKED_OUTPUT}")
    print(f"Unpacked binary output file: {UNPACKED_BINARY_OUTPUT}")


if __name__ == "__main__":
    main()
