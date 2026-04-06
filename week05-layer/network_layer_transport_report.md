# Week 05 — IPv4/IPv6, NAT, ICMP, and Transport Layer Fundamentals

**Course:** EC 441 — Introduction to Computer Networking, Boston University, Spring 2026

**Type:** Report

**Sources:** Lecture 17 — IPv4, IPv6, NAT, and ICMP; Lecture 18 — Transport Layer, UDP, and Reliable Data Transfer

---

## 1. Introduction

Lectures 13–16 completed the routing picture: how forwarding tables are built and how routers decide where to send packets. Lecture 17 opens up the **IPv4 datagram** itself — the actual data structure every router examines — along with the supporting protocols: **ICMP** for error reporting, **NAT** for address sharing, **IPv6** as the next-generation replacement, and **DHCP** for dynamic address configuration. Lecture 18 crosses the layer boundary upward into the **transport layer**, introducing process-to-process communication via **multiplexing and ports**, examining **UDP** as the minimal transport protocol, and building the foundation of **reliable data transfer** through Stop-and-Wait, Go-Back-N, and Selective Repeat.

---

## 2. Lecture 17 — The IPv4 Datagram Header

### 2.1 Header structure

Every IPv4 packet begins with a header of at least **20 bytes** (160 bits). The base format:

```
0        4        8       12       16       20       24       28      32
| Ver  | IHL  |  DSCP   |ECN|          Total Length               |
|          Identification          | Flg |    Fragment Offset     |
|    TTL    |   Protocol  |            Header Checksum            |
|                     Source Address (32 bits)                    |
|                   Destination Address (32 bits)                 |
|                    Options (if IHL > 5)                        |
```

### 2.2 Field-by-field description

