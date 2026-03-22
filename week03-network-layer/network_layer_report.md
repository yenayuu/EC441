# Week 03 — The Network Layer: Forwarding, Routing, and IP Addressing

**Course:** EC 441, Spring 2026

**Type:** Report

**Topic:** Network Layer — forwarding vs. routing, router architecture, longest-prefix match, SDN, IP addressing, CIDR, subnetting

---

## 1. Introduction

The physical and data link layers deliver frames one hop at a time — Ethernet moves a frame from a laptop to a campus router, and WiFi moves a frame from a phone to an access point. Neither has any notion of end-to-end delivery across the internet. The network layer solves this harder problem: getting a packet from a source host to a destination host that may be many hops away, traversing heterogeneous link technologies along the path.

IP (Internet Protocol) sits at the "narrow waist" of the internet's hourglass architecture — the single protocol that every application runs on top of, and that runs on top of every link technology. Its design is deliberately simple: best-effort, connectionless, and universal. This report covers how the network layer fulfills its three core responsibilities — addressing, forwarding, and routing — and dives into IP addressing, CIDR, and subnetting in detail.

---

## 2. The Narrow Waist and IP's Design Philosophy

The internet's protocol stack forms an hourglass shape with IP at the center:

```
Applications:   HTTP, DNS, SMTP, SSH, video, ...
Transport:      TCP, UDP, QUIC
                    IP  ← narrow waist
Link:           Ethernet, WiFi, LTE, cable, ...
Physical:       copper, radio, fiber, ...
```

Three properties define IP's abstraction:

| Property | Description |
|---|---|
| **Best-effort** | No guaranteed delivery, ordering, or timing. Reliability is TCP's job, not IP's. |
| **Connectionless** | Each packet is forwarded independently — no setup phase, no circuit, no per-flow state. |
| **Universal** | Runs on every device (routers, hosts, phones, IoT) and over every link technology. |

This simplicity is a feature. By being best-effort and connectionless, IP can be implemented on any new link technology and lets each transport protocol decide its own reliability semantics.

### The End-to-End Argument

IP's best-effort design is justified by the **end-to-end argument** (Saltzer, Reed, Clark, 1984): if a function requires application-specific knowledge to implement correctly, it must be implemented at the endpoints. Building reliability into the network is redundant because the application still needs to verify correctness anyway. Therefore, reliability is implemented once in TCP at the endpoints, not duplicated at every hop.

Applied concretely: even if every router verified delivery, the application would still need to confirm that data arrived at the correct process, was interpreted correctly, and that the session is valid. The network cannot know what "received correctly" means for an arbitrary application.

---

## 3. Historical Alternatives: X.25 and ATM

Best-effort was not the only vision for the network layer. Two major alternatives tried to build reliability and QoS into the network fabric.

| Technology | Era | Approach | Why it lost |
|---|---|---|---|
| **X.25** | 1976–1990s | Connection-oriented, reliable, sequenced delivery; per-connection state at every switch | Expensive and fragile at scale; ITU standards body moved slowly |
| **ATM** | 1980s–1990s | Fixed 53-byte cells, hardware-switched at line rate, QoS guarantees | 10% header overhead (5 B header / 48 B payload); complex; lost to IP over Fast/Gigabit Ethernet |

The outcome illustrates a lasting principle: **"good enough" beats "perfect."** IP won because it was simple enough to run on commodity hardware, implement quickly on any link technology, deploy without per-connection state, and iterate on rapidly. The telecom mindset (guarantee everything in the network) lost to the internet mindset (keep the network simple, push complexity to endpoints, run on cheap hardware).

---

## 4. Three Responsibilities of the Network Layer

| Responsibility | Scope | Timescale | Plane |
|---|---|---|---|
| **Addressing** | Globally unique identifiers for every host | Static/semi-static | — |
| **Forwarding** | Per-packet: which output port? | Nanoseconds | Data plane |
| **Routing** | Network-wide: compute forwarding tables | Seconds to minutes | Control plane |

### Forwarding (data plane)

At each router, given an incoming packet, decide which output port to send it on. This is a local, per-packet decision using the forwarding table. A router on a 100 Gb/s link must make a forwarding decision every ~120 ns for 1500-byte packets. Forwarding is implemented in specialized hardware (ASICs, NPUs) because software cannot keep pace at line rate.

### Routing (control plane)

