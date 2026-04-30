"""
Command-line interface.

Examples:
  python -m traffic_analyzer analyze pcaps/zoom.pcap
  python -m traffic_analyzer analyze pcaps/mixed.pcap --charts reports/mixed/
  python -m traffic_analyzer generate mixed pcaps/mixed.pcap
"""

from __future__ import annotations

import argparse
import os
import sys

from rich.console import Console

from .analyzer import PcapAnalyzer
from .pcap_generator import generate as generate_pcap
from .reporter import render_terminal_report
from .visualizer import render_all_charts


def _cmd_analyze(args: argparse.Namespace) -> int:
    if not os.path.isfile(args.pcap):
        print(f"error: pcap file not found: {args.pcap}", file=sys.stderr)
        return 2

    console = Console()
    console.print(f"[dim]Reading[/dim] [bold]{args.pcap}[/bold] ...")

    analyzer = PcapAnalyzer(args.pcap)
    cap = analyzer.analyze()

    render_terminal_report(cap, args.pcap, console=console)

    if args.charts:
        console.print(f"[dim]Writing charts to[/dim] [bold]{args.charts}[/bold] ...")
        paths = render_all_charts(cap, args.charts)
        for p in paths:
            console.print(f"  - {p}")
        console.print()
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    out_dir = os.path.dirname(args.out) or "."
    os.makedirs(out_dir, exist_ok=True)
    generate_pcap(args.name, args.out)
    print(f"wrote {args.out}")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    """One-shot: generate all pcaps + run analysis on the mixed file."""
    pcap_dir = args.pcap_dir
    report_dir = args.report_dir
    os.makedirs(pcap_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    print("[1/3] generating synthetic pcaps ...")
    for name in ("zoom", "discord", "youtube", "spotify", "web", "mixed"):
        path = os.path.join(pcap_dir, f"{name}.pcap")
        generate_pcap(name, path)
        print(f"      {path}")

    target = os.path.join(pcap_dir, "mixed.pcap")
    print(f"[2/3] analyzing {target} ...")
    cap = PcapAnalyzer(target).analyze()

    console = Console()
    render_terminal_report(cap, target, console=console)

    print(f"[3/3] writing charts to {report_dir} ...")
    paths = render_all_charts(cap, report_dir)
    for p in paths:
        print(f"      {p}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="traffic_analyzer",
        description='Wireshark Traffic Analyzer -- "What App Are You Really Using?"',
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_analyze = sub.add_parser("analyze", help="Analyze a pcap file")
    p_analyze.add_argument("pcap", help="Path to .pcap or .pcapng file")
    p_analyze.add_argument("--charts", default=None,
                           help="Output directory for chart PNGs")
    p_analyze.set_defaults(func=_cmd_analyze)

    p_gen = sub.add_parser("generate", help="Generate a synthetic demo pcap")
    p_gen.add_argument("name",
                       choices=["zoom", "discord", "youtube",
                                "spotify", "web", "mixed"])
    p_gen.add_argument("out", help="Output .pcap path")
    p_gen.set_defaults(func=_cmd_generate)

    p_demo = sub.add_parser(
        "demo",
        help="One-command demo: generate pcaps, analyze mixed.pcap, write charts",
    )
    p_demo.add_argument("--pcap-dir", default="pcaps")
    p_demo.add_argument("--report-dir", default="reports/mixed")
    p_demo.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
