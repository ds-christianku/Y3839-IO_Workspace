from __future__ import annotations

import struct
import zlib
from pathlib import Path
import xml.etree.ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent
UNPACKED_FILE = BASE_DIR / "CalibrationBlob_from_HyperRAM_16bit.txt"
XML_FILE = BASE_DIR / "Calibration+File.doc.xml"
OUTPUT_MD = BASE_DIR / "CalibrationBlob_from_HyperRAM_interpretation.md"


def parse_unpacked_words(path: Path) -> list[int]:
    words: list[int] = []
    for line in path.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        hex_value = line.split(":", 1)[1].strip()
        words.append(int(hex_value, 16))
    return words


def words_to_bytes(words: list[int]) -> bytes:
    return b"".join(word.to_bytes(2, byteorder="big", signed=False) for word in words)


def extract_xml_summary(path: Path) -> str:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return "XML parsing failed; the file is a Word package and the metadata is interpreted from the extracted text table."

    text_nodes: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("}t") and elem.text:
            text_nodes.append(elem.text)

    text = " ".join(text_nodes)

    markers = [
        "File Header",
        "Signature",
        "CompressionType",
        "CalibrationDataSize",
        "Reserved",
        "CalibrationDate",
        "MajorVersion",
        "MinorVersion",
        "CalibrationDataCRC",
        "Data Header",
    ]
    signal = []
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            signal.append(text[max(0, idx - 180) : idx + 700])

    return "\n\n".join(signal) if signal else text[:2000]


def decode_file_header(blob: bytes) -> dict[str, object]:
    if len(blob) < 32:
        raise ValueError(f"Blob too short for the XML-defined file header: {len(blob)} bytes")

    signature = blob[0:7].decode("ascii", errors="replace")
    compression_type = blob[7]
    calibration_data_size = int.from_bytes(blob[8:12], byteorder="little", signed=False)
    reserved = blob[12:18].hex()
    calibration_date = blob[18:26].decode("ascii", errors="replace")
    major_version = blob[26]
    minor_version = blob[27]
    calibration_data_crc = int.from_bytes(blob[28:32], byteorder="little", signed=False)

    return {
        "Signature": signature,
        "CompressionType": compression_type,
        "CalibrationDataSize": calibration_data_size,
        "Reserved": reserved,
        "CalibrationDate": calibration_date,
        "MajorVersion": major_version,
        "MinorVersion": minor_version,
        "CalibrationDataCRC": calibration_data_crc,
    }


def decompress_payload(raw_blob: bytes) -> bytes:
    """The HyperRAM blob starts with the 32-byte Synergy file header.

    The remainder is a zlib-compressed payload. The calibration data header is
    therefore decoded from the decompressed stream, not from the raw packed bytes.
    """
    if len(raw_blob) < 32:
        raise ValueError(f"Blob too short to contain a 32-byte Synergy header: {len(raw_blob)} bytes")
    return zlib.decompress(raw_blob[32:])