| Field | Size | Purpose |
|---|---|---|
| Version | 4 bits | Always 4 for IPv4; tells the router which header format to parse |
| IHL | 4 bits | Header length in 32-bit words; minimum 5 (= 20 bytes) |
| DSCP | 6 bits | Differentiated Services Code Point — IP's practical QoS mechanism |
| ECN | 2 bits | Explicit Congestion Notification — signal congestion without dropping packets |
| Total Length | 16 bits | Full datagram size (header + payload); max 65,535 bytes |
| Identification | 16 bits | All fragments of the same datagram share this value for reassembly |
| Flags | 3 bits | Bit 1: DF (Don't Fragment); Bit 2: MF (More Fragments) |
| Fragment Offset | 13 bits | Fragment's position within the original datagram, in 8-byte units |
| TTL | 8 bits | Decremented at each hop; packet dropped (ICMP Time Exceeded sent) when it reaches 0 |
| Protocol | 8 bits | Demultiplexing key to the upper layer: 1 = ICMP, 6 = TCP, 17 = UDP, 89 = OSPF |
| Header Checksum | 16 bits | Covers the header only; recomputed at every hop because TTL changes |
| Source Address | 32 bits | Sender's IP; modified by NAT |
| Destination Address | 32 bits | Used for the forwarding table lookup (longest prefix match) |
| Options | 0–40 bytes | Rarely used today; variable length is why IHL exists |

**DSCP and QoS.** DSCP provides differentiated service without per-flow signaling. Packets are marked by class; each router independently decides how to treat each class in its queues.

| DSCP Value | Per-Hop Behavior | Typical Use |
|---|---|---|
| 000000 | Best Effort (default) | Regular web traffic |
| 001010–011010 | Assured Forwarding | Video streaming |
| 101110 | Expedited Forwarding | VoIP — low delay, low jitter |

**What routers actually examine at each hop.** A forwarding router primarily needs the Destination Address (forwarding decision), TTL (decrement and check), Header Checksum (verify and recompute), Total Length (packet boundary), and Flags/Fragment Offset (if fragmentation is involved). Source Address, Protocol, DSCP, and payload pass through unmodified except by NAT or QoS-aware routers.

---

## 3. Lecture 17 — ICMP

### 3.1 Purpose and encapsulation

**ICMP (Internet Control Message Protocol)**, defined in RFC 792, is the network layer's mechanism for error reporting and diagnostics. Although technically a separate protocol, ICMP is encapsulated directly in IP datagrams (Protocol = 1) and is considered part of the network layer. IP is unreliable and connectionless; ICMP provides the feedback mechanism when something goes wrong.

### 3.2 Message format

Every ICMP message begins with **Type** (8 bits), **Code** (8 bits), and **Checksum** (16 bits), followed by type-specific data. Error messages include the IP header and first 8 bytes of the original datagram that triggered the error — enough to identify which packet failed (the 8 bytes cover transport-layer source and destination ports).

| Type | Code | Name | Purpose |
|---|---|---|---|
| 0 | 0 | Echo Reply | Response to ping |
| 3 | 0 | Dest Unreachable: Network | No route to destination network |
| 3 | 1 | Dest Unreachable: Host | Network reachable but host unreachable |
| 3 | 3 | Dest Unreachable: Port | Host reached but destination port closed |
| 3 | 4 | Frag Needed, DF Set | Packet too large, DF flag prevents fragmentation |
| 8 | 0 | Echo Request | Ping request |
| 11 | 0 | Time Exceeded: TTL | TTL decremented to 0 (used by traceroute) |
| 11 | 1 | Time Exceeded: Reassembly | Fragment reassembly timeout |

**Key rule:** ICMP error messages are never generated in response to other ICMP error messages, preventing infinite cascades.

### 3.3 How ping works

1. Host creates an **ICMP Echo Request** (Type 8, Code 0) with an identifier, sequence number, and optional payload.
2. Encapsulated in an IP datagram with Protocol = 1, routed to the destination.
3. Destination's network layer sees Protocol = 1 and hands the payload to ICMP.
4. ICMP generates an **ICMP Echo Reply** (Type 0, Code 0) with the same identifier and sequence number.
5. Sender measures the **round-trip time (RTT)**.

ping operates entirely at the network layer — it does not use TCP or UDP.

### 3.4 How traceroute works

traceroute exploits TTL expiration and ICMP Time Exceeded messages:

1. Send a packet with TTL = 1. The first router decrements TTL to 0, drops the packet, and sends ICMP Time Exceeded (Type 11, Code 0). The source IP of this reply reveals the first router's address.
2. Send TTL = 2. The second router replies. Repeat for TTL = 3, 4, …
3. The destination responds differently by implementation:
   - **Unix `traceroute`:** sends UDP to a high port (33434+). Destination replies with ICMP Destination Unreachable: Port (Type 3, Code 3) because nothing listens there.
   - **Windows `tracert`:** sends ICMP Echo Requests. Destination replies with Echo Reply.

`* * *` entries indicate routers configured not to send ICMP replies (rate-limited or disabled for security).

---

## 4. Lecture 17 — IP Fragmentation

### 4.1 The MTU problem

Every link has a **Maximum Transmission Unit (MTU)** — the largest frame payload it can carry:

| Link Type | MTU |
|---|---|
| Ethernet | 1,500 bytes |
| PPPoE (DSL) | 1,492 bytes |
| WiFi (802.11) | 2,304 bytes |
| Jumbo frames | 9,000 bytes |

When a router must forward a datagram onto a link whose MTU is smaller than the datagram, it either fragments the datagram or drops it (if DF is set) and sends an ICMP error.

### 4.2 How fragmentation works

The router splits the payload into fragments small enough for the outgoing MTU. Each fragment receives its own IP header with the same **Identification** value, the appropriate **MF** flag, and the correct **Fragment Offset**. Reassembly occurs **only at the destination**, not at intermediate routers.

**Example — 4,000-byte datagram (20-byte header + 3,980 bytes payload) entering a link with MTU = 1,500:**

| Fragment | Total Length | MF | Fragment Offset | Payload Bytes |
|---|---|---|---|---|
| 1 | 1,500 | 1 | 0 | 0–1,479 |
| 2 | 1,500 | 1 | 185 (= 1480/8) | 1,480–2,959 |
| 3 | 1,040 | 0 | 370 (= 2960/8) | 2,960–3,979 |

### 4.3 Why fragmentation is problematic

1. **Losing one fragment loses the entire datagram** — other fragments consumed bandwidth for nothing.
2. **Reassembly is complex** — the destination must buffer out-of-order fragments, handle duplicates, and time out incomplete reassemblies.
3. **Security vulnerabilities** — the "Ping of Death" used overlapping fragments to crash reassembly code; "teardrop" attacks sent contradictory fragment offsets.
4. **Header overhead** — each fragment carries its own 20-byte IP header.

### 4.4 Path MTU Discovery

The modern approach avoids fragmentation entirely:

1. Sender sets the **DF** flag on all outgoing datagrams.
2. If a router encounters a too-small MTU, it drops the packet and sends **ICMP Destination Unreachable: Fragmentation Needed** (Type 3, Code 4), including the MTU of the problematic link.
3. The sender reduces its datagram size to fit that MTU and retransmits.
4. This repeats until the smallest MTU along the entire path — the **path MTU** — is discovered.

TCP uses PMTUD to adjust its **Maximum Segment Size (MSS)**. A **PMTUD black hole** occurs when firewalls block all ICMP, preventing the "Fragmentation Needed" reply from reaching the sender — the connection stalls silently. This is why network operators should never indiscriminately block all ICMP. IPv6 bans router fragmentation entirely; only the source host may fragment.

---

## 5. Lecture 17 — NAT

### 5.1 The problem NAT solves

IPv4 has only \(2^{32} \approx 4.3\) billion addresses — a pool that is exhausted. **NAT (Network Address Translation)** allows an entire private network to share a single public IP address. Combined with RFC 1918 private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), NAT kept the internet running long past the point where IPv4 addresses should have been exhausted.

