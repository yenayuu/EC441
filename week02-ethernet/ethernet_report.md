# Week 02 — Ethernet: Addressing, Switching, and ARP

**Course:** EC 441, Spring 2026

**Type:** Report

**Topic:** Data Link Layer — Ethernet frame structure, MAC addresses, ARP, switching, subnets

---

## 1. Introduction

Ethernet is the dominant wired LAN technology, connecting billions of devices worldwide. Since its invention at Xerox PARC in 1973 by Bob Metcalfe and David Boggs, it has evolved from a shared 2.94 Mb/s coaxial bus to today's switched, full-duplex links running at 400 Gb/s over fiber — all while keeping the same basic frame format. This report covers the core mechanisms that make Ethernet work: frame structure, MAC addressing, address resolution (ARP), and switch-based forwarding.

---

## 2. Ethernet at the Physical Layer

Ethernet relies on **line codes** to transmit bits as electrical or optical signals. A good line code must provide three things:

| Property | Why it matters |
|---|---|
| **Clock recovery** | The receiver must stay synchronized with the sender without a separate clock wire |
| **DC balance** | No average voltage offset, so the signal can pass through transformers and AC-coupled links |
| **Bandwidth efficiency** | More bits per Hz means higher data rates within cable/fiber bandwidth limits |

Each Ethernet generation uses a progressively more efficient encoding:

| Generation | Line Code | Key Idea |
|---|---|---|
| 10 Mb/s (10BASE-T) | Manchester | Transition every bit period — self-clocking but costs 2x bandwidth |
| 100 Mb/s (100BASE-TX) | 4B5B + MLT-3 | Map 4 data bits to 5-bit codewords; 3 voltage levels cut bandwidth by 3x |
| 1 Gb/s (1000BASE-T) | PAM-5 | 5-level amplitude modulation on all 4 twisted pairs simultaneously |
| 10+ Gb/s | PAM-4 / DSP | 4-level PAM with digital signal processing and equalization |

**Manchester encoding** (used in original 10 Mb/s Ethernet) guarantees a mid-bit transition in every bit period: a rising edge for `1` and a falling edge for `0`. This makes clock recovery trivial but doubles the required signal bandwidth. The Ethernet preamble — seven bytes of `10101010` — produces a perfectly regular 10 MHz square wave in Manchester encoding, allowing the receiver's phase-locked loop (PLL) to lock onto the signal before data arrives.

---

## 3. Ethernet Frame Structure

Every Ethernet frame follows the same format, unchanged across all generations:

```
| Preamble + SFD | Dst MAC | Src MAC | Type  | Payload    | FCS  |
|     8 B        |   6 B   |   6 B   |  2 B  | 46–1500 B  |  4 B |
```

| Field | Size | Purpose |
|---|---|---|
| **Preamble** | 7 bytes | `10101010` × 7 — clock sync for receiver PLL |
| **SFD** | 1 byte | `10101011` — the two final `1`-bits signal "data starts now" |
| **Dst MAC** | 6 bytes | Destination hardware address |
| **Src MAC** | 6 bytes | Source hardware address |
| **Type** | 2 bytes | Identifies encapsulated protocol (`0x0800` = IPv4, `0x0806` = ARP, `0x86DD` = IPv6) |
| **Payload** | 46–1500 bytes | Data from higher layers; padded to 46 bytes if shorter |
| **FCS** | 4 bytes | CRC-32 checksum; frames with errors are silently dropped |

### Frame size constraints

- **Maximum:** 1518 bytes (1500-byte payload). This defines IP's Maximum Transmission Unit (MTU) of 1500 bytes.
- **Minimum:** 64 bytes (46-byte payload). Originally required by CSMA/CD so that a sender is still transmitting when a collision echo arrives. At 10 Mb/s with maximum cable length, the round-trip delay is 51.2 μs, giving $L_{\min} = 2\tau \times R = 51.2\;\mu\text{s} \times 10\;\text{Mb/s} = 512\;\text{bits} = 64\;\text{bytes}$. In modern full-duplex switched Ethernet, collisions cannot occur — the 64-byte minimum is a legacy artifact.
- **Interframe Gap (IFG):** 96 bits of silence after each frame, signaling the end of transmission.