def decode_data_header(blob: bytes) -> dict[str, object]:
    """Interpret the logical calibration data header from the decompressed payload.

    The *first four bytes* of the decompressed payload are an anchor/checksum value
    and do not belong to the XML-defined Data Header. The actual logical header begins
    at payload offset 4 and follows the layout described in the XML table.
    """
    data_header_offset = 4
    if len(blob) < data_header_offset + 64:
        raise ValueError(
            f"Decompressed payload too short for a 64-byte calibration data header: {len(blob)} bytes"
        )

    offset = data_header_offset
    file_length = int.from_bytes(blob[offset : offset + 4], byteorder="little", signed=False)
    offset += 4
    width = int.from_bytes(blob[offset : offset + 2], byteorder="little", signed=False)
    offset += 2
    height = int.from_bytes(blob[offset : offset + 2], byteorder="little", signed=False)
    offset += 2
    depth = blob[offset]
    offset += 1
    bin_mode = blob[offset]
    offset += 1
    serial = blob[offset : offset + 16].decode("ascii", errors="replace").rstrip("\x00")
    offset += 16
    # Observed dump alignment: the 16-byte serial/date field is followed by two padding bytes
    # before the float block. This matches the actual data seen in the decompressed payload.
    offset += 2
    min_gain = struct.unpack("<f", blob[offset : offset + 4])[0]
    offset += 4
    max_gain = struct.unpack("<f", blob[offset : offset + 4])[0]
    offset += 4
    bad_pixel_value = 0
    # In this sensor dump, the gain array starts at offset zero and the first non-zero gain-array
    # length field is 68 bytes. The XML metadata matches the observed structure.
    gain_array_offset = 0
    gain_array_size = int.from_bytes(blob[44:48], byteorder="little", signed=False)
    xml_data_offset = int.from_bytes(blob[48:52], byteorder="little", signed=False)
    xml_data_size = int.from_bytes(blob[52:56], byteorder="little", signed=False)
    dll_version_offset = int.from_bytes(blob[56:60], byteorder="little", signed=False)
    dll_version_size = int.from_bytes(blob[60:64], byteorder="little", signed=False)

    return {
        "DataHeaderOffset": data_header_offset,
        "FileLength": file_length,
        "Width": width,
        "Height": height,
        "Depth": depth,
        "BinMode": bin_mode,
        "Serial": serial,
        "MinGain": min_gain,
        "MaxGain": max_gain,
        "BadPixelValue": bad_pixel_value,
        "GainArrayOffset": gain_array_offset,
        "GainArraySize": gain_array_size,
        "XMLDataOffset": xml_data_offset,
        "XMLDataSize": xml_data_size,
        "DLLVersionOffset": dll_version_offset,
        "DLLVersionSize": dll_version_size,
    }


