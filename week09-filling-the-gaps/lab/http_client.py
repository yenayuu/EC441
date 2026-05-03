"""Hand-rolled HTTP/1.1 client using only `socket` -- EC 441 Week 09 lab.

Pairs with `http_server.py`. The whole point is to show the request and
response on the wire as plain ASCII -- no `requests`, no `urllib`, no
hidden machinery. Run a packet capture (tcpdump/Wireshark) on the loopback
interface while invoking this and you can read the entire exchange.

Usage:
    python http_client.py                       # GETs /
    python http_client.py /hello                # GETs /hello
    python http_client.py /info --port 9000
    python http_client.py / --raw               # also print raw bytes
"""

from __future__ import annotations

import argparse
import socket
import sys


CLIENT_NAME = "EC441-LabClient/0.1"


def build_request(method: str, path: str, host: str) -> bytes:
    """Build a minimal HTTP/1.1 request. Note: CRLF, not LF."""
    return (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"User-Agent: {CLIENT_NAME}\r\n"
        f"Accept: */*\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("ascii")


def fetch(host: str, port: int, path: str, *, raw: bool = False) -> None:
    addr = (host, port)
    print(f"--> connecting to {host}:{port}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5.0)
        s.connect(addr)
        # On most systems the loopback "host" header should be the literal IP/
        # port the server bound to. Real browsers use the URL hostname.
        host_header = host if port in (80, 443) else f"{host}:{port}"
        request = build_request("GET", path, host_header)

        if raw:
            print("--- RAW REQUEST ---")
            sys.stdout.write(request.decode("ascii", errors="replace"))

        s.sendall(request)

        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
        response = b"".join(chunks)

    if raw:
        print("--- RAW RESPONSE ---")
        sys.stdout.write(response.decode("iso-8859-1", errors="replace"))
        sys.stdout.flush()
        print("--- END ---")
        return

    head, sep, body = response.partition(b"\r\n\r\n")
    if not sep:
        print("malformed response (no header/body separator)")
        sys.stdout.flush()
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return

    head_text = head.decode("iso-8859-1", errors="replace")
    print("--- response headers ---")
    print(head_text)
    print("--- response body ---")
    sys.stdout.flush()
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()
    if body and not body.endswith(b"\n"):
        print()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", nargs="?", default="/")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--raw", action="store_true",
                   help="show full request and response byte streams")
    args = p.parse_args()

    try:
        fetch(args.host, args.port, args.path, raw=args.raw)
    except ConnectionRefusedError:
        print(f"connection refused -- is http_server.py running on "
              f"{args.host}:{args.port}?", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
