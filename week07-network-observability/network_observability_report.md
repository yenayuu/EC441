# Week 07 -- See the Network: CLI Tools, Wireshark, and pyshark

**Course:** EC 441 -- Introduction to Computer Networking, Boston University, Spring 2026

**Type:** Report

**Source:** Lecture 21 -- See the Network (CLI tools, Wireshark, pyshark)

---

## 1. Introduction

Lecture 21 shifts from protocol design to protocol observation. After learning how Ethernet, IP, routing, ARP, UDP, TCP, congestion control, and DNS work, this week focuses on how to inspect those mechanisms on a live system. The lecture combines two complementary views:

- CLI tools for rapid diagnosis on Linux/Unix systems.
- Wireshark for packet-level visual inspection.
- pyshark for repeatable, code-driven analysis at scale.

The central theme is practical: networking knowledge is most valuable when we can verify behavior directly on real traffic.

---

## 2. Session Structure and Learning Goals

Lecture 21 is split into two sessions:

1. **Session 1 -- CLI tools:** `ping`, `traceroute`, `ip`, `ss`, `dig`, `tcpdump`
2. **Session 2 -- analysis workflow:** Wireshark GUI + pyshark scripts

By the end of the lecture, students should be able to:

- Generate traffic intentionally.
- Capture packets into a `.pcap`.
- Inspect protocol fields manually in Wireshark.
- Query the same packet data programmatically in Python.

---

## 3. Why Linux/BSD Tooling Matters

The lecture emphasizes that these tools are not "student-only" exercises. They are standard in production network engineering:

- Juniper JunOS is FreeBSD-based.
- Arista EOS is Linux-based.
- pfSense/OPNsense are FreeBSD-based.
- `tcpdump`, `ping`, `traceroute`, and `ss` exist across these environments.

This connects course content to real operator workflows and reinforces command-line fluency as a professional networking skill.

---

## 4. Lab Environment: Multipass VM

All commands are run in an Ubuntu 24.04 VM named `ec441`.

Typical setup flow:

```bash
multipass launch --name ec441 --cpus 2 --memory 4G --disk 20G --cloud-init ec441_setup.yaml 24.04
multipass shell ec441
```

This isolates the lab environment while keeping host-level tools (especially Wireshark GUI) separate.

---

## 5. `ping`: ICMP Echo and RTT Variability

`ping` is presented as the quickest health and latency probe:

```bash
ping -c 5 8.8.8.8
ping -i 0.2 -c 20 8.8.8.8
```

Conceptual connections:

- ICMP Echo Request/Reply from earlier network-layer lectures.
- Measured RTT variation as intuition for RTTVAR (used by TCP RTO logic).
- Reply TTL as a rough hint of hop count (relative to common initial TTL values like 64 or 128).

So, `ping` is not only reachability; it is also a live demonstration of delay dynamics that transport protocols must tolerate.

---

## 6. `traceroute`: TTL-Limited Path Discovery

`traceroute` reveals forwarding path structure by sending probes with TTL 1, 2, 3, ...

```bash
traceroute -m 20 8.8.8.8
traceroute -T -p 80 8.8.8.8
```

Key points:

- Routers decrement TTL and generate ICMP Time Exceeded at expiration.
- `-T` mode (TCP probes) can pass environments where ICMP probing is filtered.
- `* * *` hops typically indicate filtering or no response, not necessarily a failed path.
- RTT jumps often suggest crossing larger administrative boundaries.

This tool operationalizes TTL behavior from IP theory into a concrete path map.

---

## 7. `ip`: Interfaces, Routes, and Neighbor Cache

The `ip` utility gives a compact view of local L2/L3 state:

```bash
ip addr show
ip route show
ip neigh show
```

Interpretation:

- `ip addr`: interface and address assignment.
- `ip route`: forwarding table entries and default gateway logic.
- `ip neigh`: ARP/neighbor cache entries with state labels (for example, REACHABLE, STALE).

This is the exact local state used when packets leave a host toward next hops.

---

## 8. `ss`: Live TCP Socket Internals

`ss` bridges socket abstractions and TCP control internals:

```bash
ss -t
ss -tipm
```

During traffic generation (for example `iperf3`), `ss -tipm` exposes:

- `cwnd` (congestion window)
- `ssthresh` (slow-start threshold)
- `rtt` and RTT variance values
- retransmission counters

This is especially useful for validating Lecture 19/20 behavior (slow start, congestion avoidance, and loss reaction) in real time.

---

## 9. `dig`: DNS Resolution as Observable UDP Traffic

`dig` demonstrates DNS behavior at multiple detail levels:

```bash
dig google.com
dig +short google.com
dig @8.8.8.8 google.com
dig +trace google.com
dig google.com MX
```

Important observations:

- DNS answer TTL indicates cache lifetime.
- `+trace` reveals iterative resolution from root to TLD to authoritative servers.
- Most classic queries are UDP-based and can be captured with `tcpdump` on port 53.

This previews application-layer DNS mechanisms while staying grounded in packet traces.

---

## 10. `tcpdump`: Fast Capture and Filtered Visibility

`tcpdump` provides command-line packet capture and BPF filtering:

```bash
sudo tcpdump -i any -n port 53
sudo tcpdump -i any -n -w ~/capture.pcap &
ping -c 5 8.8.8.8
dig google.com
curl -s https://example.com > /dev/null
sudo pkill tcpdump
```

Representative filters:

- `host 8.8.8.8`
- `port 443`
- `tcp`, `udp`, `icmp`
- `tcp and port 80`

The practical pattern is: generate known traffic, capture it, then inspect the resulting `.pcap`.

---

## 11. Wireshark Workflow: Human Inspection

The lecture's workflow places Wireshark GUI on the laptop and traffic generation in the VM.

Transfer example:

```bash
multipass transfer ec441:/home/ubuntu/capture.pcap ~/capture.pcap
```

Then inspect in Wireshark:

- Protocol hierarchy statistics.
- A DNS packet stack (Ethernet -> IP -> UDP -> DNS).
- TCP stream follow/assembly.
- SYN, SYN-ACK, ACK sequencing details.

Wireshark is strongest for interactive diagnosis and drill-down into individual conversations.

---

## 12. pyshark Workflow: Programmatic Analysis

pyshark uses Wireshark/tshark dissectors but exposes packets in Python objects, enabling dataset-style analysis.

Basic iteration:

```python
import pyshark
cap = pyshark.FileCapture('/home/ubuntu/capture.pcap')
for pkt in cap:
    print(pkt.highest_layer, pkt.length)
```

Packet field inspection:

```python
pkt = next(iter(cap))
print(pkt.layers)
print(pkt.ip.src)
print(pkt.ip.ttl)
print(pkt.transport_layer)
```

DNS query extraction:

```python
cap = pyshark.FileCapture('capture.pcap', display_filter='dns')
queries = []
for pkt in cap:
    try:
        if hasattr(pkt.dns, 'qry_name'):
            queries.append(pkt.dns.qry_name)
    except AttributeError:
        pass
for q in sorted(set(queries)):
    print(q)
```

TCP RTT plotting:

```python
import pyshark, matplotlib.pyplot as plt
cap = pyshark.FileCapture('capture.pcap', display_filter='tcp.analysis.ack_rtt')
times, rtts = [], []
for pkt in cap:
    try:
        times.append(float(pkt.sniff_timestamp))
        rtts.append(float(pkt.tcp.analysis_ack_rtt) * 1000)
    except AttributeError:
        pass
plt.plot(times, rtts, '.', markersize=3)
plt.xlabel('Time (s)')
plt.ylabel('RTT (ms)')
plt.savefig('rtt_plot.png')
```

The key idea is that field names match Wireshark, so manual discovery in GUI translates directly into script logic.

---

## 13. Connections to Earlier Lectures

Lecture 21 is integrative. Each tool maps to prior theory:

| Tool | Earlier concepts reinforced |
|---|---|
| `ping` | ICMP, RTT variance |
| `traceroute` | TTL, ICMP Time Exceeded, forwarding |
| `ip neigh` | ARP and L2/L3 binding |
| `ss -tipm` | TCP cwnd, ssthresh, RTT, retransmissions |
| `dig` | DNS records, caching TTL, recursive chain |
| `tcpdump`/Wireshark | Full layered packet parsing |
| pyshark | Repeatable measurement and transport analytics |

This week effectively turns "protocol knowledge" into "observability practice."

---

## 14. Practical Debugging Loop from the Lecture

A robust workflow implied by the slides:

1. Reproduce a behavior (`ping`, `curl`, `dig`, test app traffic).
2. Capture packets (`tcpdump -w`).
3. Inspect quickly in Wireshark (sanity + protocol-level clues).
4. Script targeted extraction in pyshark (counts, RTT trends, query sets, anomalies).
5. Iterate with tighter filters and better hypotheses.

This combines human intuition and automation, which is exactly how modern network troubleshooting scales.

---

## 15. What Comes Next

The lecture closes by previewing Lecture 22 ("Touch the network"): Scapy, Mininet, and sockets. Conceptually, Week 07 is the bridge between understanding packets and actively generating/customizing them. First we observe the network accurately; next we manipulate it.

