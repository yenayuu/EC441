"""Tiny HTTP/1.1 server using only `socket` -- EC 441 Week 09 lab.

The point is *not* to be a useful server. It is to make every byte of an
HTTP exchange visible at the syscall level so the client/server pattern,
the request line, the headers, and the response body are all naked on
the wire and easy to capture with `tcpdump` or Wireshark.

Routes:
  GET /           -> a small HTML page listing the other endpoints
  GET /hello      -> plain-text "Hello, EC441!"
  GET /info       -> JSON-style dump of request metadata
  anything else   -> 404 Not Found

Usage:
    python http_server.py                # listens on 127.0.0.1:8080
    python http_server.py --port 9000

In another terminal:
    python http_client.py /hello
    curl -v http://127.0.0.1:8080/

To capture for inspection (requires sudo on most systems):
    sudo tcpdump -i lo0 -w lab.pcap port 8080
"""

from __future__ import annotations

import argparse
import datetime
import socket
import sys


SERVER_NAME = "EC441-LabServer/0.1"


PAGES = {
    "/": (
        "text/html; charset=utf-8",
        b"""<!doctype html>
<html><head><title>EC441 Lab Server</title></head>
<body>
  <h1>EC441 Week 09 Lab Server</h1>
  <p>Available endpoints:</p>
  <ul>
    <li><a href="/hello">/hello</a> &mdash; plain text</li>
    <li><a href="/info">/info</a>   &mdash; JSON-ish request dump</li>
  </ul>
</body></html>
""",
    ),
    "/hello": ("text/plain; charset=utf-8", b"Hello, EC441!\n"),
}


def http_date() -> str:
    """RFC 7231 IMF-fixdate, e.g. 'Sun, 03 May 2026 20:00:00 GMT'."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )


def build_response(status: str, content_type: str, body: bytes) -> bytes:
    """Hand-build a minimal HTTP/1.1 response. CRLF line endings are required."""
    headers = (
        f"HTTP/1.1 {status}\r\n"
        f"Server: {SERVER_NAME}\r\n"
        f"Date: {http_date()}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode("ascii")
    return headers + body


def parse_request(raw: bytes) -> tuple[str, str, str, dict[str, str]]:
    """Return (method, path, version, headers) from a raw request."""
    head, _, _ = raw.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1", errors="replace").split("\r\n")
    if not lines or not lines[0]:
        raise ValueError("empty request")

    request_line = lines[0]
    parts = request_line.split()
    if len(parts) != 3:
        raise ValueError(f"bad request line: {request_line!r}")
    method, path, version = parts

    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
    return method, path, version, headers


def handle(conn: socket.socket, addr: tuple[str, int]) -> None:
    raw = b""
    conn.settimeout(2.0)
    try:
        while b"\r\n\r\n" not in raw:
            chunk = conn.recv(4096)
            if not chunk:
                break
            raw += chunk
            if len(raw) > 8192:   # cheap DoS guard for the demo
                break
    except socket.timeout:
        pass

    if not raw:
        conn.close()
        return

    try:
        method, path, version, headers = parse_request(raw)
    except ValueError as exc:
        body = f"400 Bad Request: {exc}\n".encode("utf-8")
        conn.sendall(build_response("400 Bad Request", "text/plain", body))
        conn.close()
        return

    print(f"{addr[0]}:{addr[1]} -> {method} {path} {version}  "
          f"Host={headers.get('host', '?')}  UA={headers.get('user-agent', '?')}")

    if method != "GET":
        body = b"Only GET is supported in this demo.\n"
        resp = build_response("405 Method Not Allowed", "text/plain", body)
    elif path in PAGES:
        ctype, body = PAGES[path]
        resp = build_response("200 OK", ctype, body)
    elif path == "/info":
        body = (
            "{\n"
            f"  \"client\":     \"{addr[0]}:{addr[1]}\",\n"
            f"  \"method\":     \"{method}\",\n"
            f"  \"path\":       \"{path}\",\n"
            f"  \"http_version\": \"{version}\",\n"
            f"  \"host_header\":  \"{headers.get('host', '')}\",\n"
            f"  \"user_agent\":   \"{headers.get('user-agent', '')}\"\n"
            "}\n"
        ).encode("utf-8")
        resp = build_response("200 OK", "application/json", body)
    else:
        body = f"404 Not Found: {path}\n".encode("utf-8")
        resp = build_response("404 Not Found", "text/plain", body)

    conn.sendall(resp)
    conn.close()


def serve(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(8)
        print(f"{SERVER_NAME} listening on http://{host}:{port}")
        print("Ctrl-C to stop.")
        try:
            while True:
                conn, addr = srv.accept()
                handle(conn, addr)
        except KeyboardInterrupt:
            print("\nshutting down")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args()
    try:
        serve(args.host, args.port)
    except OSError as exc:
        print(f"could not bind: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
