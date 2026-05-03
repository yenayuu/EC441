# Week 09 Lab — Three Tiny Programs, Three Topics

**Course:** EC 441 — Spring 2026
**Type:** Lab
**Companion report:** [`../filling_the_gaps_report.md`](../filling_the_gaps_report.md)

This lab is intentionally minimal. Each script is short enough to read in one
sitting, runs on plain Python 3 (standard library only — no `pip install`
needed), and demonstrates exactly one concept from the report.

| Script | Topic from report | What it shows |
|---|---|---|
| `crc_demo.py` | §3 Link layer | CRC-16-CCITT detects 100% of single-bit errors |
| `stop_and_wait.py` | §6 Reliable data transfer | rdt 3.0 over a lossy channel; throughput collapses with loss |
| `http_server.py` + `http_client.py` | §8 Apps + §9 Web | Hand-built HTTP/1.1 client/server visible byte-for-byte on the wire |

---

## Requirements

- Python 3.9+ (uses `dataclasses`, type hints, `random.Random`)
- Nothing else. No `pip install`.

Optional, for cross-checking with the Week 07 observability tools:

- `tcpdump` (preinstalled on macOS/Linux)
- Wireshark (any recent version)
- `curl` (any version)

---

## 1. CRC-16 demo

```bash
python3 crc_demo.py
```

Expected output (deterministic — seeded with `441`):

```
Original message (13 bytes): b'Hello, EC441!'
CRC-16-CCITT trailer:    0x3AA1
Framed bytes (hex):      48 65 6c 6c 6f 2c 20 45 43 34 34 31 21 3a a1

Receiver verifies clean frame: True
Flipped bit #22 -> verify = False

Single-bit error sweep:  120/120 flips detected (100.0%)
```

**What to look at**

- The CRC-16 trailer `3A A1` is computed from the polynomial `0x1021`.
- Flipping any one bit anywhere in the 15-byte framed message — header *or*
  trailer — is detected by the receiver.
- The same construction is what gives every Ethernet frame its trailing
  CRC-32 FCS. A 32-bit CRC catches even more bursts.

---

## 2. Stop-and-Wait reliable transfer

```bash
python3 stop_and_wait.py                         # default: 30 packets, 20% loss
python3 stop_and_wait.py --loss 0.0 --quiet      # no-loss baseline
python3 stop_and_wait.py --loss 0.5 --packets 20 # heavy loss
```

Sample output (excerpt):

```
[pkt   0] seq=0 attempt=1 DATA lost  -> timeout, retransmit
[pkt   0] seq=0 attempt=2 delivered (RTT ~10 ms)
[pkt   1] seq=1 attempt=1 delivered (RTT ~10 ms)
...
--- Stop-and-Wait summary (loss=30%, n=8) ---
Packets delivered:           8
Total transmissions:         16
Wall-clock elapsed:          0.40 s
Effective throughput:        19.8 pkts/s
Channel efficiency:          50%
```

**What to look at**

- Compare the throughput at `--loss 0.0` vs `--loss 0.3` vs `--loss 0.5`.
  The pipe is empty for one full timeout per dropped packet — the exact
  motivation for sliding-window protocols (GBN, SR) discussed in the report.
- The 1-bit "alternating-bit" sequence number is enough to disambiguate a
  retransmission from a fresh packet.
- Try implementing GBN as an extension: keep a window of size `N`, ACK
  cumulatively, and retransmit the whole window on timeout.

---

## 3. HTTP client + server

Open **two terminals**.

**Terminal A — start the server:**

```bash
python3 http_server.py
# EC441-LabServer/0.1 listening on http://127.0.0.1:8080
```

**Terminal B — talk to it:**

```bash
python3 http_client.py            # GETs /
python3 http_client.py /hello
python3 http_client.py /info
python3 http_client.py /missing   # 404
python3 http_client.py /info --raw   # show full request + response on the wire
```

You can also use real-world clients to confirm interop:

```bash
curl -v http://127.0.0.1:8080/hello
curl -i http://127.0.0.1:8080/info
```

The browser also works: open <http://127.0.0.1:8080/> while the server is
running.

**What to look at**

- `--raw` prints the literal bytes the client and server exchange. Notice
  that every line ends in `\r\n` (CRLF) and the headers are separated from
  the body by a blank line — the HTTP/1.1 wire format is just plain ASCII.
- The server logs each request with the client's IP, port, method, path,
  and User-Agent — the same metadata that shows up in every real web log
  (Apache/Nginx access logs, Cloudflare, etc.).
- The `Connection: close` header forces the server to close the socket after
  one response. HTTP/1.1's default is keep-alive; turning it on would let
  the client pipeline multiple requests on one TCP connection.

### Cross-check with `tcpdump` (Week 07 callback)

While the server is running, in a third terminal:

```bash
sudo tcpdump -i lo0 -A -s0 -nn 'tcp port 8080'
```

(On Linux substitute `lo` for `lo0`.)

Then run a `python3 http_client.py /hello` from terminal B. You'll see the
TCP three-way handshake (SYN, SYN-ACK, ACK), the request bytes (in ASCII
thanks to `-A`), the response bytes, and the connection close — the same
sequence Wireshark would show in its TCP-stream view.

This is the moment the entire stack lines up: physical/link delivery on the
loopback, IP addressing on `127.0.0.1`, TCP reliable transport, and HTTP at
the top. The lab is small, but it touches every layer in the syllabus.

---

## Suggested extensions

- **GBN/SR variant:** add a `--window N` flag to `stop_and_wait.py`.
- **HTTPS variant:** wrap the server socket with `ssl.wrap_socket` and a
  self-signed cert; observe TLS records in Wireshark (Week 08 connection).
- **P2P variant:** turn `http_server.py` into a UDP "peer" that maintains a
  list of other peers and broadcasts new messages — the application-layer
  half of §8.
- **CRC-32 / Ethernet FCS:** replace `POLY = 0x1021` with `0x04C11DB7` and
  the proper bit-reflection to match what `ethtool -K` reports.