### 5.2 How NAT works (Port Address Translation)

A NAT-enabled router sits between the private network and the public internet.

**Outgoing:** The NAT router replaces the source IP (e.g., 10.0.0.2) with its public IP (e.g., 128.197.10.1) and replaces the source port with a unique port from its pool (e.g., 40001). The mapping is recorded in the **NAT translation table**.

**Return:** When the reply arrives addressed to 128.197.10.1:40001, the router looks up port 40001, finds the mapping to 10.0.0.2:5001, and forwards the packet with the original destination restored.

| WAN Side | LAN Side |
|---|---|
| 128.197.10.1:40001 | 10.0.0.2:5001 |
| 128.197.10.1:40002 | 10.0.0.3:5002 |
| 128.197.10.1:40003 | 10.0.0.4:5003 |

This is **PAT (Port Address Translation)** or **NAPT** — the most common form. A single public IP can support up to ~65,000 simultaneous connections (limited by the 16-bit port space). NAT modifies both the IP header and transport header, and must recompute both checksums.

### 5.3 NAT and the end-to-end principle

NAT fundamentally violates the **end-to-end principle** — the design philosophy that network functions should be implemented at the endpoints, not inside the network:

- **Incoming connections are broken:** A host behind NAT cannot be directly reached from the public internet. Running a server requires port forwarding or similar workarounds.
- **Peer-to-peer is complicated:** Two hosts both behind NAT cannot directly communicate.
- **Protocol assumptions violated:** Applications that embed IP addresses in their payload (FTP, SIP) need special NAT handling via Application Layer Gateways.

Workarounds include port forwarding (manual), UPnP/NAT-PMP (automatic), STUN/TURN/ICE (WebRTC and VoIP), and UDP hole punching (gaming and P2P applications).

### 5.4 NAT's legacy

NAT is simultaneously: the hack that saved the internet from IPv4 exhaustion; a violation of clean network design; a de facto security feature (hosts behind NAT are not directly reachable); and **the primary reason IPv6 adoption stalled** — NAT made IPv4 "good enough" for another 20+ years.

---

## 6. Lecture 17 — IPv6

### 6.1 The original vision

IPv6 was designed in the mid-1990s (RFC 2460, 1998):

- **128-bit addresses:** \(2^{128} \approx 3.4 \times 10^{38}\) addresses
- **Global addressability:** every device gets a real, globally routable address — no NAT needed
- **Simplified header:** fixed 40 bytes, no header checksum, faster router processing
- **No fragmentation in transit:** only endpoints may fragment
- **SLAAC:** hosts can configure themselves without DHCP
- **Mandatory IPsec:** built-in encryption and authentication