Across the network, compute what the forwarding tables should contain so packets reach their destinations efficiently. Routing protocols (OSPF, BGP, RIP) run on general-purpose CPUs because correctness matters more than speed. They operate over seconds to minutes.

The analogy: **forwarding** is following GPS turn-by-turn directions at each intersection; **routing** is computing the entire route before you leave.

---

## 5. Data Plane vs. Control Plane

Every router performs two functions on fundamentally different timescales:

| | Data Plane (Fast Path) | Control Plane (Slow Path) |
|---|---|---|
| **Speed** | Nanoseconds–microseconds per packet | Seconds–minutes |
| **Job** | Receive packet → lookup destination → forward | Build and maintain forwarding tables |
| **Hardware** | ASICs, NPUs, TCAM | General-purpose CPU |
| **Character** | Dumb but fast — executes the table | Smart but slow — computes the strategy |

The separation matters for three reasons:

1. **Failure isolation:** If the routing protocol crashes, packets in flight continue forwarding using last-known-good tables.
2. **Different optimization targets:** Data-plane hardware optimizes throughput/latency; control-plane software optimizes correctness/flexibility.
3. **Enables SDN:** If the control plane is separate, it doesn't have to run inside the router — it can run on a centralized server with a global network view.

### RIB vs. FIB

The control plane builds the **Routing Information Base (RIB)** — the full routing table with redundancy, preferences, and policy. From the RIB, a pruned, hardware-optimized subset is installed into the **Forwarding Information Base (FIB)**, stored in TCAM, which the data plane consults per packet.

---

## 6. Router Architecture

A high-end router (Cisco CRS-X, Juniper PTX) forwarding tens of terabits per second has four main components:

```
           Routing Processor
     (control plane: OSPF, BGP → builds RIB, installs FIB)
                  |
     ┌────────────┴────────────┐
     │      Switching Fabric     │
     │ (crossbar or shared mem)  │
     └──┬────┬────┬────┬────┬──┘
        │    │    │    │    │
      In/Out In/Out In/Out ...
      Port 1 Port 2 Port 3
```

| Component | Function |
|---|---|
| **Input ports** | Physical layer receives bits; link layer strips frame header and checks FCS; FIB lookup determines output port; small queue buffers packets while fabric is busy |
| **Switching fabric** | Interconnects all input/output ports; must exceed aggregate input rate or it bottlenecks; crossbar (n×n) in high-end, shared-memory bus in lower-cost routers |
| **Output ports** | Receive packets from fabric, queue to absorb bursts, add outgoing link-layer header, transmit bits |
| **Routing processor** | Runs OSPF, BGP, and other protocols; maintains RIB; installs FIB entries to line cards |

### Queuing and Packet Loss

Queues form at output ports when packets arrive faster than the link drains them. When a queue overflows, packets are dropped — this is the fundamental mechanism of internet congestion. TCP detects drops and reduces its sending rate.

| Policy | Behavior |
|---|---|
| **Tail drop** | When queue is full, discard the newest arriving packet |
| **RED** (Random Early Detection) | Drop packets probabilistically *before* the queue fills, providing early congestion signals and avoiding global synchronization |

**Head-of-line (HOL) blocking** occurs at input ports with FIFO queuing: a packet waiting for a busy output port blocks all packets behind it, even those destined for free ports. The fix is **Virtual Output Queues (VOQ)** — a separate queue at each input port for each output port.

---

## 7. Longest-Prefix Match

IP addresses are hierarchical: a routing table entry for `10.0.0.0/8` covers 16 million addresses, while `10.1.2.0/24` covers only 256. A destination address can match multiple entries simultaneously.

> **Longest-Prefix Match Rule:** When a destination matches more than one forwarding table entry, always use the entry with the longest (most specific) prefix. A more specific entry was installed precisely to handle that narrower range.

### Worked Example

| Prefix | Length | Next Hop | Interface |
|---|---|---|---|
| `0.0.0.0/0` | 0 | 203.0.113.1 | eth0 (default) |
| `10.0.0.0/8` | 8 | 10.255.0.1 | eth1 |
| `10.1.0.0/16` | 16 | 10.1.255.1 | eth2 |
| `10.1.2.0/24` | 24 | 10.1.2.254 | eth3 |
| `192.168.0.0/16` | 16 | 192.168.0.1 | eth4 |

- **Destination `10.1.2.5`:** Matches `/0`, `/8`, `/16`, and `/24`. Longest match → `10.1.2.0/24` → forward out **eth3**.
- **Destination `10.5.6.7`:** Matches `/0` and `/8`. Longest match → `10.0.0.0/8` → forward out **eth1**.
- **Destination `172.16.0.1`:** Matches only `/0`. Default route → forward out **eth0**.

