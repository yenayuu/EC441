# Week 09 — Filling the Gaps: Information, Link Layer, Wireless, Reliable Transfer, Addressing, and the Web

**Course:** EC 441 — Introduction to Computer Networking, Boston University, Spring 2026

**Type:** Report + Lab

**Source:** Course material across the semester — topics not yet covered in Weeks 01–08

---

## 1. Introduction

The previous eight weeks moved bottom-up through the stack: physical signaling, Ethernet/ARP, IP and routing, BGP, TCP, observability tools, and a security capstone. A handful of foundational and application-layer topics from the syllabus were not yet given their own report. This week consolidates those gaps in a single artifact and grounds them in a small hands-on lab.

The topics covered here are:

1. **Information** — sources and representation.
2. **Link layer** — frames, error detection, CRC.
3. **Multiple access** — ALOHA and CSMA family.
4. **Wireless networks** — IEEE 802.11.
5. **Reliable data transfer** — Stop-and-Wait, Go-Back-N, Selective Repeat.
6. **Addressing and configuration** — IPv4, IPv6, DHCP, NAT.
7. **Applications** — client/server vs. peer-to-peer.
8. **Web** — HTTP and HTML.

The companion lab in `lab/` exercises three of these directly: a CRC-16 implementation (link layer), a Stop-and-Wait simulator (reliable transfer), and a minimal HTTP client/server (web + applications).

---

## 2. Information: Sources and Representation

Networking begins before any wire is touched: with the question of what a "message" actually is.

### 2.1 Information sources

A source produces symbols drawn from some alphabet — a microphone produces audio samples, a camera produces pixel values, a keyboard produces characters. Two source models matter for the rest of the course:

- **Discrete sources** emit symbols from a finite alphabet (text, digital sensor readings).
- **Continuous sources** emit real-valued signals that must be sampled and quantized before transmission.

### 2.2 Bits as the universal currency

Every payload eventually becomes a sequence of bits. The mapping from a symbol to bits is the *representation*:

| Symbol type | Representation |
|---|---|
| Text characters | ASCII (7-bit), UTF-8 (1–4 byte) |
| Integers | two's-complement, fixed width |
| Real numbers | IEEE 754 floats |
| Audio | PCM samples (e.g. 16-bit at 48 kHz) |
| Image | RGB pixel arrays, then JPEG/PNG compression |

Two ideas drive everything that follows:

- **Source coding (compression)** removes redundancy so fewer bits represent the same information (entropy is the lower bound, per Shannon).
- **Channel coding (error control)** *adds* structured redundancy so bits survive a noisy channel — the link layer's job in Section 3.

A useful slogan: *compress to remove waste, then add controlled redundancy back to survive the channel.*

### 2.3 Why this matters for the rest of the stack

Every later layer treats its payload as an opaque bit-string. Knowing where those bits came from explains real engineering choices:

- VoIP tolerates a little loss but not delay → UDP, small frames.
- File downloads tolerate delay but not loss → TCP, larger segments.
- Video streaming tolerates moderate loss with concealment → adaptive bitrate over HTTPS.

---

## 3. Link Layer: Frames, Error Control, CRC

The link layer is the first layer that actually puts bits on a shared medium.

### 3.1 Framing

The physical layer delivers a stream of bits with no inherent boundaries. The link layer groups bits into **frames** with a header, payload, and trailer. Three common framing techniques:

- **Length field** in the header (Ethernet II uses an EtherType that doubles as a type when ≥ 0x0600, and a length when < 0x0600 in 802.3).
- **Byte/character stuffing** (PPP) — a special start/end byte plus an escape mechanism.
- **Bit stuffing** (HDLC) — a `01111110` flag plus a stuffed `0` after any five `1`s in the payload.

A receiver can only act on a *complete* frame; framing is what gives the rest of the layer something to work with.

### 3.2 Errors on the wire

Even with good cabling, bit errors happen — thermal noise, EMI, attenuation, multipath fading on wireless. The link layer needs to:

1. **Detect** that a frame was corrupted.
2. **Decide** what to do (drop, request retransmission, correct).

### 3.3 Parity → checksum → CRC