### 6.2 IPv6 header format

The IPv6 header is fixed at 40 bytes:

```
| Ver | Traffic Class |       Flow Label (20 bits)        |
|     Payload Length      | Next Header |   Hop Limit    |
|               Source Address (128 bits)                |
|             Destination Address (128 bits)             |
```

### 6.3 IPv4 vs. IPv6 comparison

| Feature | IPv4 | IPv6 |
|---|---|---|
| Address size | 32 bits | 128 bits |
| Header size | 20–60 bytes (variable) | 40 bytes (fixed) |
| Header checksum | Yes (recomputed every hop) | Removed |
| Fragmentation | In base header; routers fragment | Removed from base header |
| Options | In base header (variable IHL) | Extension headers |
| TTL | Time to Live | Hop Limit (renamed) |
| Protocol | Identifies upper layer | Next Header (same + chains extensions) |
| Broadcast | Yes | No — multicast only |
| Auto-config | DHCP required | SLAAC (stateless) |

**Why the header checksum was removed:** Recomputing it at every hop wastes CPU. Link-layer CRCs catch bit errors per link; transport-layer checksums catch end-to-end corruption. The IP header checksum was redundant. **Why fragmentation fields were removed:** In IPv6, routers never fragment — if a packet is too large, the router sends ICMPv6 "Packet Too Big." Only the source host may fragment using an extension header.

### 6.4 IPv6 address notation

IPv6 addresses are written as eight groups of four hexadecimal digits separated by colons:

```
2001:0db8:85a3:0000:0000:8a2e:0370:7334
```

Two compression rules apply:
- **Drop leading zeros** in each group: `0db8 → db8`, `0000 → 0`
- **Replace one longest run of consecutive all-zero groups with `::`**

Result: `2001:db8:85a3::8a2e:370:7334`

`::` can appear **only once** per address. Expansion examples:
- `::1` = `0000:0000:0000:0000:0000:0000:0000:0001` (loopback)
- `fe80::1` = `fe80:0000:0000:0000:0000:0000:0000:0001` (link-local)

### 6.5 IPv6 address types

| Type | Prefix | Scope | Purpose |
|---|---|---|---|
| Global Unicast | 2000::/3 | Internet | Globally routable |
| Link-Local | fe80::/10 | Single link | Auto-configured; neighbor discovery |
| Unique Local | fc00::/7 | Organization | Like RFC 1918 private addresses |
| Multicast | ff00::/8 | Varies | Replaces broadcast |
| Loopback | ::1/128 | Host | Equivalent to 127.0.0.1 |

Every IPv6 interface has at least two addresses: a link-local address (auto-generated, always present) and typically a global unicast address. There is no broadcast in IPv6 — all one-to-many communication uses multicast (ff02::1 = all nodes, ff02::2 = all routers).

### 6.6 IPv6 address allocation hierarchy and the /64 boundary

| From | To | Typical Prefix | What It Provides |
|---|---|---|---|
| RIR (e.g., ARIN) | ISP | /32 (or /29) | 65,536 customer /48 blocks |
| ISP | Enterprise | /48 | 65,536 subnets (each a /64) |
| ISP | Home / small site | /48 or /56 | 256–65,536 subnets |
| Customer | Single subnet | /64 | \(2^{64} \approx 1.8 \times 10^{19}\) host addresses |

The **/64 subnet size is mandatory** in IPv6. SLAAC and Neighbor Discovery Protocol both assume the host portion is exactly 64 bits. Contrast with IPv4 where address conservation drives variable subnet sizes; IPv6's design philosophy shifted to "allocate generously and keep the hierarchy clean."

### 6.7 Transition mechanisms

- **Dual stack:** Hosts and routers run both IPv4 and IPv6 simultaneously. DNS returns both A and AAAA records; the host chooses (modern systems prefer IPv6 via the "Happy Eyeballs" algorithm, RFC 8305).
- **Tunneling (6in4, 6to4, Teredo):** IPv6 packets are encapsulated inside IPv4 packets to cross IPv4-only segments.
- **NAT64 / DNS64:** Translates between IPv6-only clients and IPv4-only servers. Maps IPv4 addresses into the special IPv6 prefix 64:ff9b::/96. Used by mobile carriers running IPv6-only internally.

