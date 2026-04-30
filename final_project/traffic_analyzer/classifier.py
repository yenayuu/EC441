"""
Heuristic application classifier.

For each flow we compute a feature vector (proto, server port, mean packet
size, packet rate, burstiness, payload symmetry) and score it against a
small set of hand-tuned application fingerprints.

This is deliberately *transparent*: every guess comes with a list of
human-readable reasons so you can defend it during the live demo.

Fingerprints are based on public documentation and our own captures:

  Zoom         - mostly UDP to ports 8801-8810, ~150-1100 B packets,
                 very regular ~20 ms inter-arrivals (audio frames),
                 strong bidirectional symmetry.
  Discord      - UDP voice (RTP-style) on ports 50000-65535, similar
                 audio cadence to Zoom but typically a single peer
                 server, plus TCP/443 WebSocket gateway.
  YouTube      - TCP/443 or QUIC (UDP/443), large MTU-sized packets,
                 bursty download pattern (ABR chunks), very asymmetric
                 (server -> client dominates).
  Spotify      - TCP/443 to CDN, mid-size packets, smaller ABR chunks
                 than YouTube, also asymmetric download-heavy.
  Web browsing - TCP/443 (or QUIC) to many distinct destinations,
                 short-lived flows, mixed packet sizes, low burst regularity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .analyzer import CaptureStats, FlowStats


@dataclass
class AppGuess:
    app: str
    confidence: float  # 0..1
    reasons: list[str] = field(default_factory=list)
    runner_up: str | None = None
    runner_up_confidence: float = 0.0


@dataclass
class _Score:
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def add(self, points: float, reason: str) -> None:
        self.score += points
        self.reasons.append(f"{reason} (+{points:.1f})")


_APPS = ("Zoom", "Discord", "YouTube", "Spotify", "Web browsing")


class AppClassifier:
    """Score a flow against each application fingerprint."""

    def classify_flow(self, flow: FlowStats) -> AppGuess:
        scores: dict[str, _Score] = {app: _Score() for app in _APPS}

        proto = flow.key.proto
        avg_size = flow.avg_pkt_size
        p95_size = flow.p95_pkt_size
        burst = flow.burstiness()
        pps = flow.pps
        symmetry = self._symmetry(flow)

        self._score_zoom(scores["Zoom"], proto, flow, avg_size, burst, pps, symmetry)
        self._score_discord(scores["Discord"], proto, flow, avg_size, burst, pps, symmetry)
        self._score_youtube(scores["YouTube"], proto, flow, avg_size, p95_size, symmetry)
        self._score_spotify(scores["Spotify"], proto, flow, avg_size, p95_size, symmetry)
        self._score_web(scores["Web browsing"], proto, flow, avg_size, burst, symmetry)

        ranked = sorted(scores.items(), key=lambda kv: kv[1].score, reverse=True)
        winner_app, winner = ranked[0]
        runner_app, runner = ranked[1]

        total = sum(s.score for _, s in ranked) or 1.0
        confidence = winner.score / total

        if winner.score < 1.0:
            return AppGuess(
                app="Unknown",
                confidence=0.0,
                reasons=["No fingerprint scored high enough to classify confidently."],
                runner_up=winner_app,
                runner_up_confidence=confidence,
            )

        return AppGuess(
            app=winner_app,
            confidence=confidence,
            reasons=winner.reasons,
            runner_up=runner_app,
            runner_up_confidence=runner.score / total,
        )

    def classify_capture(self, cap: CaptureStats, top_n: int = 5) -> list[tuple[FlowStats, AppGuess]]:
        results = []
        for flow in cap.flow_list()[:top_n]:
            if flow.packets < 5:  # skip noise
                continue
            results.append((flow, self.classify_flow(flow)))
        return results

    @staticmethod
    def _symmetry(flow: FlowStats) -> float:
        """Return a value in [0, 1]; 1.0 = perfectly bidirectional."""
        a, b = flow.bytes_a_to_b, flow.bytes_b_to_a
        total = a + b
        if total == 0:
            return 0.0
        smaller = min(a, b)
        return (2.0 * smaller) / total

    @staticmethod
    def _score_zoom(s: _Score, proto: str, flow: FlowStats, avg: float,
                    burst: float, pps: float, symmetry: float) -> None:
        if proto != "UDP":
            return
        s.add(2.0, "UDP transport (Zoom RTP-style media)")
        zoom_port = next((p for p in flow.key.ports if 8801 <= p <= 8810), None)
        if zoom_port is not None:
            s.add(4.0, f"port {zoom_port} in Zoom range 8801-8810")
        elif flow.key.has_any_port(3478, 3479):
            s.add(1.0, "STUN port (used by Zoom for NAT traversal)")
        if 80 <= avg <= 350:
            s.add(2.0, f"avg packet size {avg:.0f} B fits Zoom audio frames")
        elif 350 < avg <= 1100:
            s.add(1.5, f"avg packet size {avg:.0f} B fits Zoom video frames")
        if burst < 0.5 and pps > 30:
            s.add(2.0, f"very regular cadence (CV={burst:.2f}, {pps:.0f} pps) -> realtime media")
        if symmetry > 0.4:
            s.add(1.5, f"strong bidirectional symmetry ({symmetry:.2f}) -> 2-way call")

    @staticmethod
    def _score_discord(s: _Score, proto: str, flow: FlowStats, avg: float,
                       burst: float, pps: float, symmetry: float) -> None:
        if proto == "UDP":
            # If a Zoom-range port is present, Discord shouldn't claim this flow.
            if any(8801 <= p <= 8810 for p in flow.key.ports):
                return
            s.add(1.5, "UDP transport (Discord voice over RTP)")
            disc_port = next(
                (p for p in flow.key.ports if 50000 <= p <= 65535), None
            )
            if disc_port is not None:
                s.add(3.5, f"port {disc_port} in Discord voice range (50000-65535)")
            if 60 <= avg <= 250:
                s.add(2.0, f"avg packet size {avg:.0f} B fits Opus voice frames")
            if burst < 0.5 and pps > 30:
                s.add(1.5, f"steady realtime cadence (CV={burst:.2f}, {pps:.0f} pps)")
            if symmetry > 0.4:
                s.add(1.0, f"bidirectional voice ({symmetry:.2f})")
        elif proto == "TCP" and flow.key.has_any_port(443):
            s.add(0.3, "TCP/443 could be Discord WebSocket gateway (weak signal)")

    @staticmethod
    def _score_youtube(s: _Score, proto: str, flow: FlowStats, avg: float,
                       p95: float, symmetry: float) -> None:
        if not flow.key.has_any_port(443):
            return
        # Gate: a single page-resource fetch shouldn't masquerade as a video.
        size_mb = flow.bytes_total / 1_000_000
        if size_mb < 0.3 and flow.duration_s < 5:
            return
        if proto == "TCP":
            s.add(1.0, "TCP/443 (HTTPS video transport)")
        else:
            s.add(1.5, "UDP/443 (QUIC -- YouTube uses HTTP/3)")
        if p95 >= 1300:
            s.add(2.0, f"p95 packet size {p95:.0f} B near MTU -> bulk download")
        if avg >= 900:
            s.add(1.5, f"avg packet size {avg:.0f} B is large -> video chunks")
        if symmetry < 0.2:
            s.add(2.0, f"highly asymmetric ({symmetry:.2f}) -> server -> client streaming")
        if size_mb >= 1.0:
            s.add(2.5, f"large transfer ({size_mb:.1f} MB) -> sustained video stream")
        if flow.duration_s >= 5.0:
            s.add(1.0, f"long-lived flow ({flow.duration_s:.1f}s) -> streaming session")

    @staticmethod
    def _score_spotify(s: _Score, proto: str, flow: FlowStats, avg: float,
                       p95: float, symmetry: float) -> None:
        if proto != "TCP" or not flow.key.has_any_port(443):
            return
        s.add(0.8, "TCP/443 to CDN (HTTPS audio)")
        if 500 <= avg <= 1100:
            s.add(2.0, f"avg packet size {avg:.0f} B fits audio chunk transfers")
        if 1100 <= p95 <= 1500:
            s.add(1.0, f"p95 {p95:.0f} B -> some MTU-sized chunks but not all")
        if symmetry < 0.3:
            s.add(2.0, f"download-heavy ({symmetry:.2f}) -> streaming audio")
        size_mb = flow.bytes_total / 1_000_000
        if 0.3 <= size_mb <= 20.0:
            s.add(1.5, f"transfer size {size_mb:.1f} MB matches an audio track")
        elif size_mb > 50:
            s.add(-2.0, f"transfer too large ({size_mb:.1f} MB) for one Spotify track")

    @staticmethod
    def _score_web(s: _Score, proto: str, flow: FlowStats, avg: float,
                   burst: float, symmetry: float) -> None:
        web_port = next(
            (p for p in flow.key.ports if p in (80, 443, 8080, 8443)), None,
        )
        if web_port is None:
            return
        s.add(1.0, f"TCP/{web_port} (web traffic)")
        if proto == "TCP":
            s.add(0.5, "TCP transport (HTTP/1.1, HTTP/2)")
        if 200 <= avg <= 900:
            s.add(1.0, f"mixed packet sizes (avg {avg:.0f} B) typical for web pages")
        if burst > 0.8:
            s.add(1.5, f"bursty traffic (CV={burst:.2f}) -> request/response pattern")
        if 0.15 <= symmetry <= 0.55:
            s.add(1.0, f"moderate asymmetry ({symmetry:.2f}) -> small reqs, larger resps")
        kb = flow.bytes_total / 1024
        if kb < 200:
            s.add(2.0, f"small transfer ({kb:.0f} KB) -> single page resource")
        if flow.duration_s < 5 and flow.packets < 300:
            s.add(1.5, f"short flow ({flow.duration_s:.1f}s, {flow.packets} pkts) -> page load")
