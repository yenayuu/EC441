"""
End-to-end tests. Each test generates a synthetic pcap for one app,
runs it through the analyzer + classifier, and checks that the top
flow lands on the right verdict.

Run from the project root:
    python -m unittest discover tests
"""

from __future__ import annotations

import os
import tempfile
import unittest

from traffic_analyzer.analyzer import PcapAnalyzer
from traffic_analyzer.classifier import AppClassifier
from traffic_analyzer.pcap_generator import generate


class ClassifierEndToEnd(unittest.TestCase):
    def _top_flow_app(self, name: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, f"{name}.pcap")
            generate(name, path)
            cap = PcapAnalyzer(path).analyze()
            classifier = AppClassifier()
            top_flow = cap.flow_list()[0]
            return classifier.classify_flow(top_flow).app

    def test_zoom(self) -> None:
        self.assertEqual(self._top_flow_app("zoom"), "Zoom")

    def test_discord(self) -> None:
        self.assertEqual(self._top_flow_app("discord"), "Discord")

    def test_youtube(self) -> None:
        self.assertEqual(self._top_flow_app("youtube"), "YouTube")

    def test_spotify(self) -> None:
        self.assertEqual(self._top_flow_app("spotify"), "Spotify")

    def test_web(self) -> None:
        # Top flow on the web pcap should be the largest single-page session;
        # the classifier should confidently call it Web browsing.
        self.assertEqual(self._top_flow_app("web"), "Web browsing")


class CaptureStatsBasics(unittest.TestCase):
    def test_zoom_pcap_has_udp_only(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "zoom.pcap")
            generate("zoom", path)
            cap = PcapAnalyzer(path).analyze()
            self.assertEqual(cap.tcp_packets, 0)
            self.assertGreater(cap.udp_packets, 100)
            self.assertGreater(cap.duration_s, 1.0)

    def test_youtube_has_rtt_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "youtube.pcap")
            generate("youtube", path)
            cap = PcapAnalyzer(path).analyze()
            top = cap.flow_list()[0]
            self.assertIsNotNone(top.rtt_ms)
            assert top.rtt_ms is not None
            self.assertGreater(top.rtt_ms, 5.0)
            self.assertLess(top.rtt_ms, 200.0)


if __name__ == "__main__":
    unittest.main()