### 6.8 The reality of IPv6 deployment

The IPv4-to-IPv6 transition has been the longest upgrade in internet history — over 25 years. NAT unexpectedly extended IPv4's life; enterprise adoption stalled because IPv4 + NAT works fine. **Mobile carriers** drove actual deployment by running out of IPv4 addresses first. T-Mobile US runs over 90% IPv6 traffic; Reliance Jio (India) launched as IPv6-first. As of 2025, approximately 45% of Google traffic arrives over IPv6, extremely unevenly distributed across countries.

---

## 7. Lecture 17 — DHCP

### 7.1 The bootstrap problem

When a host first connects to a network, it has no IP address, no subnet mask, no default gateway, and no DNS server. **DHCP (Dynamic Host Configuration Protocol)** automates configuration: a DHCP server hands out addresses and parameters to requesting hosts.

### 7.2 The DORA four-step process

1. **Discover:** The client broadcasts (destination 255.255.255.255, source 0.0.0.0) because it knows no server address and has no IP of its own.
2. **Offer:** The server responds with an available IP address, subnet mask, default gateway, DNS server addresses, and a lease duration.
3. **Request:** The client accepts the offer. Also broadcast so other DHCP servers know the address was claimed.
4. **Ack:** The server confirms the assignment. The client uses the address for the lease duration.

**Leases** enable address reuse — clients must renew before expiry or the address returns to the pool. **Relay agents** (typically the router) forward DHCP broadcasts as unicast to the server when the DHCP server is on a different subnet. DHCP uses **UDP — port 67 (server) and port 68 (client)**; it cannot use TCP because the client has no IP address to establish a TCP connection.

### 7.3 IPv6: SLAAC and DHCPv6

- **SLAAC (Stateless Address Auto-Configuration):** The host generates its own global address from the network prefix (advertised by the router via Router Advertisement messages) and a host identifier (from the MAC address or generated randomly for privacy). No DHCP server needed.
- **DHCPv6:** Works in "stateful" mode (assigns addresses) or "stateless" mode (provides only DNS servers while SLAAC handles the address).

Most IPv6 networks use SLAAC for address assignment and either SLAAC options or DHCPv6 for DNS configuration.

---

## 8. Lecture 17 — Summary

| Topic | Key Takeaway |
|---|---|
| IPv4 header | 20-byte base with TTL (hop counter), Protocol (demux key), Source/Dest addresses; DSCP for QoS |
| ICMP | Error reporting (Destination Unreachable, Time Exceeded) and diagnostics (Echo Request/Reply) — the protocol behind ping and traceroute |
| Fragmentation | Router fragmentation is problematic; PMTUD avoids it; IPv6 bans in-transit fragmentation entirely |
| NAT | Saved IPv4 from address exhaustion but broke end-to-end communication; uses port translation |
| IPv6 | 128-bit addresses, simplified fixed header, no broadcast; real adoption driven by mobile carriers |
| DHCP | Discover/Offer/Request/Ack; IPv6 adds SLAAC for stateless auto-configuration |

---

## 9. Lecture 18 — The Transport Layer

### 9.1 Process-to-process communication

The network layer (IP) moves datagrams from one **host** to another on a best-effort basis. But **processes**, not machines, send and receive data. A single host may simultaneously run a web browser, an SSH client, a video call, and a background update. The **transport layer** closes this gap by providing process-to-process communication on top of IP's host-to-host service.

In the 5-layer Internet model, the transport layer is layer 4, sitting between the network layer (layer 3) and the application layer (layer 5). The IPv4 Protocol field is the explicit handoff: TCP = 6, UDP = 17, ICMP = 1.

| Layer | Name (5-layer) | Protocol Data Unit |
|---|---|---|
| 5 | Application | Message / stream |
| 4 | Transport | Segment (TCP) / Datagram (UDP) |
| 3 | Network | Datagram (IP) |
| 2 | Link | Frame |
| 1 | Physical | Bits |

### 9.2 Multiplexing and demultiplexing

