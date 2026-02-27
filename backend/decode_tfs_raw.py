#!/usr/bin/env python3
"""
Step 1: Base64url decode the Google Flights tfs parameter
Step 2: Raw protobuf decode to identify field structure
"""
import base64
import struct
import sys

TFS_VALUE = (
    "CBwQAhooEgoyMDI2LTAzLTA5agwIAhIIL20vMGM4dGtyDAgDEggvbS8wOWMxNx"
    "ooEgoyMDI2LTAzLTIwagwIAxIIL20vMDljMTdyDAgCEggvbS8wYzh0a0ABSAFw"
    "AYIBCwj___________8BmAEB"
)

# ---------------------------------------------------------------------------
# Base64url decode
# ---------------------------------------------------------------------------
def b64url_decode(s: str) -> bytes:
    """Decode base64url (RFC 4648 section 5) with auto-padding."""
    s = s.replace("-", "+").replace("_", "/")
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.b64decode(s)


raw = b64url_decode(TFS_VALUE)

print("=== RAW BYTES (hex) ===")
for i in range(0, len(raw), 16):
    hexpart = " ".join(f"{b:02x}" for b in raw[i : i + 16])
    ascpart = "".join(chr(b) if 32 <= b < 127 else "." for b in raw[i : i + 16])
    print(f"  {i:04x}  {hexpart:<48s}  {ascpart}")
print(f"\nTotal bytes: {len(raw)}\n")

# ---------------------------------------------------------------------------
# Minimal protobuf varint / wire-type decoder
# ---------------------------------------------------------------------------

WIRE_VARINT = 0
WIRE_64BIT = 1
WIRE_LEN = 2
WIRE_SGROUP = 3
WIRE_EGROUP = 4
WIRE_32BIT = 5

WIRE_NAMES = {
    0: "varint",
    1: "64-bit",
    2: "length-delimited",
    3: "start group",
    4: "end group",
    5: "32-bit",
}


def decode_varint(buf: bytes, pos: int):
    result = 0
    shift = 0
    while True:
        b = buf[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if (b & 0x80) == 0:
            break
        shift += 7
    return result, pos


def decode_fields(buf: bytes, offset: int = 0, end: int | None = None, depth: int = 0):
    """Recursively decode protobuf fields."""
    if end is None:
        end = len(buf)
    indent = "  " * depth
    pos = offset
    while pos < end:
        tag, pos = decode_varint(buf, pos)
        field_number = tag >> 3
        wire_type = tag & 0x07
        wname = WIRE_NAMES.get(wire_type, f"unknown({wire_type})")

        if wire_type == WIRE_VARINT:
            value, pos = decode_varint(buf, pos)
            # Also show signed interpretation
            signed = (value >> 1) ^ -(value & 1)  # zigzag
            print(f"{indent}Field {field_number} [{wname}]: {value}  (zigzag={signed})")

        elif wire_type == WIRE_64BIT:
            value = buf[pos : pos + 8]
            pos += 8
            as_double = struct.unpack("<d", value)[0]
            as_fixed64 = struct.unpack("<Q", value)[0]
            print(f"{indent}Field {field_number} [{wname}]: fixed64={as_fixed64}  double={as_double}")

        elif wire_type == WIRE_LEN:
            length, pos = decode_varint(buf, pos)
            data = buf[pos : pos + length]
            pos += length

            # Try to interpret as UTF-8 string first
            try:
                text = data.decode("utf-8")
                if all(32 <= ord(c) < 127 or c in "\n\r\t" for c in text):
                    print(f"{indent}Field {field_number} [{wname}] (len={length}): \"{text}\"")
                else:
                    raise ValueError("not printable")
            except (UnicodeDecodeError, ValueError):
                # Try as nested protobuf message
                try:
                    print(f"{indent}Field {field_number} [{wname}] (len={length}): <message>")
                    decode_fields(data, 0, len(data), depth + 1)
                except Exception:
                    # Raw bytes
                    print(f"{indent}Field {field_number} [{wname}] (len={length}): {data.hex()}")

        elif wire_type == WIRE_32BIT:
            value = buf[pos : pos + 4]
            pos += 4
            as_float = struct.unpack("<f", value)[0]
            as_fixed32 = struct.unpack("<I", value)[0]
            print(f"{indent}Field {field_number} [{wname}]: fixed32={as_fixed32}  float={as_float}")

        elif wire_type == WIRE_SGROUP:
            print(f"{indent}Field {field_number} [start group]")

        elif wire_type == WIRE_EGROUP:
            print(f"{indent}Field {field_number} [end group]")

        else:
            print(f"{indent}Field {field_number} [wire={wire_type}]: UNKNOWN")
            break


print("=== PROTOBUF DECODE (raw) ===\n")
decode_fields(raw)
print()

# ---------------------------------------------------------------------------
# Also save the raw bytes to a .bin file for protoc --decode_raw
# ---------------------------------------------------------------------------
binpath = "/home/lostboi/aefoa/web-crawler/backend/tfs_decoded.bin"
with open(binpath, "wb") as f:
    f.write(raw)
print(f"Raw bytes written to {binpath}")
print("You can also run:  protoc --decode_raw < tfs_decoded.bin")