| Scheme | Bits added | Detects |
|---|---|---|
| Single parity | 1 | Odd numbers of bit errors |
| Internet checksum (16 bits, ones'-complement sum) | 16 | Most single-bit and many burst errors; cheap, algebraic |
| **Cyclic Redundancy Check (CRC)** | typically 16 or 32 | All single-bit, all double-bit, all odd numbers of errors, all bursts shorter than the CRC length |

CRC is the link-layer workhorse because it is:

- **Strong:** mathematically guaranteed to catch entire classes of errors.
- **Fast:** implementable in hardware as a shift register XOR'd with a generator polynomial.

### 3.4 How CRC works (intuition)

Treat the message `M` as a polynomial over GF(2). Pick a fixed **generator polynomial** `G` of degree `r`. Compute:

```
T  = M·xʳ           (shift left by r bits)
R  = T mod G        (polynomial remainder, all arithmetic XOR)
Tx = T XOR R        (transmitted frame; divisible by G by construction)
```

Receiver divides the received frame by `G`. Remainder = 0 → almost certainly intact. Non-zero remainder → corruption detected.

Common generators:

| Name | Polynomial (hex) | Used by |
|---|---|---|
| CRC-16-CCITT | `0x1021` | Bluetooth, X.25, HDLC |
| CRC-32 (Ethernet) | `0x04C11DB7` | Ethernet, ZIP, PNG |

The lab implements **CRC-16-CCITT** in Python and demonstrates that a single bit-flip in a frame is reliably detected.

### 3.5 Error detection vs. error correction

The link layer in Ethernet only **detects**; it drops bad frames and lets higher layers (TCP) retransmit. Wireless and storage often add **forward error correction (FEC)** because retransmits over a 4G/5G/satellite link are expensive — losing 1% of bits hurts throughput far more than carrying ~10% redundancy.

---

## 4. Multiple Access: ALOHA and CSMA

When a single channel is shared by many transmitters, who gets to send and when?

### 4.1 The shared-channel problem

Three regimes are possible:

- **Channel partitioning** (TDMA, FDMA, CDMA) — pre-assign slots, frequencies, or codes. Efficient at high load, wasteful at low load.
- **Random access** — everyone transmits whenever they want, resolve collisions afterward. Cheap and decentralized.
- **Taking turns** (token ring, polling) — explicit coordination. Predictable but adds latency.

The Internet's link layers are dominated by **random-access** schemes.

### 4.2 Pure ALOHA

The original 1970s Hawaiian wireless network. Rule: *transmit whenever you have a frame; if no ACK, wait a random time and retry.*

- Maximum throughput: **~18.4 % (1 / 2e)** of channel capacity.
- Dead simple, but collisions dominate at moderate load.

### 4.3 Slotted ALOHA

Introduce global time slots; transmissions can only start at a slot boundary. This halves the vulnerable window.

- Maximum throughput: **~36.8 % (1 / e)**.

### 4.4 CSMA — Carrier Sense Multiple Access

"Listen before you talk." A node senses whether the channel is busy before transmitting. Variants:

- **1-persistent CSMA** — transmit immediately when idle. Aggressive, prone to collisions when multiple stations are waiting.
- **Non-persistent CSMA** — if busy, wait a random interval, then re-sense.
- **p-persistent CSMA** — when idle, transmit with probability *p*; otherwise defer one slot.

### 4.5 CSMA/CD (Ethernet)

**Collision Detection** is feasible on a wire because a station can listen while transmitting. Ethernet adds:

1. Sense; transmit when idle.
2. While transmitting, monitor the line; if a collision is detected, abort and send a 32-bit jam signal.
3. **Binary exponential backoff:** after the *n*-th collision, wait a random number of slot times in `[0, 2ⁿ - 1]` (capped at `n=10`, give up at `n=16`).

Modern switched Ethernet runs full-duplex point-to-point, so CSMA/CD is effectively dormant — but the *protocol* still works on legacy half-duplex links.

### 4.6 CSMA/CA (Wi-Fi)

Wireless cannot reliably detect collisions while transmitting (TX power swamps any incoming signal — the "near/far" problem). 802.11 substitutes **Collision Avoidance**:

1. Sense the channel for a DIFS interval.
2. Wait an additional random backoff.
3. Transmit; receiver replies with ACK.
4. Optional **RTS/CTS** handshake for hidden-terminal scenarios.

This is the bridge into Section 5.

---

## 5. Wireless Networks: IEEE 802.11

802.11 is the Ethernet of the air. It keeps the same MAC-address abstraction but rebuilds nearly everything below it.

### 5.1 Architecture

- **STA (station)** — the client, e.g. a laptop.
- **AP (access point)** — bridges 802.11 to the wired network.
- **BSS (basic service set)** — one AP and its associated stations.
- **ESS (extended service set)** — multiple BSSs glued together by a shared SSID.

### 5.2 Physical-layer evolution

| Standard | Year | Band | Max rate (single stream) | Notes |
|---|---|---|---|---|
| 802.11b | 1999 | 2.4 GHz | 11 Mbps | DSSS |
| 802.11a/g | 1999/2003 | 5 / 2.4 GHz | 54 Mbps | OFDM introduced |
| 802.11n (Wi-Fi 4) | 2009 | 2.4/5 GHz | 150 Mbps/stream | MIMO |
| 802.11ac (Wi-Fi 5) | 2013 | 5 GHz | 433 Mbps/stream | 80/160 MHz channels, MU-MIMO |
| 802.11ax (Wi-Fi 6/6E) | 2019 | 2.4/5/6 GHz | 1.2 Gbps/stream | OFDMA, BSS coloring |
| 802.11be (Wi-Fi 7) | 2024 | 2.4/5/6 GHz | 2.9 Gbps/stream | 320 MHz, 4096-QAM, MLO |

### 5.3 Frame format (simplified)

802.11 has up to **four MAC addresses** in the header (vs. Ethernet's two), supporting forwarding through APs and infrastructure modes.

```
+----------+--------+----+----+--------+--------+--------+----+--------+--------+-----+
| Frame Ctl| Dur/ID | A1 | A2 |   A3   | SeqCtl |   A4   | QoS|  HT    | Body   | FCS |
+----------+--------+----+----+--------+--------+--------+----+--------+--------+-----+
```

The trailing **FCS** is a CRC-32 — the same CRC concept as Section 3, applied per-frame.

### 5.4 Association flow

1. **Scan** — passive (listen for beacons) or active (probe requests).
2. **Authenticate** (open or WPA2/WPA3 SAE).
3. **Associate** with an AP.
4. Get an IP via **DHCP** (Section 7).
5. (Optional) DNS lookup, then traffic.

This is exactly what your laptop does every time it joins a coffee-shop network.

### 5.5 Why Wi-Fi feels slower than Ethernet

- Half-duplex shared medium.
- CSMA/CA backoff overhead.
- Rate adaptation in response to errors.
- Hidden terminals and interference.
- MAC-layer ACKs after every unicast frame.

Even at gigabit-class advertised rates, real throughput is typically 30–60% of the PHY rate.

---

## 6. Reliable Data Transfer: Stop-and-Wait, GBN, SR

These are the *abstract* protocols that prepare you to read TCP. Each adds a piece needed for reliable delivery over an unreliable channel.

### 6.1 The channel models (rdt 1.0 → rdt 3.0)

The classic Kurose & Ross development:

| Version | Channel assumption | Mechanism added |
|---|---|---|
| rdt 1.0 | Perfect | Just send; trivial |
| rdt 2.0 | Bit errors | Checksum + ACK/NAK |
| rdt 2.1/2.2 | + duplicate ACKs possible | Sequence numbers (1 bit) |
| rdt 3.0 | + packet loss | Retransmission timer |

rdt 3.0 = **Stop-and-Wait** = the minimum viable reliable transport.

### 6.2 Stop-and-Wait

Sender sends one packet, waits for ACK, then sends the next. With sequence numbers `0` and `1`, it's correct even with retransmissions and duplicate deliveries.

**Throughput is the catch.** With a one-way delay `d`, packet length `L`, and link rate `R`:

```
U = (L/R) / (RTT + L/R)
```

For `L = 1 KB`, `R = 1 Gbps`, `RTT = 30 ms`: `U ≈ 0.027 %`. The pipe sits idle 99.97 % of the time.

### 6.3 Pipelining: sliding window

The fix is to allow `N` unacknowledged packets in flight:

```
U_pipe = N · (L/R) / (RTT + L/R)
```

Two flavors:

#### Go-Back-N (GBN)

- Sender keeps a window of size `N`.
- Receiver only ACKs the **next expected** sequence number (cumulative ACK).
- On timeout, sender retransmits **everything** from the lost packet onward.
- Receiver discards out-of-order packets.

Simple receiver, wasteful sender on lossy links.

#### Selective Repeat (SR)

- Receiver buffers out-of-order packets and ACKs each one individually.
- Sender retransmits **only** the specific packets that timed out.
- Window size constraint: `N ≤ 2^(k-1)` where `k` is sequence-number bit width (otherwise old and new packets become indistinguishable).

Better channel use, more complex receiver.

#### Comparison

| Property | Stop-and-Wait | GBN | SR |
|---|---|---|---|
| In-flight packets | 1 | N | N |
| Receiver buffer | 0 | 0 | up to N |
| ACKs | per packet | cumulative | per packet |
| Retransmit on loss | the one | everything from loss | only the lost |
| Real-world heir | — | early TCP | TCP w/ SACK, QUIC |

### 6.4 Connection to TCP

Modern TCP is essentially a **selective-repeat-flavored sliding window** with:

- 32-bit sequence numbers (byte-indexed).
- Cumulative ACKs **plus** SACK (RFC 2018) for selective info.
- Adaptive window sizing (flow control via `rwnd`, congestion control via `cwnd`) — the Week 06 material.

The lab's Stop-and-Wait simulator drops random packets/ACKs and shows the timer-driven retransmission loop — the smallest possible model of what TCP does at scale.

---

## 7. Addressing and Configuration: IPv4, IPv6, DHCP, NAT

### 7.1 IPv4 recap and exhaustion

- 32-bit addresses → ~4.3 billion total.
- IANA depleted its central pool in 2011; regional registries followed.
- Real-world IPv4 lives on through aggressive reuse via **NAT** (Section 7.4).

### 7.2 IPv6

- **128-bit addresses** → 3.4 × 10³⁸. Effectively inexhaustible.
- Written as eight 16-bit hex groups, separated by `:`. `::` collapses one run of zero groups.

```
2001:0db8:0000:0000:0000:0000:0000:0001
   = 2001:db8::1
```

Key changes from IPv4:

| Aspect | IPv4 | IPv6 |
|---|---|---|
| Address length | 32-bit | 128-bit |
| Header | Variable, includes checksum | Fixed 40 B, no checksum |
| Fragmentation | Routers may fragment | Source only (PMTUD) |
| ARP | Yes | Replaced by NDP (ICMPv6) |
| Address config | DHCP | SLAAC + DHCPv6 |
| Broadcast | Yes | Removed; uses multicast |

### 7.3 DHCP — Dynamic Host Configuration Protocol

When a host joins a network it needs four things: an **IP address**, a **subnet mask**, a **default gateway**, and a **DNS server**. DHCP delivers all four. The classic four-message **DORA** exchange:

1. **DHCPDISCOVER** — client broadcasts on `255.255.255.255` from `0.0.0.0:68`.
2. **DHCPOFFER** — server (or relay) replies with a candidate lease.
3. **DHCPREQUEST** — client formally asks for that lease.
4. **DHCPACK** — server confirms; lease starts.

Leases are time-bounded (typically minutes to days) and renewed at half the lease duration.

**IPv6** can use SLAAC (Stateless Address Autoconfiguration): the host derives its own address from the router's advertised prefix and either its MAC (modified EUI-64) or a privacy-extension random suffix. DHCPv6 still exists for stateful needs (DNS, options).

### 7.4 NAT — Network Address Translation

NAT lets many hosts share one public IPv4 address. The most common form is **NAPT** ("port-overloaded NAT"):

```
Internal:  192.168.1.42:51000  →  Public: 203.0.113.5:34567
                                    (rewritten by NAT box)
```

The NAT keeps a translation table:

| Inside (IP:port) | Outside (IP:port) | Remote |
|---|---|---|
| 192.168.1.42:51000 | 203.0.113.5:34567 | 8.8.8.8:443 |

Entries expire after a short idle window for UDP, longer for established TCP.

**Why it matters for protocols:**

- Breaks the end-to-end principle — the inside host cannot be addressed unsolicited.
- Forces application-layer workarounds: STUN, TURN, ICE for WebRTC; UPnP/PCP for port mapping; relays for P2P.
- Even after IPv6, NAT persists for "address conservation" and (perceived) security.

---

## 8. Applications: Client/Server vs. Peer-to-Peer

### 8.1 Client/server

- One **server** with a stable address and identity.
- Many **clients** initiate connections to it.
- Examples: HTTP/HTTPS, SMTP, DNS (mostly), most cloud APIs.
- Pros: simple to operate, easy to secure, well-understood scaling (load balancers, CDNs).
- Cons: server is a bottleneck and single point of failure; download throughput per client falls as `N` grows.

### 8.2 Peer-to-peer (P2P)

- Every participant is both client and server.
- No required centralized infrastructure for the data plane (sometimes a tracker or DHT for discovery).
- Examples: BitTorrent, classic Skype, blockchains, IPFS.
- Pros: aggregate capacity scales with participants; no single bottleneck.
- Cons: peer churn, NAT traversal hard (Section 7.4), harder security model, harder to monetize.

### 8.3 Hybrid models

Most real systems mix the two:

- Gaming: client/server matchmaking + peer-to-peer voice.
- Video calls (Zoom): client/server signaling + SFU media servers (logically client/server, but optimized for many simultaneous flows).
- BitTorrent: tracker (centralized) + swarm (P2P).

The lab demonstrates the **client/server** half by spinning up an HTTP server and pointing a client at it; extending it to a P2P style is straightforward with `socket.SOCK_DGRAM` and a small peer list.

---

## 9. Web: HTTP and HTML

### 9.1 HTML in one paragraph

HTML is a tag-based markup language for documents. A page is a tree of elements — `<html>`, `<head>`, `<body>`, `<h1>`, `<p>`, `<a>`, `<img>`, `<script>`, `<style>` — which the browser parses into a DOM and renders. CSS styles it; JavaScript animates it; everything else (HTTP, TCP, IP, Wi-Fi) just delivers the bytes.

### 9.2 HTTP — the request/response protocol

A request:

```
GET /index.html HTTP/1.1
Host: example.com
User-Agent: curl/8.4
Accept: */*

```

A response:

```
HTTP/1.1 200 OK
Date: Sun, 03 May 2026 20:00:00 GMT
Content-Type: text/html; charset=utf-8
Content-Length: 137

<!doctype html>
<html><body><h1>Hello</h1></body></html>
```

Key elements:

| Piece | Meaning |
|---|---|
| **Method** (`GET`, `POST`, `PUT`, `DELETE`, `HEAD`, …) | The verb |
| **Path** (`/index.html`) | The resource |
| **Headers** | Metadata (host, content type, cookies, auth) |
| **Body** | Optional payload |
| **Status code** | 1xx info, 2xx success, 3xx redirect, 4xx client error, 5xx server error |

### 9.3 HTTP version landscape

| Version | Year | Transport | Multiplexing | TLS required? |
|---|---|---|---|---|
| HTTP/1.0 | 1996 | TCP, one request per connection | No | No |
| HTTP/1.1 | 1997/1999 | TCP, persistent + pipelining | Head-of-line blocked | No |
| HTTP/2 | 2015 | TCP, binary, multiplexed streams | Yes (per stream) | De facto |
| HTTP/3 | 2022 | **QUIC over UDP** | Yes (no HoL across streams) | Yes |

### 9.4 Anatomy of a page load

1. **DNS** resolves `example.com` → IP.
2. **TCP** (or QUIC) handshake to that IP on port 443.
3. **TLS** handshake (Week 08 material).
4. **HTTP** GET for the HTML document.
5. Browser parses HTML, finds CSS/JS/image references, opens parallel requests.
6. Browser renders to pixels.

Every layer of the course participates in a single page load. The lab's `http_client.py` walks through steps 2 and 4 explicitly using only `socket`.

### 9.5 Statelessness and cookies

HTTP itself is stateless — every request stands alone. State is layered on top via:

- **Cookies** (`Set-Cookie:` / `Cookie:` headers) → server-managed session id.
- **Authorization** headers → tokens (JWT, OAuth bearer).
- **Local storage / IndexedDB** → client-side state managed by JS.

This stateless core is what made HTTP scale — load balancers can send any request to any backend.

---

## 10. The Lab

The companion lab (`lab/`) implements three small Python programs, each tied to one of the topics above. None require external dependencies beyond the Python standard library.

| File | Topic | What it demonstrates |
|---|---|---|
| `lab/crc_demo.py` | Link layer | CRC-16-CCITT computation, verification, and detection of single-bit corruption |
| `lab/stop_and_wait.py` | Reliable data transfer | Stop-and-Wait sender/receiver over a simulated lossy "channel"; measures throughput at varying loss rates |
| `lab/http_server.py` + `lab/http_client.py` | Web + applications | A bare TCP HTTP/1.1 server and a hand-rolled client speaking the protocol byte-for-byte |

See `lab/README.md` for usage and discussion. The lab is intentionally small enough to read end-to-end in one sitting and to capture with `tcpdump` for cross-checking against the Week 07 observability tools.

---

## 11. Summary

This week filled in the syllabus topics that did not get a dedicated artifact earlier in the semester. Each section connects to material already covered:

- **Information** explains what TCP and HTTP are actually carrying.
- **Link layer / CRC** is the mechanism behind every Ethernet FCS captured in Week 07.
- **Multiple access** explains why Wi-Fi is slower than Ethernet despite high PHY rates.
- **802.11** is where the four-address frame and association handshake live.
- **Reliable data transfer** is the conceptual scaffolding for TCP from Week 06.
- **IPv4/IPv6/DHCP/NAT** are the address-management glue between Weeks 03 and 07.
- **Applications and the Web** are the layer that the entire stack ultimately serves.

With the lab, the syllabus's *Lab* type is now also represented. The three programs are short, observable with the Week 07 tools, and small enough to extend in any direction (P2P swarm, GBN/SR variants, HTTPS via `ssl`, NAT-traversal experiments).
