"""Stop-and-Wait reliable data transfer over a simulated lossy channel.

This is the rdt 3.0 protocol from Kurose & Ross, written tightly enough
to read in one sitting. The "channel" is just a function that drops
packets with a configurable probability; there is no real socket so the
demo is deterministic given a seed.

What you can read out of the run:
  - Every retransmission is logged with the cause (data drop vs ack drop).
  - Final throughput in packets-per-second falls sharply with loss --
    this is exactly the motivation for sliding-window pipelining.

Usage:
    python stop_and_wait.py                  # default 30 packets, 20% loss
    python stop_and_wait.py --loss 0.4       # heavier loss
    python stop_and_wait.py --packets 50 --quiet
"""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass


# Round-trip propagation in seconds for the simulated channel.
# Real-world WAN RTTs are 20-100 ms; we use a small value so the demo is fast.
ONE_WAY_DELAY = 0.005   # 5 ms each way -> 10 ms RTT
TIMEOUT = 0.030         # 30 ms -- ~3x RTT, the classic rule of thumb


@dataclass
class Stats:
    sent: int = 0
    retransmits_data_loss: int = 0
    retransmits_ack_loss: int = 0
    delivered: int = 0


def lossy_send(payload, drop_prob: float, rng: random.Random) -> bool:
    """Simulate channel: returns True if payload arrives, False if dropped."""
    time.sleep(ONE_WAY_DELAY)   # propagation
    return rng.random() >= drop_prob


def run(num_packets: int, loss: float, seed: int, *, verbose: bool = True) -> Stats:
    rng = random.Random(seed)
    stats = Stats()
    seq = 0   # 1-bit sequence number toggles 0/1

    start = time.perf_counter()

    for pkt_id in range(num_packets):
        delivered = False
        attempts = 0

        while not delivered:
            attempts += 1
            stats.sent += 1
            data_arrived = lossy_send(("DATA", seq, pkt_id), loss, rng)

            if not data_arrived:
                # Sender will time out waiting for an ACK that never comes.
                if verbose:
                    print(f"[pkt {pkt_id:>3}] seq={seq} attempt={attempts} "
                          f"DATA lost  -> timeout, retransmit")
                stats.retransmits_data_loss += 1
                time.sleep(TIMEOUT)
                continue

            # Receiver got the data; receiver always sends an ACK.
            ack_arrived = lossy_send(("ACK", seq), loss, rng)
            if not ack_arrived:
                if verbose:
                    print(f"[pkt {pkt_id:>3}] seq={seq} attempt={attempts} "
                          f"DATA ok, ACK lost -> timeout, retransmit")
                stats.retransmits_ack_loss += 1
                time.sleep(TIMEOUT - ONE_WAY_DELAY)
                continue

            if verbose:
                print(f"[pkt {pkt_id:>3}] seq={seq} attempt={attempts} "
                      f"delivered (RTT ~{2*ONE_WAY_DELAY*1000:.0f} ms)")
            delivered = True
            stats.delivered += 1
            seq ^= 1   # alternating-bit toggle

    elapsed = time.perf_counter() - start

    print()
    print(f"--- Stop-and-Wait summary (loss={loss:.0%}, n={num_packets}) ---")
    print(f"Packets delivered:           {stats.delivered}")
    print(f"Total transmissions:         {stats.sent}")
    print(f"Retransmits (data lost):     {stats.retransmits_data_loss}")
    print(f"Retransmits (ack lost):      {stats.retransmits_ack_loss}")
    print(f"Wall-clock elapsed:          {elapsed:.2f} s")
    print(f"Effective throughput:        {stats.delivered / elapsed:.1f} pkts/s")
    print(f"Channel efficiency:          {stats.delivered / stats.sent:.0%}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", type=int, default=30,
                        help="number of application packets to deliver")
    parser.add_argument("--loss", type=float, default=0.2,
                        help="per-direction drop probability (0.0-0.95)")
    parser.add_argument("--seed", type=int, default=441)
    parser.add_argument("--quiet", action="store_true",
                        help="suppress per-packet log lines")
    args = parser.parse_args()

    if not 0.0 <= args.loss < 0.95:
        parser.error("loss must be in [0.0, 0.95)")

    run(args.packets, args.loss, args.seed, verbose=not args.quiet)

    print("\nTry: python stop_and_wait.py --loss 0.0   # no loss baseline")
    print("Try: python stop_and_wait.py --loss 0.5   # heavy loss")


if __name__ == "__main__":
    main()