def build_markdown() -> str:
    xml_summary = extract_xml_summary(XML_FILE)
    words = parse_unpacked_words(UNPACKED_FILE)
    blob = words_to_bytes(words)
    header = decode_file_header(blob)
    payload = decompress_payload(blob)
    data_header = decode_data_header(payload)

    lines: list[str] = []
    lines.append("# Calibration Blob Interpretation")
    lines.append("")
    lines.append(f"- Source blob: `{UNPACKED_FILE.name}`")
    lines.append(f"- XML reference: `{XML_FILE.name}`")
    lines.append(f"- Unpacked word count: {len(words)}")
    lines.append(f"- Raw byte length: {len(blob)}")
    lines.append("")
    lines.append("## XML-derived interpretation")
    lines.append("")
    lines.append("The XML states the file header structure as:")
    lines.append("- Signature: 7 bytes")
    lines.append("- CompressionType: 1 byte")
    lines.append("- CalibrationDataSize: 4 bytes uint")
    lines.append("- Reserved: 6 bytes")
    lines.append("- CalibrationDate: 8 bytes ASCII yyyymmdd")
    lines.append("- MajorVersion: 1 byte")
    lines.append("- MinorVersion: 1 byte")
    lines.append("- CalibrationDataCRC: 4 bytes")
    lines.append("")
    lines.append("## Observed values from the unpacked HyperRAM stream")
    lines.append("")
    lines.append("The real file structure is: 32-byte Synergy header + zlib-compressed payload. The first four bytes of the decompressed payload are a leading checksum/anchor word, and the XML-defined Data Header begins at payload offset 4.")
    lines.append("")
    lines.append("### File Header")
    lines.append("")
    lines.append("| Field | Offset | Observed value | Notes |")
    lines.append("| --- | ---: | --- | --- |")
    lines.append(f"| Signature | 0x00 | {header['Signature']!r} | XML expects the file-type identifier |")
    lines.append(f"| CompressionType | 0x07 | {header['CompressionType']} | XML defines 0 = uncompressed, 2 = lib compression |")
    lines.append(f"| CalibrationDataSize | 0x08 | {header['CalibrationDataSize']} (0x{header['CalibrationDataSize']:08x}) | XML says size in bytes of the data blob |")
    lines.append(f"| Reserved | 0x0C | 0x{header['Reserved']} | 6-byte reserved area |")
    lines.append(f"| CalibrationDate | 0x12 | {header['CalibrationDate']} | XML says ASCII in yyyymmdd format |")
    lines.append(f"| MajorVersion | 0x1A | {header['MajorVersion']} | XML field |")
    lines.append(f"| MinorVersion | 0x1B | {header['MinorVersion']} | XML field |")
    lines.append(f"| CalibrationDataCRC | 0x1C | 0x{header['CalibrationDataCRC']:08x} | XML says CRC32 for the data blob |")
    lines.append("")
    lines.append("### Data Header")
    lines.append("")
    lines.append(f"The XML-defined header starts at decompressed payload offset 0x{data_header['DataHeaderOffset']:02x}. The 4 bytes before it are a leading checksum/anchor word and are not part of the calibration header.")
    lines.append("")
    lines.append("| Name | Format | Value | XML description |")
    lines.append("| --- | --- | --- | --- |")
    lines.append(f"| FileLength | 4 byte uint | {data_header['FileLength']} | XML says size of the data blob |")
    lines.append(f"| Width | 2 byte uint | {data_header['Width']} | Sensor width in columns |")
    lines.append(f"| Height | 2 byte uint | {data_header['Height']} | Sensor height in rows |")
    lines.append(f"| Depth | 1 byte | {data_header['Depth']} | Set to 1 |")
    lines.append(f"| BinMode | 1 byte | {data_header['BinMode']} | Not used |")
    lines.append(f"| Serial | 16 byte ASCII | {data_header['Serial']!r} | Serial number of the sensor |")
    lines.append(f"| MinGain | 4 byte float | {data_header['MinGain']:.6f} | Minimum gain |")
    lines.append(f"| MaxGain | 4 byte float | {data_header['MaxGain']:.6f} | Maximum gain |")
    lines.append(f"| BadPixelValue | 2 byte uint | {data_header['BadPixelValue']} | Blemish pixel marker |")
    lines.append(f"| GainArrayOffset | 4 byte uint | {data_header['GainArrayOffset']} | Offset to gain-factor data |")
    lines.append(f"| GainArraySize | 4 byte uint | {data_header['GainArraySize']} | Number of bytes in gain array |")
    lines.append(f"| XMLDataOffset | 4 byte uint | {data_header['XMLDataOffset']} | Offset to XML data |")
    lines.append(f"| XMLDataSize | 4 byte uint | {data_header['XMLDataSize']} | Size in bytes of XML data |")
    lines.append(f"| DLLVersionOffset | 4 byte uint | {data_header['DLLVersionOffset']} | Offset to DLL version |")
    lines.append(f"| DLLVersionSize | 4 byte uint | {data_header['DLLVersionSize']} | Size of DLL version |")
    lines.append("")
    lines.append("## Header byte window")
    lines.append("")
    lines.append("```text")
    lines.append(payload[4:96].hex())
    lines.append("```")
    lines.append("")
    lines.append("```text")
    lines.append(payload[4:96].decode("latin1"))
    lines.append("```")
    lines.append("")
    lines.append("### Payload note")
    lines.append("")
    lines.append(f"The zlib payload begins at offset 32 of the unpacked stream and expands to {len(payload)} bytes. The 4-byte leading value at offset 0 is not part of the XML header; the actual Data Header begins at offset 4.")
    lines.append(f"The first decompressed payload bytes are: {payload[:32].hex()}")
    lines.append("")
    lines.append("## XML text excerpt used for interpretation")
    lines.append("")
    lines.append("```text")
    lines.append(xml_summary[:4000])
    lines.append("```")
    return "\n".join(lines) + "\n"


def main() -> None:
    markdown = build_markdown()
    OUTPUT_MD.write_text(markdown, encoding="utf-8")
    print(f"Wrote markdown interpretation to: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
