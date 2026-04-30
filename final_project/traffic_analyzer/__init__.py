"""
Wireshark Traffic Analyzer — "What App Are You Really Using?"

A pcap-driven traffic-fingerprinting tool that classifies flows into
likely applications (Zoom, Discord, YouTube, Spotify, Web browsing)
and reports the network-layer evidence behind the guess.

Built for EC 441 Final Project, Spring 2026.
"""

from .analyzer import PcapAnalyzer, FlowKey, FlowStats, CaptureStats
from .classifier import AppClassifier, AppGuess
from .reporter import render_terminal_report
from .visualizer import render_all_charts

__all__ = [
    "PcapAnalyzer",
    "FlowKey",
    "FlowStats",
    "CaptureStats",
    "AppClassifier",
    "AppGuess",
    "render_terminal_report",
    "render_all_charts",
]

__version__ = "1.0.0"
