"""
Rich terminal report. The tables / panels here are what the audience sees
during the live demo, so they're tuned for readability over a laptop screen.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .analyzer import CaptureStats, FlowStats
from .classifier import AppClassifier, AppGuess


def _bar(pct: float, width: int = 24) -> str:
    filled = int(round(pct / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def render_terminal_report(cap: CaptureStats, pcap_path: str,
                           console: Console | None = None) -> None:
    console = console or Console()

    # --- Header -----------------------------------------------------------
    console.print()
    console.rule("[bold cyan]Wireshark Traffic Analyzer[/bold cyan]")
    console.print(
        f"[dim]File:[/dim] [bold]{pcap_path}[/bold]   "
        f"[dim]Duration:[/dim] {cap.duration_s:.2f} s   "
        f"[dim]Packets:[/dim] {cap.total_packets:,}   "
        f"[dim]Bytes:[/dim] {_human_bytes(cap.total_bytes)}"
    )
    console.print()

    # --- TCP vs UDP breakdown --------------------------------------------
    proto_table = Table(title="Transport-layer breakdown", title_style="bold",
                        show_lines=False, expand=False)
    proto_table.add_column("Protocol")
    proto_table.add_column("Packets", justify="right")
    proto_table.add_column("%", justify="right")
    proto_table.add_column("Bytes", justify="right")
    proto_table.add_column("Distribution", justify="left")
    proto_table.add_row(
        "TCP", f"{cap.tcp_packets:,}", f"{cap.tcp_pct:5.1f}%",
        _human_bytes(cap.tcp_bytes), _bar(cap.tcp_pct),
    )
    proto_table.add_row(
        "UDP", f"{cap.udp_packets:,}", f"{cap.udp_pct:5.1f}%",
        _human_bytes(cap.udp_bytes), _bar(cap.udp_pct),
    )
    other_pct = 100.0 - cap.tcp_pct - cap.udp_pct
    if cap.other_packets:
        proto_table.add_row(
            "Other", f"{cap.other_packets:,}", f"{other_pct:5.1f}%",
            _human_bytes(cap.other_bytes), _bar(other_pct),
        )
    console.print(proto_table)
    console.print()

    # --- Top ports / destinations ----------------------------------------
    ports_table = Table(title="Top server ports", title_style="bold")
    ports_table.add_column("Port", justify="right")
    ports_table.add_column("Packets", justify="right")
    ports_table.add_column("Likely service")
    for port, count in cap.top_ports():
        ports_table.add_row(str(port), f"{count:,}", _service_name(port))

    dst_table = Table(title="Top destinations", title_style="bold")
    dst_table.add_column("IP")
    dst_table.add_column("Packets", justify="right")
    for ip, count in cap.top_destinations():
        dst_table.add_row(ip, f"{count:,}")

    console.print(ports_table)
    console.print()
    console.print(dst_table)
    console.print()

    # --- Flow table -------------------------------------------------------
    classifier = AppClassifier()
    classified = classifier.classify_capture(cap, top_n=8)

    flow_table = Table(title="Top flows", title_style="bold", show_lines=False)
    flow_table.add_column("#", justify="right")
    flow_table.add_column("Proto")
    flow_table.add_column("Server")
    flow_table.add_column("Pkts", justify="right")
    flow_table.add_column("Bytes", justify="right")
    flow_table.add_column("Avg", justify="right")
    flow_table.add_column("Burst", justify="right")
    flow_table.add_column("RTT (ms)", justify="right")
    flow_table.add_column("App guess")

    for idx, (flow, guess) in enumerate(classified, start=1):
        rtt_str = f"{flow.rtt_ms:.1f}" if flow.rtt_ms is not None else "-"
        flow_table.add_row(
            str(idx),
            flow.key.proto,
            flow.key.server_side(),
            f"{flow.packets:,}",
            _human_bytes(flow.bytes_total),
            f"{flow.avg_pkt_size:.0f}",
            f"{flow.burstiness():.2f}",
            rtt_str,
            _guess_text(guess),
        )
    console.print(flow_table)
    console.print()

    # --- Detailed reasoning per flow -------------------------------------
    for idx, (flow, guess) in enumerate(classified, start=1):
        console.print(_flow_panel(idx, flow, guess))
        console.print()


def _service_name(port: int) -> str:
    services = {
        53: "DNS", 80: "HTTP", 443: "HTTPS / QUIC",
        8801: "Zoom media", 8802: "Zoom media", 8803: "Zoom media",
        3478: "STUN", 5060: "SIP", 5004: "RTP",
        25: "SMTP", 587: "SMTP-submission", 993: "IMAPS", 995: "POP3S",
    }
    if port in services:
        return services[port]
    if 50000 <= port <= 65535:
        return "ephemeral / Discord voice"
    return ""


def _guess_text(guess: AppGuess) -> Text:
    color = {
        "Zoom":         "magenta",
        "Discord":      "blue",
        "YouTube":      "red",
        "Spotify":      "green",
        "Web browsing": "yellow",
        "Unknown":      "dim",
    }.get(guess.app, "white")
    txt = Text(f"{guess.app} ({guess.confidence*100:.0f}%)", style=color)
    return txt


def _flow_panel(idx: int, flow: FlowStats, guess: AppGuess) -> Panel:
    body = Text()
    body.append(
        f"{flow.key.proto}  "
        f"{flow.key.endpoint_a}  <->  {flow.key.endpoint_b}\n",
        style="bold",
    )
    body.append(
        f"packets={flow.packets:,}   "
        f"bytes={_human_bytes(flow.bytes_total)}   "
        f"duration={flow.duration_s:.2f}s   "
        f"pps={flow.pps:.1f}   "
        f"avg={flow.avg_pkt_size:.0f}B   "
        f"p95={flow.p95_pkt_size:.0f}B   "
        f"burst CV={flow.burstiness():.2f}\n",
        style="dim",
    )
    if flow.rtt_ms is not None:
        body.append(
            f"TCP handshake RTT estimate: {flow.rtt_ms:.2f} ms\n",
            style="cyan",
        )
    body.append("\n")
    body.append(f"Verdict: {guess.app}", style="bold")
    body.append(f"   confidence={guess.confidence*100:.0f}%", style="dim")
    if guess.runner_up:
        body.append(
            f"   (runner-up: {guess.runner_up}, "
            f"{guess.runner_up_confidence*100:.0f}%)\n",
            style="dim",
        )
    else:
        body.append("\n")
    body.append("Why:\n", style="bold")
    for r in guess.reasons:
        body.append(f"  - {r}\n")

    return Panel(body, title=f"[bold]Flow #{idx}[/bold]",
                 border_style="cyan", padding=(0, 1))