**Multiplexing** (at the sender): the transport layer gathers data from many application sockets, adds transport-layer headers including port numbers, and passes segments down to the network layer.

**Demultiplexing** (at the receiver): the transport layer examines incoming segments, reads the destination port number, and routes each segment to the correct socket.

**Ports** are 16-bit unsigned integers identifying a transport-layer endpoint on a host:

| Range | Name | Notes |
|---|---|---|
| 0–1023 | Well-known | Assigned by IANA; requires elevated privileges to bind |
| 1024–49151 | Registered | Assigned by IANA on request |
| 49152–65535 | Ephemeral | Assigned dynamically by the OS for the client side |

Selected well-known ports:

| Port | Protocol | Service |
|---|---|---|
| 22 | TCP | SSH |
| 53 | TCP/UDP | DNS |
| 67 | UDP | DHCP (server) |
| 68 | UDP | DHCP (client) |
| 80 | TCP | HTTP |
| 123 | UDP | NTP |
| 443 | TCP | HTTPS |

### 9.3 Sockets and the 5-tuple

The OS represents a transport-layer endpoint as a **socket**. Every socket is identified by a 5-tuple:

```
(protocol, local IP, local port, remote IP, remote port)
```

**UDP demultiplexing key:** (destination IP, destination port) — two UDP datagrams arriving at the same destination port from different sources land in the **same socket**.

**TCP demultiplexing key:** the full 5-tuple — this is what allows a web server to maintain thousands of simultaneous TCP connections all arriving at port 443; each has a different source IP or port, mapping to a distinct socket.

---

## 10. Lecture 18 — UDP

### 10.1 Design philosophy

UDP extends IP's best-effort philosophy up one layer. Reliability, ordering, duplicate detection, and flow control are the **application's problem**, not the protocol's. For applications needing tight latency control, that perform their own retransmission, or that use UDP as a building block for higher-level transports, the absence of protocol-level mechanisms is an advantage.

### 10.2 The UDP header

The UDP header is **8 bytes**, consisting of four 16-bit fields:

```
| Source Port (16 bits) | Destination Port (16 bits) |
|   Length (16 bits)    |    Checksum (16 bits)      |
```

- **Source port:** identifies the sending socket; used by the receiver to reply
- **Destination port:** demultiplexing key at the receiver
- **Length:** length in bytes of UDP header plus data (minimum 8)
- **Checksum:** error detection over the segment

What UDP does **not** provide: delivery guarantee, ordering, duplicate detection, congestion control, or connection setup. Entire on-wire overhead: **8 bytes** vs. 20–60 bytes for TCP.

### 10.3 The UDP checksum

Computed using **ones'-complement addition** over a **pseudo-header** — a synthetic structure including source IP, destination IP, a zero byte, protocol number (17), and UDP length — followed by the UDP header and data padded to an even number of bytes. Including IP addresses guards against misdelivered datagrams: a packet forwarded to the wrong host due to a corrupted IP header will fail the UDP checksum even if the UDP header itself is intact.

This is the same ones'-complement principle as the IPv4 header checksum: minimum Hamming distance \(d_{min} = 2\), meaning all single-bit errors are detected. In IPv4, the checksum is **optional** (0x0000 = no checksum). In **IPv6, the UDP checksum is mandatory**, because the IPv6 header carries no checksum.

### 10.4 When UDP is the right choice

| Situation | Reason UDP wins |
|---|---|
| Low-latency interactive (VoIP, gaming) | A retransmitted voice packet arriving 200 ms late is useless — better to discard and play silence |
| Query-response protocols (DNS, NTP, DHCP) | A TCP handshake (≥1 full RTT) would double the latency of a name lookup |
| Multicast and broadcast | TCP is point-to-point; it cannot multicast |
| Application-controlled reliability (QUIC, WebRTC) | Fine-grained control that TCP's kernel implementation cannot provide |
| UDP tunnels (WireGuard) | Avoids TCP-over-TCP pathology — inner and outer TCP retransmissions interact badly |

---

## 11. Lecture 18 — Reliable Data Transfer

### 11.1 The problem