---

## 4. MAC Addresses

A **MAC address** (Medium Access Control address, also called a hardware address or Burned-In Address) is a 48-bit identifier written in hex notation, e.g., `A4:C3:F0:85:AC:2D`.

### Structure

- **Bytes 1–3:** OUI (Organizationally Unique Identifier) — assigned to manufacturers by the IEEE (e.g., `A4:C3:F0` = Apple).
- **Bytes 4–6:** Device-specific, assigned by the manufacturer.
- **Special bits in byte 1:**
  - Bit 0 (I/G): `0` = unicast, `1` = multicast
  - Bit 1 (U/L): `0` = globally administered, `1` = locally administered
- **Broadcast address:** `FF:FF:FF:FF:FF:FF` — received by every device on the LAN.

### Flat vs. hierarchical addressing

| Property | MAC (flat) | IP (hierarchical) |
|---|---|---|
| Identifies | The hardware interface | A network location |
| Location info | None | Encoded in the prefix |
| Changes when device moves? | No | Yes (across subnets) |
| Used by | Switches (local delivery) | Routers (global routing) |

A critical insight: as a packet traverses the network, the **IP addresses stay the same** end-to-end, but the **MAC addresses change at every hop** — each link rewrites the Ethernet header for local delivery.

---

## 5. ARP — Address Resolution Protocol

### The problem

When Host A wants to send data to Host B on the same subnet, it knows B's IP address but needs B's MAC address to construct the Ethernet frame. ARP bridges this gap.

### The exchange

1. **ARP Request (broadcast):** Host A sends an Ethernet frame to `FF:FF:FF:FF:FF:FF` containing: *"I'm 192.168.1.10 (AA:AA:AA:AA:AA:AA). Who has 192.168.1.20?"*
2. **ARP Reply (unicast):** Host B responds directly to A: *"I'm 192.168.1.20; my MAC is BB:BB:BB:BB:BB:BB."*
3. **Data transmission:** Host A now sends the IP datagram inside an Ethernet frame addressed to `BB:BB:BB:BB:BB:BB`.

The result is cached in an **ARP table** with a TTL of roughly 20 minutes, avoiding repeated broadcasts. Hosts also learn from ARP requests they overhear — every request contains the sender's IP-to-MAC mapping.

### Off-subnet destinations

When the destination IP is on a different subnet, the host:

1. Checks its routing table and finds the **default gateway** (e.g., 192.168.1.1).
2. ARPs for the **gateway's MAC address** (not the final destination's).
3. Sends the frame to the router's MAC, with the IP datagram still carrying the remote destination IP.

ARP operates strictly within a single subnet (broadcast domain).

---

## 6. Switches and Self-Learning

### Hub vs. switch

| | Hub | Switch |
|---|---|---|
| Forwarding | Repeats frame on all ports | Selectively forwards by MAC |
| Collision domain | All ports share one | Each port is its own |
| Duplex | Half-duplex (CSMA/CD required) | Full-duplex (no collisions) |
| Privacy | Every host sees every frame | Frames go only where needed |

Switches replaced hubs because they enable multiple simultaneous transmissions, provide privacy, and eliminate collisions.

### Self-learning forwarding table

A switch maintains a **MAC address table** (also called a CAM table) that maps MAC addresses to ports:

| MAC Address | Port | TTL |
|---|---|---|
| AA:AA:AA:AA:AA:AA | 1 | 4:58 |
| BB:BB:BB:BB:BB:BB | 3 | 4:45 |

The table is populated automatically through **self-learning**: when a frame arrives on port P from source MAC X, the switch records (X → P). The forwarding logic is:

1. Look up the destination MAC in the table.
2. **Found** → forward to that port only.
3. **Not found** → **flood** (send to all ports except the ingress port).
4. **Broadcast/multicast** → always flood.

