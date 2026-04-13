# Week 06 — TCP: Connections, Flow Control, Congestion Control, and QUIC

**Course:** EC 441 — Introduction to Computer Networking, Boston University, Spring 2026

**Type:** Report

**Sources:** Lecture 19 — TCP Part 1 (connections, sequencing, flow control); Lecture 20 — TCP Part 2 (congestion control, CUBIC, ECN, QUIC)

---

## 1. Introduction

Lectures 18–20 form a single transport-layer arc: Lecture 18 built reliable data transfer from first principles; Lecture 19 maps those ideas onto **TCP** as deployed — segment format, the **byte-stream** abstraction, connection setup and teardown, **retransmission** and **RTT estimation**, and **flow control** via the receive window. Lecture 20 completes the sender-side picture with **congestion control**: the **congestion window (cwnd)**, **slow start**, **AIMD**, **fast recovery**, performance limits on high-**BDP** paths, **CUBIC**, **ECN**, fairness arguments, and why **QUIC** reimplements transport over **UDP** for the modern web.

---

## 2. From Lecture 18 Building Blocks to TCP

| Lecture 18 concept | TCP’s answer |
|---|---|
| Sequence numbers | Byte offsets in the stream (not packet counts) |
| Cumulative ACK (GBN) | Default; **SACK** option adds SR-style selective ACK |
| Receiver buffer (SR) | Required; advertised as **rwnd** |
| Pipelining | **Effective window** = min(**cwnd**, **rwnd**) |
| Single timer vs. per-packet | One **RTO** per connection + **fast retransmit** (3 dup ACKs) |
| Full-duplex | Two independent byte streams, one per direction |

Lecture 19 develops everything except **cwnd**; Lecture 20 defines congestion control and the modern ecosystem (CUBIC, QUIC).

---

## 3. Lecture 19 — TCP Segment Header

A TCP segment has a **minimum 20-byte header** (up to 60 bytes with options), then payload.

**Core fields:**

| Field | Role |
|---|---|
| Source / destination port (16 bits each) | With IP addresses, form the **5-tuple** that identifies a connection |
| **Sequence number** (32 bits) | Byte offset of the **first** data byte in this segment; **SYN** and **FIN** each consume **one** sequence number |
| **Acknowledgment number** (32 bits) | **Next** byte the sender of this segment expects; **ACK = N** means “all bytes through **N − 1** received.” Valid when **ACK** flag = 1 |
| **Data offset** (4 bits) | Header length in 32-bit words (like IPv4 **IHL**); min 5 (= 20 bytes) |
| Flags | **SYN**, **ACK**, **FIN**, **RST**, **PSH**, **URG**; **CWR** / **ECE** for ECN (L20) |
| **Window size** (16 bits) | **rwnd** — free space at the receiver; caps **bytes in flight** |
| **Checksum** (16 bits) | Pseudo-header (src/dst IP, proto=6, TCP length) + header + data; **mandatory** (unlike UDP’s optional checksum) |
| **Urgent pointer** | Rarely used today |
| **Options** | **MSS** (often 1460 on Ethernet: 1500 − 20 IP − 20 TCP), **Window Scale**, **SACK**, **Timestamps** |

**MSS on Ethernet:** 1460 bytes of TCP data per segment (typical).

---

## 4. Lecture 19 — The Byte-Stream Model

TCP exposes a **continuous byte stream** — no message boundaries at the transport layer. Two `write(100)` calls may be read as one `read(200)` or many smaller reads. Applications add framing where needed (HTTP header termination, TLS record lengths).

**Sequence numbers count bytes**, not segments. Example: ISN = 1000, first segment carries 500 bytes → seq = 1000 (bytes 1000–1499); next segment seq = 1500. An ACK of 1500 asks for byte 1500 next.

**SEQ/ACK duality:** “Your SEQ is my ACK.” ACK-only segments do not advance the sender’s sequence number; only **data**, **SYN**, and **FIN** consume sequence space.

---

## 5. Lecture 19 — Three-Way Handshake and ISN Randomization

