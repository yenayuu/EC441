"""CRC-16-CCITT demo for the EC 441 Week 09 lab.

Implements the CRC-16-CCITT-FALSE variant (poly=0x1021, init=0xFFFF, no
reflection, no final XOR) -- the same algorithm used by XMODEM, Bluetooth
HCI framing, and many embedded link layers.

The script:
  1. Computes a CRC for a sample frame.
  2. Appends it as a "trailer" and verifies that the receiver re-computes 0.
  3. Flips one random bit and shows that the corrupted frame fails the check.
  4. Sweeps every single-bit position to confirm 100% single-bit detection.

Usage:
    python crc_demo.py
"""

from __future__ import annotations

import random


POLY = 0x1021
INIT = 0xFFFF
WIDTH = 16
TOPBIT = 1 << (WIDTH - 1)
MASK = (1 << WIDTH) - 1


def crc16_ccitt(data: bytes, *, init: int = INIT) -> int:
    """Bitwise CRC-16-CCITT-FALSE. Slow but easy to read."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & TOPBIT:
                crc = ((crc << 1) ^ POLY) & MASK
            else:
                crc = (crc << 1) & MASK
    return crc


def append_crc(frame: bytes) -> bytes:
    """Return frame || CRC16 (big-endian), the way a link layer would."""
    crc = crc16_ccitt(frame)
    return frame + crc.to_bytes(2, "big")


def verify(frame_with_crc: bytes) -> bool:
    """Receiver-side check.

    Re-running CRC over (data || CRC) yields a known constant. For the
    CCITT-FALSE variant with no final XOR, the constant is 0 only when
    the CRC bytes are appended in big-endian order, which is what
    `append_crc` does.
    """
    payload, trailer = frame_with_crc[:-2], frame_with_crc[-2:]
    recomputed = crc16_ccitt(payload)
    received = int.from_bytes(trailer, "big")
    return recomputed == received


def flip_bit(frame: bytes, bit_index: int) -> bytes:
    """Flip a single bit (0-indexed from MSB of byte 0) and return new bytes."""
    byte_index, bit_in_byte = divmod(bit_index, 8)
    mutable = bytearray(frame)
    mutable[byte_index] ^= 1 << (7 - bit_in_byte)
    return bytes(mutable)


def sweep_single_bit_errors(frame_with_crc: bytes) -> tuple[int, int]:
    """Try every single-bit flip; return (detected, total)."""
    total = len(frame_with_crc) * 8
    detected = 0
    for i in range(total):
        if not verify(flip_bit(frame_with_crc, i)):
            detected += 1
    return detected, total


def main() -> None:
    random.seed(441)

    msg = b"Hello, EC441!"
    print(f"Original message ({len(msg)} bytes): {msg!r}")

    framed = append_crc(msg)
    crc_value = int.from_bytes(framed[-2:], "big")
    print(f"CRC-16-CCITT trailer:    0x{crc_value:04X}")
    print(f"Framed bytes (hex):      {framed.hex(' ')}")
    print()

    print("Receiver verifies clean frame:", verify(framed))

    flip_idx = random.randrange(len(framed) * 8)
    corrupted = flip_bit(framed, flip_idx)
    print(f"Flipped bit #{flip_idx} -> verify =", verify(corrupted))
    print()

    detected, total = sweep_single_bit_errors(framed)
    print(f"Single-bit error sweep:  {detected}/{total} flips detected "
          f"({100 * detected / total:.1f}%)")

    print("\nKey takeaway: a 16-bit CRC catches 100% of single-bit errors and")
    print("nearly all bursts shorter than 16 bits -- which is why every Ethernet")
    print("frame ends in a 32-bit FCS computed exactly this way.")


if __name__ == "__main__":
    main()
