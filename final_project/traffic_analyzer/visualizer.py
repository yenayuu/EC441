"""
Generate the four headline charts from a capture:

  1. TCP vs UDP packets and bytes (bar pair).
  2. Packet-size distribution (histogram, log-y).
  3. Burst timeline -- bytes/second over capture duration.
  4. Per-flow scatter: avg packet size vs burstiness, colored by app guess.

These are the visuals you point at during the live demo.
"""

from __future__ import annotations

import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")  # headless-safe: works without an X server.
import matplotlib.pyplot as plt  # noqa: E402

from .analyzer import CaptureStats  # noqa: E402
from .classifier import AppClassifier  # noqa: E402


_APP_COLORS = {
    "Zoom":         "#9c27b0",
    "Discord":      "#5865f2",
    "YouTube":      "#ff0000",
    "Spotify":      "#1db954",
    "Web browsing": "#f5a623",
    "Unknown":      "#888888",
}


def render_all_charts(cap: CaptureStats, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = [
        _chart_proto_breakdown(cap, os.path.join(out_dir, "01_tcp_vs_udp.png")),
        _chart_size_hist(cap, os.path.join(out_dir, "02_packet_sizes.png")),
        _chart_burst_timeline(cap, os.path.join(out_dir, "03_burst_timeline.png")),
        _chart_flow_scatter(cap, os.path.join(out_dir, "04_flow_fingerprints.png")),
    ]
    return paths


def _chart_proto_breakdown(cap: CaptureStats, path: str) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    labels = ["TCP", "UDP", "Other"]
    pkt_vals = [cap.tcp_packets, cap.udp_packets, cap.other_packets]
    byte_vals = [cap.tcp_bytes, cap.udp_bytes, cap.other_bytes]
    colors = ["#1f77b4", "#ff7f0e", "#999999"]

    axes[0].bar(labels, pkt_vals, color=colors)
    axes[0].set_title("Packets by transport protocol")
    axes[0].set_ylabel("Packets")
    for i, v in enumerate(pkt_vals):
        axes[0].text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=9)

    axes[1].bar(labels, byte_vals, color=colors)
    axes[1].set_title("Bytes by transport protocol")
    axes[1].set_ylabel("Bytes")
    for i, v in enumerate(byte_vals):
        axes[1].text(i, v, _short_bytes(v), ha="center", va="bottom", fontsize=9)

    fig.suptitle("TCP vs UDP usage", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _chart_size_hist(cap: CaptureStats, path: str) -> str:
    sizes_tcp: list[int] = []
    sizes_udp: list[int] = []
    for flow in cap.flows.values():
        if flow.key.proto == "TCP":
            sizes_tcp.extend(flow.sizes)
        elif flow.key.proto == "UDP":
            sizes_udp.extend(flow.sizes)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    bins = list(range(0, 1600, 50))
    if sizes_tcp:
        ax.hist(sizes_tcp, bins=bins, alpha=0.65, label="TCP",
                color="#1f77b4", edgecolor="white")
    if sizes_udp:
        ax.hist(sizes_udp, bins=bins, alpha=0.65, label="UDP",
                color="#ff7f0e", edgecolor="white")
    ax.set_xlabel("Packet size (bytes)")
    ax.set_ylabel("Packet count (log scale)")
    ax.set_yscale("log")
    ax.set_title("Packet-size distribution",
                 fontsize=14, fontweight="bold")
    ax.axvline(1500, color="red", linestyle="--", alpha=0.4,
               label="Ethernet MTU (1500 B)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _chart_burst_timeline(cap: CaptureStats, path: str) -> str:
    """Bytes-per-100ms-bucket timeline -- shows ABR chunks vs steady audio."""
    if cap.total_packets == 0:
        return path
    bucket_size = 0.1
    buckets_tcp: dict[int, int] = defaultdict(int)
    buckets_udp: dict[int, int] = defaultdict(int)

    t0 = cap.start_time
    for flow in cap.flows.values():
        target = buckets_tcp if flow.key.proto == "TCP" else buckets_udp
        for ts, sz in zip(flow.timestamps, flow.sizes):
            idx = int((ts - t0) / bucket_size)
            target[idx] += sz

    duration = max(cap.duration_s, bucket_size)
    n_buckets = int(duration / bucket_size) + 1
    xs = [i * bucket_size for i in range(n_buckets)]
    ys_tcp = [buckets_tcp.get(i, 0) / 1024 for i in range(n_buckets)]
    ys_udp = [buckets_udp.get(i, 0) / 1024 for i in range(n_buckets)]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.fill_between(xs, ys_udp, alpha=0.6, label="UDP",
                    color="#ff7f0e", step="mid")
    ax.fill_between(xs, ys_tcp, alpha=0.6, label="TCP",
                    color="#1f77b4", step="mid")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Throughput (KB / 100 ms bucket)")
    ax.set_title("Burst timeline -- where the bytes happen",
                 fontsize=14, fontweight="bold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _chart_flow_scatter(cap: CaptureStats, path: str) -> str:
    """avg packet size vs burstiness, sized by total bytes, colored by guess."""
    classifier = AppClassifier()
    fig, ax = plt.subplots(figsize=(10, 6))

    plotted_apps: dict[str, bool] = {}
    for flow in cap.flow_list():
        if flow.packets < 5:
            continue
        guess = classifier.classify_flow(flow)
        color = _APP_COLORS.get(guess.app, "#888888")
        size_pts = max(40, min(500, flow.bytes_total / 4000))
        label = guess.app if guess.app not in plotted_apps else None
        plotted_apps[guess.app] = True
        ax.scatter(flow.avg_pkt_size, flow.burstiness(),
                   s=size_pts, alpha=0.7, color=color,
                   edgecolors="white", linewidths=1.0, label=label)

    ax.set_xlabel("Avg packet size (bytes)")
    ax.set_ylabel("Burstiness (CV of inter-arrival times)")
    ax.set_title("Flow fingerprints -- bubble area = total bytes",
                 fontsize=14, fontweight="bold")
    ax.axhline(0.5, color="grey", linestyle=":", alpha=0.5)
    ax.text(50, 0.52, "  steady realtime media (Zoom/Discord)",
            color="grey", fontsize=8)
    ax.axvline(1000, color="grey", linestyle=":", alpha=0.5)
    ax.text(1010, ax.get_ylim()[1] * 0.95, "  bulk download (YouTube)",
            color="grey", fontsize=8, va="top")
    if plotted_apps:
        ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _short_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"