**Handshake** (minimum three messages for mutual confirmation):

1. Client → Server: **SYN**, seq = **x** (client ISN).
2. Server → Client: **SYN-ACK**, seq = **y** (server ISN), ack = **x + 1**.
3. Client → Server: **ACK**, ack = **y + 1**.

**SYN** and **SYN-ACK** each consume one sequence number so loss can be detected and segments retransmitted.

**Why randomize the ISN?**

1. **Stale segments:** A new connection reusing the same 5-tuple could accept delayed segments from an old connection if sequence space restarted predictably at zero.
2. **Security:** Predictable ISNs enable **sequence-number prediction** and forged segments from off-path attackers.

Modern stacks use unpredictable ISNs (e.g., hash of 5-tuple, secret, time).

---

## 6. Lecture 19 — Teardown: FIN, TIME WAIT, RST

TCP closes **each direction independently** (half-close).

1. Active closer sends **FIN** (consumes one sequence number).
2. Peer **ACK**s; may still send data.
3. When the peer is done, it sends **FIN**; active closer **ACK**s.

**TIME WAIT** (active closer, after the final ACK): lasts **2 × MSL** (often on the order of minutes).

- The **final ACK may be lost** — the peer may retransmit **FIN**; the host in TIME WAIT must still accept and re-ACK.
- **Prevents 5-tuple reuse confusion** until stale segments from the old connection have left the network.

**RST:** Abrupt abort — no graceful close, **no TIME WAIT**. Used when no listener (“connection refused”), half-open detection after crash, firewall teardown. RST is not acknowledged; the receiver drops buffered data and closes.

---

## 7. Lecture 19 — Reliable Delivery: ACKs, RTO, Fast Retransmit

**Cumulative ACKs:** ACK **N** ⇒ all bytes through **N − 1** received. **Delayed ACK:** wait up to ~500 ms or **two** full segments before ACKing, to cut ACK traffic.

**SACK** (negotiated at SYN time): reports specific byte ranges received out of order — SR-style behavior; default on Linux, macOS, Windows (Wireshark will usually show SACK).

**RTO:** One timer keyed to the oldest unacknowledged byte. On timeout: retransmit; **exponential backoff** on repeated timeouts (cap ~60–120 s). RTO must track **RTT**.

**SRTT (EWMA):**

\[
\text{SRTT} \leftarrow (1 - \alpha)\,\text{SRTT} + \alpha\, R,\quad \alpha = \tfrac{1}{8}
\]

This is a first-order low-pass filter; \(\alpha = 2^{-3}\) was chosen partly for efficient shifts on early hardware.

**RTTVAR and RTO (Jacobson):** Mean RTT alone is insufficient — high **variance** needs a wider timeout margin.

\[
\text{RTTVAR} \leftarrow (1 - \beta)\,\text{RTTVAR} + \beta\,|\text{SRTT} - R|,\quad \beta = \tfrac{1}{4}
\]

\[
\text{RTO} = \text{SRTT} + 4 \cdot \text{RTTVAR}
\]

(RFC 6298; used in Linux TCP.)

**Karn’s algorithm:** Do not update SRTT/RTTVAR from ACKs that follow a **retransmit** — ambiguous which transmission was ACKed. **Timestamps** option removes this ambiguity when enabled.

**Fast retransmit:** Out-of-order data causes **duplicate ACKs** for the last in-order byte. **Three** duplicate ACKs ⇒ retransmit the missing segment **immediately** (don’t wait for RTO). **Why three?** One or two dup ACKs can be **reordering**, not loss.

---

## 8. Lecture 19 — Flow Control, Nagle, State Machine

**Flow control:** Every segment carries **rwnd**. Sender constraint:

\[
\text{bytes in flight} \le \text{rwnd}
\]

If **rwnd = 0**, the sender stops and sends **1-byte zero-window probes** until the window opens.

**Worked idea:** 16 KB buffer; three 1460 B segments arrive → 4380 B buffered → **rwnd = 16384 − 4380**; after the app reads everything, **rwnd** returns to full buffer size.

