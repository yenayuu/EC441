"""
Core pcap analyzer.

Reads a .pcap / .pcapng file with Scapy, groups packets into bidirectional
flows keyed by the 5-tuple, and computes per-flow + per-capture statistics:

  - TCP vs UDP breakdown (packets and bytes)
  - Average / median / p95 packet sizes
  - Inter-arrival times and burstiness
  - Top ports and destinations
  - RTT estimation (TCP SYN -> SYN+ACK handshake)

The output is plain Python dataclasses so the rest of the pipeline
(classifier, reporter, visualizer) stays decoupled from Scapy.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from scapy.all import rdpcap  # type: ignore[import-untyped]
from scapy.layers.inet import IP, TCP, UDP  # type: ignore[import-untyped]
from scapy.layers.inet6 import IPv6  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlowKey:
    """Canonicalised 5-tuple. Order-independent: (a,b) == (b,a)."""

    proto: str  # "TCP" | "UDP" | "OTHER"
    endpoint_a: str  # ip:port (lexicographically smaller side)
    endpoint_b: str  # ip:port

    @classmethod
    def from_packet(cls, src_ip: str, dst_ip: str,
                    src_port: int, dst_port: int, proto: str) -> "FlowKey":
        a = f"{src_ip}:{src_port}"
        b = f"{dst_ip}:{dst_port}"
        if a > b:
            a, b = b, a
        return cls(proto=proto, endpoint_a=a, endpoint_b=b)

    @property
    def port_a(self) -> int:
        return int(self.endpoint_a.rsplit(":", 1)[1])

    @property
    def port_b(self) -> int:
        return int(self.endpoint_b.rsplit(":", 1)[1])

    @property
    def ports(self) -> tuple[int, int]:
        return (self.port_a, self.port_b)

    def server_side(self) -> str:
        """Return the endpoint that looks like the 'server' (lower port)."""
        return self.endpoint_a if self.port_a <= self.port_b else self.endpoint_b

    def server_port(self) -> int:
        return int(self.server_side().rsplit(":", 1)[1])

    def has_port_in(self, low: int, high: int) -> bool:
        return any(low <= p <= high for p in self.ports)

    def has_any_port(self, *ports: int) -> bool:
        return any(p in ports for p in self.ports)


@dataclass
class FlowStats:
    key: FlowKey
    packets: int = 0
    bytes_total: int = 0
    sizes: list[int] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)

    # TCP handshake tracking for RTT estimation.
    syn_time: float | None = None
    synack_time: float | None = None
    rtt_ms: float | None = None

    # Direction-tagged counts (a -> b vs b -> a).
    pkts_a_to_b: int = 0
    pkts_b_to_a: int = 0
    bytes_a_to_b: int = 0
    bytes_b_to_a: int = 0

    @property
    def duration_s(self) -> float:
        if len(self.timestamps) < 2:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

    @property
    def avg_pkt_size(self) -> float:
        return statistics.mean(self.sizes) if self.sizes else 0.0

    @property
    def median_pkt_size(self) -> float:
        return statistics.median(self.sizes) if self.sizes else 0.0

    @property
    def p95_pkt_size(self) -> float:
        if not self.sizes:
            return 0.0
        ordered = sorted(self.sizes)
        idx = max(0, int(0.95 * len(ordered)) - 1)
        return float(ordered[idx])

    @property
    def pps(self) -> float:
        d = self.duration_s
        return self.packets / d if d > 0 else 0.0

    @property
    def bps(self) -> float:
        d = self.duration_s
        return (self.bytes_total * 8) / d if d > 0 else 0.0

    def inter_arrival_times(self) -> list[float]:
        if len(self.timestamps) < 2:
            return []
        return [
            self.timestamps[i] - self.timestamps[i - 1]
            for i in range(1, len(self.timestamps))
        ]

    def burstiness(self) -> float:
        """Coefficient of variation of inter-arrival times.

        ~0  -> very regular (e.g. Zoom audio every 20 ms)
        ~1  -> Poisson-like
        >>1 -> bursty (e.g. video chunk downloads)
        """
        iats = self.inter_arrival_times()
        if len(iats) < 2:
            return 0.0
        mean = statistics.mean(iats)
        if mean == 0:
            return 0.0
        return statistics.pstdev(iats) / mean


@dataclass
class CaptureStats:
    total_packets: int = 0
    total_bytes: int = 0
    tcp_packets: int = 0
    udp_packets: int = 0
    other_packets: int = 0
    tcp_bytes: int = 0
    udp_bytes: int = 0
    other_bytes: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    flows: dict[FlowKey, FlowStats] = field(default_factory=dict)
    port_hits: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    dst_hits: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_time - self.start_time)

    @property
    def tcp_pct(self) -> float:
        n = self.tcp_packets + self.udp_packets + self.other_packets
        return (self.tcp_packets / n * 100.0) if n else 0.0

    @property
    def udp_pct(self) -> float:
        n = self.tcp_packets + self.udp_packets + self.other_packets
        return (self.udp_packets / n * 100.0) if n else 0.0

    def top_ports(self, n: int = 5) -> list[tuple[int, int]]:
        return sorted(self.port_hits.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def top_destinations(self, n: int = 5) -> list[tuple[str, int]]:
        return sorted(self.dst_hits.items(), key=lambda kv: kv[1], reverse=True)[:n]

    def flow_list(self) -> list[FlowStats]:
        return sorted(
            self.flows.values(), key=lambda f: f.bytes_total, reverse=True,
        )


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


# Common service ports we want to highlight as "server-side" when both ends
# look ephemeral. Bigger list keeps classification accurate for QUIC/STUN/RTP.
_WELL_KNOWN_SERVER_PORTS = {
    53, 67, 68, 80, 123, 443, 853, 993, 995,
    1194, 3478, 3479,        # STUN
    5060, 5061,              # SIP
    5004, 5005,              # RTP
    8801, 8802, 8803, 8804, 8805, 8806, 8807, 8808, 8809, 8810,  # Zoom
    50000, 50001, 50002, 50003, 50004,  # Discord voice range (subset)
}


class PcapAnalyzer:
    """Reads a pcap file and produces a CaptureStats."""

    def __init__(self, path: str) -> None:
        self.path = path

    def analyze(self) -> CaptureStats:
        packets = rdpcap(self.path)
        return self._aggregate(packets)

    def _aggregate(self, packets: Iterable) -> CaptureStats:
        cap = CaptureStats()

        for pkt in packets:
            ts = float(pkt.time) if hasattr(pkt, "time") else 0.0
            length = len(pkt)

            if cap.total_packets == 0:
                cap.start_time = ts
            cap.end_time = ts
            cap.total_packets += 1
            cap.total_bytes += length

            ip_layer = None
            if IP in pkt:
                ip_layer = pkt[IP]
                src_ip, dst_ip = ip_layer.src, ip_layer.dst
            elif IPv6 in pkt:
                ip_layer = pkt[IPv6]
                src_ip, dst_ip = ip_layer.src, ip_layer.dst
            else:
                cap.other_packets += 1
                cap.other_bytes += length
                continue

            if TCP in pkt:
                proto, l4 = "TCP", pkt[TCP]
                cap.tcp_packets += 1
                cap.tcp_bytes += length
            elif UDP in pkt:
                proto, l4 = "UDP", pkt[UDP]
                cap.udp_packets += 1
                cap.udp_bytes += length
            else:
                cap.other_packets += 1
                cap.other_bytes += length
                continue

            sport, dport = int(l4.sport), int(l4.dport)
            key = FlowKey.from_packet(src_ip, dst_ip, sport, dport, proto)
            flow = cap.flows.get(key)
            if flow is None:
                flow = FlowStats(key=key)
                cap.flows[key] = flow

            flow.packets += 1
            flow.bytes_total += length
            flow.sizes.append(length)
            flow.timestamps.append(ts)

            a_endpoint = f"{src_ip}:{sport}"
            if a_endpoint == key.endpoint_a:
                flow.pkts_a_to_b += 1
                flow.bytes_a_to_b += length
            else:
                flow.pkts_b_to_a += 1
                flow.bytes_b_to_a += length

            server_port = self._infer_server_port(sport, dport)
            cap.port_hits[server_port] += 1
            cap.dst_hits[dst_ip] += 1

            if proto == "TCP":
                self._track_tcp_handshake(flow, l4, ts)

        return cap

    @staticmethod
    def _infer_server_port(sport: int, dport: int) -> int:
        """Pick the more 'service-like' port of the two."""
        if sport in _WELL_KNOWN_SERVER_PORTS and dport not in _WELL_KNOWN_SERVER_PORTS:
            return sport
        if dport in _WELL_KNOWN_SERVER_PORTS and sport not in _WELL_KNOWN_SERVER_PORTS:
            return dport
        return min(sport, dport)

    @staticmethod
    def _track_tcp_handshake(flow: FlowStats, tcp_layer, ts: float) -> None:
        """RTT estimate from SYN -> SYN+ACK timing (the textbook handshake)."""
        flags = int(tcp_layer.flags)
        is_syn = bool(flags & 0x02)
        is_ack = bool(flags & 0x10)

        if is_syn and not is_ack and flow.syn_time is None:
            flow.syn_time = ts
        elif is_syn and is_ack and flow.synack_time is None:
            flow.synack_time = ts
            if flow.syn_time is not None:
                flow.rtt_ms = (ts - flow.syn_time) * 1000.0
