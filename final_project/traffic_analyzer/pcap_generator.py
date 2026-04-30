"""
Generate synthetic .pcap files that mimic the on-the-wire signature of
real applications. Used so the demo works on a laptop without internet.

The packets aren't real protocol payloads -- they're crafted IP/TCP/UDP
headers with realistic sizes, ports, and timing. This is enough for our
classifier to fingerprint them, and it's reproducible across machines.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from scapy.all import wrpcap  # type: ignore[import-untyped]
from scapy.layers.inet import IP, TCP, UDP  # type: ignore[import-untyped]
from scapy.packet import Raw  # type: ignore[import-untyped]


@dataclass
class _SynthPacket:
    """A single synthetic packet, deferred so we can sort by timestamp."""

    timestamp: float
    pkt: object


def _stamp(packets: list[_SynthPacket]) -> list:
    """Sort by timestamp and write timestamps onto Scapy packets."""
    packets.sort(key=lambda p: p.timestamp)
    out = []
    for p in packets:
        p.pkt.time = p.timestamp  # type: ignore[attr-defined]
        out.append(p.pkt)
    return out


def _payload(size_bytes: int) -> Raw:
    """Pad up to the desired total Ethernet/IP packet size."""
    overhead = 20 + 8  # IP + UDP minimum; TCP gets adjusted in caller
    n = max(1, size_bytes - overhead)
    return Raw(load=b"\x00" * n)


_BASE_T0 = 1_750_000_000.0


def generate_zoom_pcap(path: str, duration_s: float = 8.0,
                       seed: int = 1, t0: float = _BASE_T0) -> None:
    """Two-way Zoom-style call: heavy UDP, ~50 pps each direction, regular cadence."""
    rng = random.Random(seed)
    client_ip, server_ip = "192.168.1.42", "170.114.52.7"
    client_port = 51_840
    server_port = 8801

    pkts: list[_SynthPacket] = []
    frame_dt = 0.020  # 50 Hz audio

    # Audio frames every 20 ms in both directions (Opus ~120-250 B).
    n_frames = int(duration_s / frame_dt)
    for i in range(n_frames):
        t = t0 + i * frame_dt + rng.gauss(0, 0.0005)
        size = rng.randint(140, 260)
        pkts.append(_SynthPacket(t, IP(src=client_ip, dst=server_ip)
                                 / UDP(sport=client_port, dport=server_port)
                                 / _payload(size)))
        size = rng.randint(140, 260)
        pkts.append(_SynthPacket(t + 0.001, IP(src=server_ip, dst=client_ip)
                                 / UDP(sport=server_port, dport=client_port)
                                 / _payload(size)))

    # Sprinkle in larger video frames every ~33 ms (~30 fps).
    n_video = int(duration_s / 0.033)
    for i in range(n_video):
        t = t0 + i * 0.033 + rng.gauss(0, 0.001)
        size = rng.randint(700, 1100)
        pkts.append(_SynthPacket(t, IP(src=client_ip, dst=server_ip)
                                 / UDP(sport=client_port, dport=server_port)
                                 / _payload(size)))
        size = rng.randint(700, 1100)
        pkts.append(_SynthPacket(t + 0.0008, IP(src=server_ip, dst=client_ip)
                                 / UDP(sport=server_port, dport=client_port)
                                 / _payload(size)))

    wrpcap(path, _stamp(pkts))


def generate_discord_pcap(path: str, duration_s: float = 8.0,
                          seed: int = 2, t0: float = _BASE_T0) -> None:
    """Discord voice: UDP RTP-like, single peer voice server, port in 50000+ range."""
    rng = random.Random(seed)
    client_ip, server_ip = "192.168.1.42", "66.22.197.45"
    client_port = 49_152
    server_port = 50_005

    pkts: list[_SynthPacket] = []
    frame_dt = 0.020  # Opus 50 Hz

    n_frames = int(duration_s / frame_dt)
    for i in range(n_frames):
        t = t0 + i * frame_dt + rng.gauss(0, 0.0005)
        size = rng.randint(100, 180)
        pkts.append(_SynthPacket(t, IP(src=client_ip, dst=server_ip)
                                 / UDP(sport=client_port, dport=server_port)
                                 / _payload(size)))
        size = rng.randint(100, 180)
        pkts.append(_SynthPacket(t + 0.0009, IP(src=server_ip, dst=client_ip)
                                 / UDP(sport=server_port, dport=client_port)
                                 / _payload(size)))

    # Plus a TCP/443 WebSocket gateway with sparse keep-alives.
    gw_ip = "162.159.135.232"
    gw_client_port = 60_124
    for i in range(int(duration_s / 1.0)):
        t = t0 + i * 1.0
        pkts.append(_SynthPacket(t, IP(src=client_ip, dst=gw_ip)
                                 / TCP(sport=gw_client_port, dport=443, flags="PA")
                                 / _payload(180)))
        pkts.append(_SynthPacket(t + 0.012, IP(src=gw_ip, dst=client_ip)
                                 / TCP(sport=443, dport=gw_client_port, flags="A")
                                 / _payload(60)))

    wrpcap(path, _stamp(pkts))


def generate_youtube_pcap(path: str, duration_s: float = 10.0,
                          seed: int = 3, t0: float = _BASE_T0) -> None:
    """YouTube ABR: TCP/443, asymmetric, MTU-sized download bursts every few seconds."""
    rng = random.Random(seed)
    client_ip, server_ip = "192.168.1.42", "172.217.14.78"
    client_port = 55_212
    server_port = 443

    pkts: list[_SynthPacket] = []

    syn = IP(src=client_ip, dst=server_ip) / TCP(sport=client_port, dport=server_port,
                                                 flags="S", seq=1000)
    pkts.append(_SynthPacket(t0, syn))
    pkts.append(_SynthPacket(t0 + 0.025, IP(src=server_ip, dst=client_ip)
                             / TCP(sport=server_port, dport=client_port,
                                   flags="SA", seq=2000, ack=1001)))
    pkts.append(_SynthPacket(t0 + 0.026, IP(src=client_ip, dst=server_ip)
                             / TCP(sport=client_port, dport=server_port,
                                   flags="A", seq=1001, ack=2001)))

    # ABR chunk pattern: every ~3 s, server bursts ~1 MB at MTU sized packets.
    chunk_interval = 3.0
    n_chunks = max(1, int(duration_s / chunk_interval))
    for c in range(n_chunks):
        burst_t = t0 + 0.05 + c * chunk_interval
        # Client GET: a few small request packets.
        for j in range(3):
            t = burst_t + j * 0.001
            pkts.append(_SynthPacket(t, IP(src=client_ip, dst=server_ip)
                                     / TCP(sport=client_port, dport=server_port,
                                           flags="PA")
                                     / _payload(rng.randint(150, 350))))
        # Server response: ~700 packets of 1500 B.
        for j in range(700):
            t = burst_t + 0.05 + j * 0.0007 + rng.gauss(0, 0.0001)
            pkts.append(_SynthPacket(t, IP(src=server_ip, dst=client_ip)
                                     / TCP(sport=server_port, dport=client_port,
                                           flags="A")
                                     / _payload(1500)))
            # ACK from client roughly every 2 server packets.
            if j % 2 == 0:
                t_ack = t + 0.001
                pkts.append(_SynthPacket(t_ack, IP(src=client_ip, dst=server_ip)
                                         / TCP(sport=client_port, dport=server_port,
                                               flags="A")
                                         / _payload(60)))

    wrpcap(path, _stamp(pkts))


def generate_spotify_pcap(path: str, duration_s: float = 10.0,
                          seed: int = 4, t0: float = _BASE_T0) -> None:
    """Spotify: TCP/443 to a CDN, smaller chunks than YouTube, asymmetric."""
    rng = random.Random(seed)
    client_ip, server_ip = "192.168.1.42", "35.186.224.47"  # Spotify CDN-ish
    client_port = 56_001
    server_port = 443

    pkts: list[_SynthPacket] = []

    pkts.append(_SynthPacket(t0, IP(src=client_ip, dst=server_ip)
                             / TCP(sport=client_port, dport=server_port,
                                   flags="S", seq=10)))
    pkts.append(_SynthPacket(t0 + 0.040, IP(src=server_ip, dst=client_ip)
                             / TCP(sport=server_port, dport=client_port,
                                   flags="SA", seq=200, ack=11)))
    pkts.append(_SynthPacket(t0 + 0.041, IP(src=client_ip, dst=server_ip)
                             / TCP(sport=client_port, dport=server_port,
                                   flags="A", seq=11, ack=201)))

    # Audio chunks: ~every 5 s, ~150 KB of 700-1100 B packets.
    chunk_interval = 5.0
    for c in range(max(1, int(duration_s / chunk_interval))):
        burst_t = t0 + 0.1 + c * chunk_interval
        pkts.append(_SynthPacket(burst_t, IP(src=client_ip, dst=server_ip)
                                 / TCP(sport=client_port, dport=server_port,
                                       flags="PA")
                                 / _payload(rng.randint(150, 320))))
        for j in range(180):
            t = burst_t + 0.05 + j * 0.0015 + rng.gauss(0, 0.0002)
            size = rng.randint(700, 1100)
            pkts.append(_SynthPacket(t, IP(src=server_ip, dst=client_ip)
                                     / TCP(sport=server_port, dport=client_port,
                                           flags="A")
                                     / _payload(size)))

    wrpcap(path, _stamp(pkts))


def generate_web_pcap(path: str, duration_s: float = 6.0,
                      seed: int = 5, t0: float = _BASE_T0) -> None:
    """Web browsing: many short TCP/443 flows to different destinations."""
    rng = random.Random(seed)
    client_ip = "192.168.1.42"
    pkts: list[_SynthPacket] = []

    destinations = [
        ("104.16.132.229", "cloudflare"),
        ("142.250.190.78", "google"),
        ("151.101.65.140", "fastly"),
        ("23.215.0.137", "akamai"),
        ("13.224.0.42",  "amazon-cf"),
        ("199.232.5.140", "fastly-2"),
    ]

    for i, (dst_ip, _name) in enumerate(destinations):
        client_port = 50_000 + i
        burst_t = t0 + i * 0.5

        pkts.append(_SynthPacket(burst_t, IP(src=client_ip, dst=dst_ip)
                                 / TCP(sport=client_port, dport=443,
                                       flags="S", seq=1)))
        rtt = rng.uniform(0.012, 0.045)
        pkts.append(_SynthPacket(burst_t + rtt, IP(src=dst_ip, dst=client_ip)
                                 / TCP(sport=443, dport=client_port,
                                       flags="SA", seq=100, ack=2)))
        pkts.append(_SynthPacket(burst_t + rtt + 0.001,
                                 IP(src=client_ip, dst=dst_ip)
                                 / TCP(sport=client_port, dport=443,
                                       flags="A", seq=2, ack=101)))

        # GET request (~500 B), then a short, bursty response (~30-80 packets).
        pkts.append(_SynthPacket(burst_t + rtt + 0.002,
                                 IP(src=client_ip, dst=dst_ip)
                                 / TCP(sport=client_port, dport=443, flags="PA")
                                 / _payload(rng.randint(350, 600))))
        n_resp = rng.randint(30, 80)
        for j in range(n_resp):
            t = burst_t + rtt + 0.05 + j * rng.uniform(0.001, 0.020)
            size = rng.choice([240, 380, 720, 1200, 1460])
            pkts.append(_SynthPacket(t, IP(src=dst_ip, dst=client_ip)
                                     / TCP(sport=443, dport=client_port, flags="A")
                                     / _payload(size)))
            if j % 4 == 0:
                pkts.append(_SynthPacket(t + 0.0005,
                                         IP(src=client_ip, dst=dst_ip)
                                         / TCP(sport=client_port, dport=443, flags="A")
                                         / _payload(60)))

    wrpcap(path, _stamp(pkts))


def generate_mixed_pcap(path: str) -> None:
    """All five apps running concurrently in one pcap -- the headline demo file.

    They start within a few seconds of each other and overlap in time, so the
    burst-timeline chart shows real-world contention rather than each app in
    its own quiet window.
    """
    import os
    import tempfile

    from scapy.all import rdpcap, wrpcap as _wr  # type: ignore[import-untyped]

    schedule = (
        # (generator,                     start_offset_s, duration_s)
        (generate_zoom_pcap,              0.0,            12.0),
        (generate_discord_pcap,           1.5,            10.0),
        (generate_youtube_pcap,           0.5,            12.0),
        (generate_spotify_pcap,           3.0,            10.0),
        (generate_web_pcap,               2.0,             8.0),
    )

    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (fn, offset, dur) in enumerate(schedule):
            p = os.path.join(tmp, f"part_{i}.pcap")
            fn(p, duration_s=dur, t0=_BASE_T0 + offset)
            parts.extend(list(rdpcap(p)))
        parts.sort(key=lambda pkt: float(pkt.time))
        _wr(path, parts)


_GENERATORS = {
    "zoom": generate_zoom_pcap,
    "discord": generate_discord_pcap,
    "youtube": generate_youtube_pcap,
    "spotify": generate_spotify_pcap,
    "web": generate_web_pcap,
    "mixed": generate_mixed_pcap,
}


def generate(name: str, path: str) -> None:
    if name not in _GENERATORS:
        raise ValueError(
            f"Unknown pcap '{name}'. Choose from: {', '.join(_GENERATORS)}"
        )
    _GENERATORS[name](path)