**Nagle’s algorithm:** If data is already in flight, buffer small writes until an ACK, then send a larger segment — reduces tiny-packet inefficiency but adds latency. Disabled with **TCP_NODELAY** for interactive/low-latency apps.

**Silly window syndrome (brief):** Receivers avoid advertising absurdly small windows (e.g., Clark’s approach); pairs with sender-side discipline.

**State machine (key states):** **LISTEN**, **SYN_SENT**, **SYN_RCVD**, **ESTABLISHED**, **FIN_WAIT_1/2**, **CLOSE_WAIT**, **LAST_ACK**, **TIME_WAIT**, **CLOSED**. Tools like `ss -t -a` expose live states.

---

## 9. Lecture 20 — Flow Control vs. Congestion Control

| Limit | Set by | Protects |
|---|---|---|
| **rwnd** | Receiver | Receiver buffer from overflow |
| **cwnd** | Sender | Network from overload |
| **Effective window** | min(**cwnd**, **rwnd**) | Both |

**Flow control** is **explicit** (receiver advertises space). **Congestion control** is **implicit** — routers rarely signal “I’m congested”; TCP infers congestion from **loss** (and optionally **ECN**).

**Loss signals:**

- **Timeout:** severe — little or nothing getting through → **cwnd → 1 MSS**, restart **slow start**.
- **Triple duplicate ACK:** mild — later packets still arrive → **fast recovery**, halve **cwnd**, skip slow start.

---

## 10. Lecture 20 — Slow Start, Congestion Avoidance, Fast Recovery

**Slow start:** **cwnd** starts at **1 MSS**. For each ACK, **cwnd +=1 MSS** ⇒ **cwnd doubles about every RTT** (exponential). “Slow” refers to the **starting** point, not the growth rate.

**ssthresh:** While **cwnd < ssthresh** → slow start; when **cwnd ≥ ssthresh** → **congestion avoidance** (linear growth, ~**+1 MSS per RTT** via **cwnd += MSS²/cwnd** per ACK in classic Reno).

**On 3 dup ACKs:** **ssthresh = cwnd/2**, **cwnd = ssthresh**, fast retransmit, **fast recovery** (inflate **cwnd** slightly for additional dup ACKs; exit to CA when a “new” ACK arrives).

**On timeout:** **ssthresh = cwnd/2**, **cwnd = 1 MSS**, restart slow start.

**Worked trace (from slides):** Starting **cwnd = 1**, **ssthresh = 8**: SS doubles until **cwnd** hits 8; CA adds ~1 per RTT; 3 dup ACKs at **cwnd = 10** → **cwnd = 5**; timeout at **cwnd = 8** → **cwnd = 1**, **ssthresh = 4**, SS again.