An unreliable channel can corrupt bits (detectable by checksum) or **lose packets entirely** (a checksum cannot help — there is nothing to check). An RDT protocol must handle both. The building blocks:

- **Checksums:** detect bit errors in received packets
- **Acknowledgments (ACKs):** positive feedback from receiver to sender
- **Sequence numbers:** detect duplicates and reorder out-of-order deliveries
- **Timers:** if no ACK arrives before expiry, the sender retransmits

### 11.2 Stop-and-Wait (Alternating Bit Protocol)

The simplest ARQ protocol: the sender transmits one packet and waits for an ACK before transmitting the next. Only a **1-bit sequence number** is needed — the receiver only needs to distinguish "expected next" from "retransmit of already delivered."

**Three failure scenarios:**

- **Data packet lost:** timer fires, sender retransmits; clean.
- **ACK lost:** data was delivered, but sender retransmits due to timeout. Without sequence numbers the receiver cannot tell new data from a retransmit and would deliver it twice — a correctness failure. With a 1-bit sequence number, the receiver discards the duplicate and re-sends ACK 0.
- **Corrupted packet:** checksum detects corruption; receiver sends NAK (or re-sends last ACK); sender retransmits.

**Core correctness requirement:** the receiver must be able to distinguish new data from a retransmit. This is why sequence numbers are necessary even when a 1-bit label is sufficient.

### 11.3 Stop-and-Wait utilization

Stop-and-Wait is correct but can be extraordinarily inefficient:

\[
U = \frac{t_{tx}}{\text{RTT} + t_{tx}}
\]

**Example — satellite link:** \(B = 1\) Gb/s, RTT = 600 ms, packet size = 1,500 bytes = 12,000 bits.

\[
t_{tx} = \frac{12{,}000 \text{ bits}}{10^9 \text{ bits/s}} = 12\ \mu\text{s}
\]
\[
U = \frac{12 \times 10^{-6}}{600 \times 10^{-3} + 12 \times 10^{-6}} \approx 0.002\%
\]

A 1 Gb/s link delivers approximately **20 kb/s** of useful throughput. The link is idle more than 99.998% of the time.

---

## 12. Lecture 18 — Bandwidth-Delay Product and Pipelining

The **bandwidth-delay product** \(\text{BDP} = B \times \text{RTT}\) is the number of bits that can be "in flight" on the link at once. For the satellite example: \(\text{BDP} = 1\ \text{Gb/s} \times 600\ \text{ms} = 600\ \text{Mb}\).

Stop-and-Wait keeps exactly one packet (12,000 bits) in flight out of 600,000,000 bits of pipe capacity. To fully utilize the link, the sender would need to keep roughly:

\[
W = \frac{\text{BDP}}{\text{packet size}} = \frac{600 \times 10^6}{12{,}000} = 50{,}000 \text{ packets}
\]

simultaneously in flight. **Pipelining** is the solution: the sender maintains a **window** of up to \(N\) outstanding (sent but not yet acknowledged) packets.

---

## 13. Lecture 18 — Go-Back-N

In **Go-Back-N (GBN)**, the sender maintains a window of up to \(N\) unacknowledged packets. Key design choices:

- **Cumulative ACKs:** ACK\(n\) means "I have received all packets through sequence number \(n\) correctly." The sender advances the window base to \(n+1\).
- **Single timer:** covers the oldest unacknowledged packet. If it fires, the sender retransmits **all** packets currently in the window.
- **Receiver discard:** the receiver accepts packets only in order. Out-of-order packets are discarded and an ACK for the last in-order packet is re-sent. No receiver buffering required.

**Sequence number constraint:** with \(k\)-bit sequence numbers, the GBN window size must satisfy \(N \leq 2^k - 1\). One sequence number is reserved to unambiguously identify the window boundary.

**Trace with packet loss (window \(N=4\), packet 2 lost):**

1. Sender transmits packets 0, 1, 2, 3 (filling the window).
2. Receiver gets packets 0 and 1, sends ACK 0 and ACK 1.
3. Packet 2 is lost.
4. Receiver gets packet 3 (out of order), discards it, and re-sends ACK 1.
5. Timer for packet 2 expires.
6. Sender retransmits packets **2, 3, 4, 5** — the entire outstanding window.