Entries expire after ~300 seconds of inactivity, so if a host moves to a different port, the stale entry ages out and the switch relearns its new location.

### Multi-switch LANs

In a network with multiple interconnected switches, the same learning-and-flooding process works across the entire topology. When a frame enters a switch with an unknown destination, it is flooded toward other switches, which in turn learn the source's location. After a few exchanges, all switches converge on correct forwarding tables. Switches are fully transparent to end hosts.

---

## 7. Subnets

A **subnet** is a set of network interfaces sharing the same IP prefix, reachable at the link layer without passing through a router. In CIDR notation, `192.168.1.0/24` means the first 24 bits are the network prefix and the last 8 bits identify hosts (0–255).

Key relationships:

- ARP operates within a subnet (broadcast domain).
- Cross-subnet traffic must go through a router.
- Each router interface belongs to a different subnet.

---

## 8. Ethernet Technology Survey

Ethernet naming follows the convention `<speed>BASE<medium>`, where "BASE" means baseband signaling.

### Historical (bus/hub era)

| Standard | Year | Speed | Medium |
|---|---|---|---|
| 10BASE-5 "Thicknet" | 1980 | 10 Mb/s | RG-8 coax, bus |
| 10BASE-2 "Thinnet" | 1985 | 10 Mb/s | RG-58 coax, bus |
| 10BASE-T | 1990 | 10 Mb/s | Cat 3 UTP, star hub |

### Modern (switched)

| Standard | Year | Speed | Medium |
|---|---|---|---|
| 100BASE-TX (Fast Ethernet) | 1995 | 100 Mb/s | Cat 5 UTP |
| 1000BASE-T (Gigabit) | 1999 | 1 Gb/s | Cat 5e UTP |
| 10GBASE-T | 2006 | 10 Gb/s | Cat 6A UTP |
| 100GBASE-SR4/LR4 | 2010 | 100 Gb/s | Fiber |
| 400GBASE-SR8 | 2017 | 400 Gb/s | Fiber |

### Power over Ethernet (PoE)

PoE (IEEE 802.3af/at/bt) delivers DC power over the same UTP cable as data:

- 802.3af: 15.4 W per port
- 802.3at: 30 W
- 802.3bt: up to 90 W

Common uses include IP phones, wireless access points, IP cameras, and IoT sensors.

### Auto-negotiation and duplex mismatch

Interfaces advertise their capabilities and both ends select the highest common mode. A **duplex mismatch** — one end full-duplex, the other half-duplex — is a common misconfiguration that causes the full-duplex end to never back off while the half-duplex end sees constant collisions, resulting in poor throughput and high CRC error counts.

---

## 9. Conclusion

Ethernet's longevity stems from a remarkably stable frame format paired with continuous physical-layer innovation. The combination of self-learning switches, a flat MAC addressing scheme, and ARP for address resolution creates a plug-and-play LAN infrastructure where hosts can communicate without any manual configuration. Understanding these mechanisms — how frames are structured, how addresses are resolved, and how switches forward traffic — is foundational for working with any modern network.

---

## Key Takeaways

1. **Ethernet frame** = preamble + dst/src MAC + type + payload (46–1500 B) + FCS; 64 B min, 1518 B max.
2. **MAC addresses** are 48-bit flat identifiers (OUI + device ID); broadcast = `FF:FF:FF:FF:FF:FF`.
3. **ARP** resolves IP → MAC within a subnet; request is broadcast, reply is unicast, results cached with TTL.
4. **Switches** self-learn MAC-to-port mappings; forward if known, flood if unknown; enable full-duplex, collision-free operation.
5. **Subnets** define broadcast domains; ARP works within one; crossing subnets requires a router.
6. **Ethernet speeds** have grown from 10 Mb/s to 400 Gb/s while the frame format has remained the same.

---

*Report based on Lecture 8 of EC 441, Spring 2026.*