**Kernel visibility:** `ss -ti` shows algorithm (e.g., **cubic**), **rtt**/**rto**, **cwnd**, **ssthresh**, **wscale**, etc.

---

## 11. Lecture 20 — Throughput, BDP, Window Scaling

**Mathis et al. (1997) scaling** (steady-state Reno, congestion avoidance):

\[
\text{BW} \approx \frac{\text{MSS}}{\text{RTT}} \cdot \frac{1}{\sqrt{p}}
\]

Throughput falls with **RTT** and with **√p** — loss is expensive. Example from lecture: **10 Gb/s** at **100 ms** RTT with **MSS = 1460 B** needs **p** on the order of **10^-10** — essentially loss-free pipes for high speed and long RTT.

**BDP** = **BW × RTT** (bytes that fill the pipe). The **16-bit** window caps **rwnd** at **64 KB** without options — e.g. **1 Gb/s × 100 ms** needs ~**12.5 MB** in flight; max ~**5.2 Mb/s** (64 KB / 0.1 s) �� 5.2 Mb/s** without window scale.

**Window Scale (RFC 7323):** negotiated at SYN; effective window = advertised value × **2^n**, **n ∈ [0, 14]** — up to ~**1 GB**.

---

## 12. Lecture 20 — Reno vs. CUBIC

| | **Reno** | **CUBIC** |
|---|---|---|
| Growth clock | Per **RTT** (linear AIMD) | **Wall-clock** time (cubic curve) |
| High BDP | Slow climb after loss | Faster recovery when far from last loss |
| RTT fairness | Favors **short-RTT** flows | **More RTT-fair** (growth not purely RTT-stepped) |
| Linux default | Superseded | **Default** since kernel 2.6.19 |

**CUBIC idea:** \(W(t) = C(t-K)^3 + W_{\max}\) with **K** chosen so the window probes cautiously near the last congestion point and grows aggressively when far below prior **W_max**.

---

## 13. Lecture 20 — ECN and AIMD Fairness

**Loss-based signaling:** Queue fills → drop → sender reacts **after** losing goodput.

**ECN (RFC 3168):** Router marks **CE** in IP when congestion is imminent; receiver echoes **ECE** in TCP; sender cuts **cwnd** like a loss — but the packet is **delivered**. Benefits: earlier signal, less goodput loss, often lower latency under load. Requires path and endpoint support (common in datacenters; uneven on the public Internet).

**AIMD fairness sketch:** Two flows sharing capacity **C**. **Additive increase** moves along **(+Δ, +Δ)** toward the efficiency line **x₁ + x₂ = C**. **Multiplicative decrease** scales both toward the origin, preserving ratio while pulling toward **fairness line** **x₁ = x₂**. The trajectory spirals toward **(C/2, C/2)**.

**Caveats:** Unequal RTTs (Reno), **UDP** without congestion control, **N parallel TCPs** from one host (browser parallelism) all break naive fairness stories.

---

## 14. Lecture 20 — QUIC and the Socket View

**TCP pain points QUIC addresses:**

1. **HOL blocking:** HTTP/2 multiplexes many streams on **one** TCP byte stream — one gap blocks **all** streams. QUIC multiplexes **independently** over UDP.
2. **Setup latency:** TCP’s 3-way handshake plus TLS often totals **2–3 RTTs** before app data; QUIC + TLS 1.3 targets **1 RTT** (**0 RTT** resume with caveats).
3. **Ossification:** Middleboxes parse TCP; QUIC encrypts headers (beyond minimal framing) over **UDP**.
4. **Connection migration:** TCP tied to **4-tuple**; QUIC uses **connection IDs** across address changes.

**QUIC:** Mandatory **TLS 1.3**, own **congestion control** (e.g., CUBIC/BBR) in user space, used heavily by **HTTP/3**.

**Socket programmer’s view:** `send`/`recv` see a reliable byte stream; **TCP_NODELAY**, **SO_RCVBUF**/**SO_SNDBUF**, and (Linux) **TCP_INFO** expose tuning and internals.

---

## 15. Transport Layer Summary (Lectures 18–20)

| Topic | Lecture | Key idea |
|---|---|---|
| Ports / demux | 18 | Processes identified by ports |
| UDP | 18 | Minimal 8-byte header; app responsible for reliability |
| S&W, GBN, SR | 18 | Pipelining, windows, timers |
| TCP header | 19 | Seq/ack are **byte** indices |
| Handshake / ISN | 19 | **SYN/SYN-ACK/ACK**; random ISN |
| Reliable + RTO | 19 | EWMA + RTTVAR; Karn; backoff; **fast retransmit** |
| Flow control | 19 | **rwnd** |
| Slow start / AIMD | 20 | **cwnd**; probe and back off |
| Fast recovery | 20 | 3 dup ACKs → skip slow start |
| Effective window | 20 | min(**cwnd**, **rwnd**) |
| QUIC | 20 | UDP + TLS + streams + migration |

---

## 16. What’s Next (from the course arc)

Later material ties these concepts to **hands-on sockets** (labs), **Wireshark** traces of real TCP (SACK, window scaling, congestion behavior), and application protocols built atop TCP or QUIC.