One lost packet causes retransmission of the entire outstanding window.

---

## 14. Lecture 18 — Selective Repeat

**Selective Repeat (SR)** fixes GBN's retransmit-the-whole-window policy. The receiver **buffers** out-of-order packets; the sender retransmits **only the specific lost packet**. Key design choices:

- **Individual ACKs:** the receiver sends ACK\(n\) for each correctly received packet, whether or not in order.
- **Individual timers:** the sender maintains a separate timer per outstanding packet.
- **Receiver buffer:** packets within the receive window are buffered until any gap below them is filled; when the in-order frontier advances, buffered packets are delivered to the application.
- **Duplicate handling:** if a packet below the current window arrives (already delivered), the receiver re-sends an ACK for it so the sender's retransmit timer can be cleared.

**Sequence number constraint:** \(N \leq 2^{k-1}\). This is stricter than GBN's. If the window were larger, the receiver could not distinguish a new packet (from the next window) from a retransmit of an already-delivered packet. With \(N = 2^{k-1}\), new-window sequence numbers always differ by at least \(N\) from already-delivered ones, making the ranges disjoint.

**Trace with packet loss (same scenario — window \(N=4\), packet 2 lost):**

1. Sender transmits packets 0, 1, 2, 3.
2. Receiver gets packets 0 and 1, sends ACK 0 and ACK 1.
3. Packet 2 is lost.
4. Receiver gets packet 3, **buffers** it, sends ACK 3.
5. Sender's timer for packet 2 expires. Sender retransmits **only packet 2**.
6. Receiver gets packet 2, fills the gap, delivers packets 2 and 3 to the application, slides its window forward.

One lost packet causes exactly **one retransmission**.

---

## 15. Lecture 18 — Go-Back-N vs. Selective Repeat, and the Road to TCP

### 15.1 Comparison

| Property | Go-Back-N | Selective Repeat |
|---|---|---|
| Receiver buffer | None (discard OOO) | Required (buffer OOO pkts) |
| Retransmit on loss | Entire window | Lost packet only |
| ACK type | Cumulative | Individual |
| Timers at sender | One (oldest unACKed) | One per outstanding packet |
| Seq. num. constraint | \(N \leq 2^k - 1\) | \(N \leq 2^{k-1}\) |
| Best when | Low loss, simple receiver | Higher loss, can buffer |

### 15.2 What TCP inherits

TCP is not a pure implementation of either protocol — it takes the best ideas from both:

- **Cumulative ACKs (GBN style):** an ACK for byte offset \(n\) confirms receipt of all bytes through \(n\). This simplicity has always been part of TCP's base specification.
- **Receiver buffer (SR style):** arriving segments are held until gaps below them are filled. Without buffering, every gap would force a full retransmit-the-window like GBN.
- **SACK option (SR style):** when the Selective Acknowledgment TCP option is negotiated, the receiver explicitly reports which byte ranges it has already received. The sender retransmits only the specific missing segments. SACK is supported by essentially all modern operating systems and is enabled by default in Linux, macOS, and Windows.

**In summary:** TCP's default behavior closely resembles GBN (cumulative ACKs, single retransmit timer), but with a receiver buffer and SACK it behaves more like SR. This hybrid design is one reason TCP performs well across such a wide range of network conditions.

### 15.3 What comes next

Stop-and-Wait, GBN, and SR answer how to deliver data reliably. A complete transport protocol must also answer:

- **Flow control:** what if the receiver's buffer is full? The sender must slow down.
- **Congestion control:** what if the network itself is overloaded? The sender must slow down for a different reason.
- **Connection management:** how do two processes agree to start communicating, and how do they cleanly terminate?
- **Byte-stream semantics:** TCP is a stream protocol, not a message protocol.

Lecture 19 addresses all of these and completes the TCP picture.

---

## 16. What's Next (from the slides)

**Lecture 17 "What's Next"** listed: L18 Wireshark lab tying together all network-layer protocols: ICMP, IPv4/IPv6 headers, DHCP, and NAT.

**Lecture 18 "What's Next"** listed: L19 TCP — flow control, congestion control, connection management, and byte-stream semantics.