In hardware, longest-prefix match is performed by **TCAM** (Ternary Content-Addressable Memory): each entry is stored as a (value, mask) pair where each bit can be 0, 1, or X (don't care). TCAM searches all entries in parallel in a single clock cycle — expensive in power and die area, but necessary at line rate.

---

## 8. Forwarding in Action: Step by Step

For each arriving packet, the data plane executes:

1. **Receive** bits on the input interface; strip the link-layer header to reconstruct the IP packet.
2. **Verify** the IP header checksum. If it fails, drop silently. Decrement the **TTL** by 1. Recompute the checksum.
3. **Check TTL:** If TTL = 0, drop the packet and send an **ICMP Time Exceeded** message to the source (loop prevention).
4. **Lookup** the destination IP in the forwarding table using longest-prefix match → output interface and next hop.
5. **Send** the packet out the matched interface. If the link is Ethernet, ARP resolves the next-hop IP to a MAC address.

### TTL and Traceroute

The **Time to Live** field is an 8-bit counter (initial values: 64 on Linux, 128 on Windows, 255 on Cisco). Each router decrements it by 1. When observed TTL is 54 from a Google server (initial 64), the path is approximately 10 hops.

`traceroute` exploits TTL by sending probes with TTL = 1, 2, 3, ... Each router that decrements TTL to 0 sends back an ICMP Time Exceeded message, revealing its address. Lines showing `* * *` mean a router silently drops TTL-expired packets (firewall policy), not that the path is broken.

---

## 9. Software-Defined Networking (SDN)

Traditional routing embeds the control plane in every router — each independently running Dijkstra or BGP path selection with only a local view. **Software-Defined Networking** extracts the control plane to a logically centralized controller with a global view of the network.

```
        SDN Controller
   (centralized; globally aware)
       /       |       \
   Switch 1  Switch 2  Switch 3
   (dumb      (dumb      (dumb
   forwarder) forwarder) forwarder)
```

**OpenFlow** is the original SDN protocol: the controller pushes flow table rules to switches (e.g., "if destination IP matches `10.1.2.0/24`, send out port 3"). Switches simply match packets against rules and act — no routing protocol runs in the switch.

### Where SDN runs

| Deployment | Description |
|---|---|
| **Google B4** | Centralized traffic engineering for Google's WAN; achieves near-100% link utilization vs. 30–40% with OSPF |
| **AWS VPC** | All virtual networking inside AWS uses SDN; no traditional routing between instances |
| **Meta / Azure** | Similar SDN-based fabric architectures |

SDN does **not** run the open internet. BGP and OSPF still power the internet's core — no single entity can control routing across thousands of independent organizations. SDN works because it is scoped to infrastructure controlled by a single organization (a data center, a campus, an enterprise WAN).

---

## 10. IPv4 Addressing: One Address, Two Jobs

An IPv4 address is 32 bits encoding two pieces of information:

```
|← network bits (N) →|← host bits (32−N) →|
        routing              host identity
```

The prefix length `/N` specifies where the split occurs. This enables **hierarchical routing**: a router in Tokyo needs to know only "send BU-destined packets this way" (`128.197.0.0/16`), not the identity of every host at BU.

### Dotted-decimal notation

The 32 bits are split into four 8-bit octets, each written as a decimal 0–255:

```
Binary:         10000000.11000101.00001010.00101010
Dotted-decimal: 128     .197     .10      .42
```

---

## 11. Classful Addressing and Its Failure

From 1981 to 1993, IPv4 addresses were allocated in fixed classes:

| Class | Leading bits | Default prefix | Hosts/net | Address range |
|---|---|---|---|---|
| A | `0` | /8 | 16.7 M | 0.x.x.x – 127.x.x.x |
| B | `10` | /16 | 65,534 | 128.x.x.x – 191.x.x.x |
| C | `110` | /24 | 254 | 192.x.x.x – 223.x.x.x |
| D | `1110` | — | multicast | 224.x.x.x – 239.x.x.x |
| E | `1111` | — | reserved | 240.x.x.x – 255.x.x.x |

BU's `128.197.0.0/16` is a Class B block from this era.

### Why classful addressing failed

**Problem 1 — Address waste:** The binary choice between Class B (65K hosts) and Class C (254 hosts) matched almost no real organization. A university needing 5,000 addresses received a /16 with 65K addresses — 60,000 wasted. By 1993, roughly half of all assigned IPv4 space sat unused.

**Problem 2 — Routing explosion:** A medium company needing 2,000 hosts but denied a Class B received 8 separate Class C blocks. Each required its own global routing table entry — no aggregation was possible. The global routing table grew exponentially; router hardware could not keep up.

---

## 12. CIDR: The Fix

**Classless Inter-Domain Routing** (RFC 1519, 1993) made three changes:

1. **Any prefix length is valid** — /19, /22, /27, whatever fits.
2. **Prefix length is written explicitly** — `192.168.1.0/24`, not "Class C, therefore /24."
3. **Aggregation is first-class** — adjacent blocks with a common prefix collapse into one shorter-prefix entry (supernetting).

Before CIDR, 8 separate `/24` routing entries. After CIDR, one aggregated `192.168.0.0/21` covering all 8 (2,048 addresses). This reduced the global routing table from an explosive trajectory to a manageable one, buying roughly a decade before IPv4 exhaustion became critical.

### Subnet masks and prefix lengths

A CIDR prefix is equivalent to a subnet mask — N ones followed by (32 − N) zeros:

| Prefix | Mask | Total addresses | Usable hosts | Typical use |
|---|---|---|---|---|
| /30 | 255.255.255.252 | 4 | 2 | Point-to-point links |
| /26 | 255.255.255.192 | 64 | 62 | Small office |
| /24 | 255.255.255.0 | 256 | 254 | Standard LAN segment |
| /22 | 255.255.240.0 | 1,024 | 1,022 | Large campus segment |
| /16 | 255.255.0.0 | 65,536 | 65,534 | Large organization |

Usable hosts = \(2^{32-N} - 2\) (subtract the network address and broadcast address).

---

## 13. Subnetting

**Subnetting** divides an address block into smaller segments by extending the prefix length. Borrowing \(k\) bits from the host portion creates \(2^k\) subnets, each a \(/(N+k)\).

### Worked Example

Divide `192.168.10.0/24` into 4 subnets:

Borrow 2 bits → \(2^2 = 4\) subnets, new prefix = /26, each with 64 addresses (62 usable).

| Subnet | Prefix | Host range | Usable hosts |
|---|---|---|---|
| 0 (Engineering) | `192.168.10.0/26` | .1 – .62 | 62 |
| 1 (Sales) | `192.168.10.64/26` | .65 – .126 | 62 |
| 2 (HR) | `192.168.10.128/26` | .129 – .190 | 62 |
| 3 (IT) | `192.168.10.192/26` | .193 – .254 | 62 |

Check: 4 × 64 = 256 — the entire /24 is accounted for.

### Key computations for any prefix

Given an address and prefix length:

- **Network address** = address AND mask (all host bits zeroed)
- **Broadcast address** = all host bits set to 1
- **Usable range** = network + 1 through broadcast − 1

**Alignment rule:** A valid subnet's network address must be a multiple of the block size. For /26 (block size 64): valid starts are .0, .64, .128, .192. An address like `192.168.1.10/26` is invalid because .10 is not a multiple of 64.

### Subnet membership check

To determine if two hosts are in the same subnet, AND each address with the mask and compare:

- `192.168.10.75 AND 255.255.255.192` → `192.168.10.64`
- `192.168.10.100 AND 255.255.255.192` → `192.168.10.64` → **same subnet**

- `192.168.10.75 AND 255.255.255.192` → `192.168.10.64`
- `192.168.10.130 AND 255.255.255.192` → `192.168.10.128` → **different subnets, must route**

Hosts in different subnets cannot communicate directly — traffic must pass through a router, even if both are on the same floor of the same building. Subnet boundaries are logical, not physical.

---

## 14. Variable-Length Subnet Masking (VLSM)

Subnets within an organization don't need to be equal-sized. VLSM allows different prefix lengths for different parts of the address space, matching allocation to actual need.

| Use | Hosts needed | Prefix | Block |
|---|---|---|---|
| Lab network | 120 | /25 (126 usable) | `192.168.20.0/25` |
| Faculty offices | 50 | /26 (62 usable) | `192.168.20.128/26` |
| Staff | 20 | /27 (30 usable) | `192.168.20.192/27` |
| Router link | 2 | /30 (2 usable) | `192.168.20.224/30` |

VLSM is efficient but requires careful bookkeeping to avoid overlaps. The alignment rule (each block starts at a multiple of its block size) keeps things tidy.

---

## 15. Special-Purpose IPv4 Ranges

### RFC 1918 — Private Address Space

Three blocks are designated as private — never routed on the public internet, reusable by any organization behind NAT:

| Block | Range | Size | Typical use |
|---|---|---|---|
| `10.0.0.0/8` | 10.0.0.0 – 10.255.255.255 | 16M | Enterprise, cloud VPCs |
| `172.16.0.0/12` | 172.16.0.0 – 172.31.255.255 | 1M | Medium enterprise |
| `192.168.0.0/16` | 192.168.0.0 – 192.168.255.255 | 65K | Home networks, small offices |

### Other notable ranges

| Range | Purpose |
|---|---|
| `127.0.0.0/8` | Loopback — `127.0.0.1` = localhost; packets never leave the host |
| `169.254.0.0/16` | Link-local (APIPA) — auto-assigned when DHCP fails; not routable |
| `224.0.0.0/4` | Multicast (OSPF uses 224.0.0.5/6; RIP uses 224.0.0.9) |
| `255.255.255.255` | Limited broadcast — all hosts on local subnet; not forwarded by routers |
| `0.0.0.0` | "This host" — used in DHCP Discover before an address is assigned |
| `100.64.0.0/10` | Carrier-Grade NAT (RFC 6598) — ISP-internal, not on public internet |

---

## 16. IPv4 Allocation and Exhaustion

IPv4 addresses flow through a four-level hierarchy:

```
IANA (Internet Assigned Numbers Authority)
  └── RIRs: ARIN, RIPE NCC, APNIC, LACNIC, AFRINIC
        └── ISPs and Large Organizations
              └── End Users
```

With only \(2^{32} \approx 4.3\) billion addresses, exhaustion was inevitable:

| Event | Date |
|---|---|
| IANA exhausts free pool | February 2011 |
| APNIC (Asia-Pacific) | April 2011 |
| RIPE NCC (Europe) | September 2012 |
| LACNIC (Latin America) | June 2014 |
| ARIN (North America) | September 2015 |
| AFRINIC (Africa) | 2021 |

New IPv4 addresses are no longer available from RIRs. They trade on the transfer market at \$30–50 per address. NAT — one public IP representing thousands of private hosts — extended IPv4's life by roughly 20 years beyond original projections.

---

## 17. Conclusion

The network layer bridges the gap between single-hop link-layer delivery and the end-to-end connectivity the internet provides. IP's deliberately simple, best-effort design won against more complex alternatives (X.25, ATM) because simplicity enables rapid deployment on commodity hardware and effortless adaptation to new link technologies. Within the network layer, the clean separation of forwarding (fast, hardware, per-packet) from routing (slow, software, network-wide) enables both high performance and architectural flexibility — including SDN, which moves the control plane out of the router entirely.

IP addressing ties the system together: hierarchical addresses with CIDR prefixes enable scalable routing through aggregation, while subnetting gives organizations flexible control over their address space. Understanding these mechanisms — how routers forward packets, how addresses are structured, and how subnets are divided — is essential for working with any IP network.

---

## Key Takeaways

1. **IP is the narrow waist** — best-effort, connectionless, universal; simplicity is the design, not a limitation.
2. **End-to-end argument** — reliability belongs at the endpoints (TCP), not in the network.
3. **Forwarding ≠ Routing** — forwarding is local/per-packet/nanoseconds (data plane); routing is network-wide/algorithmic/seconds (control plane).
4. **Router architecture** = input ports + switching fabric + output ports + routing processor; queuing at output ports is where congestion and packet loss occur.
5. **Longest-prefix match** — the most specific matching entry wins; implemented in TCAM hardware at line rate.
6. **SDN** centralizes the control plane for networks under single-organization control (cloud data centers), but does not run the open internet.
7. **Classful addressing failed** due to waste and routing explosion; **CIDR** (1993) fixed both with variable-length prefixes and aggregation.
8. **Subnetting** divides an address block by borrowing host bits; the alignment rule ensures valid network addresses.
9. **RFC 1918 private ranges** (10/8, 172.16/12, 192.168/16) are reusable behind NAT and form the backbone of internal networks.
10. **IPv4 is exhausted** — all RIRs have depleted their free pools; NAT extended its life, but IPv6 is the long-term solution.

---

*Report based on Lectures 13 and 14 of EC 441, Spring 2026.*
