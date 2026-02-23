# Week 01 — Physical Layer: Wireless Communications

**Type:** Problem Set with Worked Solutions


**Topic:** Physical Layer — path loss, link budgets, modulation, cellular reuse

**Course:** EC 441, Spring 2026

---

## Problem 1: Free-Space Path Loss

A 5 GHz WiFi access point transmits at 23 dBm. A laptop is 200 m away in an open field (free space). Both antennas have a gain of 3 dBi.

**(a)** Calculate the free-space path loss (FSPL) in dB.

**(b)** What is the received power at the laptop?

**(c)** If the receiver sensitivity is −82 dBm, what is the link margin? Is this a reliable link?

### Solution

**(a)** Using the FSPL formula:

$$
L_{\text{FSPL}}(\text{dB}) = 32.45 + 20\log_{10}(f_{\text{MHz}}) + 20\log_{10}(d_{\text{km}})
$$

Substituting $f = 5000$ MHz and $d = 0.2$ km:

$$
L_{\text{FSPL}} = 32.45 + 20\log_{10}(5000) + 20\log_{10}(0.2)
$$

$$
= 32.45 + 73.98 + (-13.98) = 92.45 \text{ dB}
$$

**(b)** Using the link budget equation:

$$
P_r = P_t + G_t + G_r - L_{\text{FSPL}}
$$

$$
P_r = 23 + 3 + 3 - 92.45 = -63.45 \text{ dBm}
$$

**(c)** Link margin:

$$
\text{Margin} = P_r - S_{\min} = -63.45 - (-82) = 18.55 \text{ dB}
$$

This is above the 10–15 dB threshold for static links, so the link is reliable in free space. However, in a real environment with fading (which can require 20–30 dB margin), this margin could be marginal.

---

## Problem 2: Indoor Propagation with Empirical Model

A WiFi router operates at 2.4 GHz with $P_t = 20$ dBm and antenna gains $G_t = G_r = 2$ dBi. A reference measurement at $d_0 = 1$ m gives $L_0 = 40$ dB. The path loss exponent in this office (NLOS) is $n = 3.5$.

**(a)** What is the expected received power at 25 m?

**(b)** If shadow fading has $\sigma = 8$ dB, is a 10 dB fading margin sufficient for this link?

### Solution

**(a)** Using the empirical path loss model (ignoring fading):

$$
L(d) = L_0 + 10n\log_{10}\!\left(\frac{d}{d_0}\right)
$$

$$
L(25) = 40 + 10(3.5)\log_{10}\!\left(\frac{25}{1}\right) = 40 + 35 \times 1.398 = 40 + 48.93 = 88.93 \text{ dB}
$$

Received power:

$$
P_r = 20 + 2 + 2 - 88.93 = -64.93 \text{ dBm}
$$

**(b)** Shadow fading adds a random variable $X_\sigma$ to the path loss, with typical $\sigma = 4$–$12$ dB. With $\sigma = 8$ dB, a 10 dB fading margin only covers about 1.25σ of variation. Given that the slides recommend 10–20 dB of fading margin, 10 dB is at the low end and may not be reliable enough — especially in an indoor NLOS environment where fading can be severe. A margin of at least 16 dB (2σ) would provide more confidence.

In this case, the received power without fading is $-64.93$ dBm and typical WiFi sensitivity is around $-80$ to $-90$ dBm, giving us roughly 15–25 dB of margin before the link drops. So this link has enough headroom to handle shadow fading comfortably.

---

## Problem 3: QAM and Data Rates

A wireless system uses 64-QAM modulation with a symbol rate of 10 Msymbols/s.

**(a)** How many bits per symbol does 64-QAM carry?

**(b)** What is the raw (uncoded) data rate?

**(c)** If the system switches to 256-QAM, what is the new data rate? What is the tradeoff?

### Solution

**(a)** In $M$-QAM, each symbol represents $\log_2(M)$ bits:

$$
\log_2(64) = 6 \text{ bits/symbol}
$$

**(b)** Raw data rate = bits/symbol × symbol rate:

$$
R = 6 \times 10 \times 10^6 = 60 \text{ Mbps}
$$

**(c)** With 256-QAM: $\log_2(256) = 8$ bits/symbol.

$$
R = 8 \times 10 \times 10^6 = 80 \text{ Mbps}
$$

**Tradeoff:** 256-QAM packs constellation points closer together, requiring a higher SNR to distinguish them reliably. In environments with more noise or fading, 256-QAM will have a much higher bit error rate. This is why modern systems use **adaptive modulation** — they choose higher-order QAM when the channel is clean and fall back to lower-order QAM (e.g., QPSK) when it is not.

---

## Problem 4: Cellular Frequency Reuse

A cellular network has hexagonal cells with radius $R = 1$ km and uses a cluster size of $N = 7$. The path loss exponent is $n = 4$.

**(a)** What is the reuse distance $D$?

**(b)** Calculate the carrier-to-interference ratio (C/I) assuming 6 co-channel interferers in the first tier.

**(c)** If the system requires a minimum C/I of 18 dB, does this design meet the requirement? What happens if the operator switches to $N = 4$?

### Solution

**(a)** Reuse distance:

$$
D = R\sqrt{3N} = 1 \times \sqrt{3 \times 7} = \sqrt{21} \approx 4.58 \text{ km}
$$

**(b)** Using the C/I approximation:

$$
\frac{C}{I} = \frac{(3N)^{n/2}}{6}
$$

For $N = 7$, $n = 4$:

$$
\frac{C}{I} = \frac{(21)^{2}}{6} = \frac{441}{6} = 73.5 \approx 18.66 \text{ dB}
$$

Wait — let me recompute more carefully:

$$
\frac{C}{I} = \frac{(3 \times 7)^{4/2}}{6} = \frac{21^2}{6} = \frac{441}{6} = 73.5
$$

In dB: $10\log_{10}(73.5) \approx 18.66$ dB.

**(c)** With $N = 7$: C/I ≈ 18.66 dB — this just barely meets the 18 dB requirement.

With $N = 4$:

$$
\frac{C}{I} = \frac{(12)^{2}}{6} = \frac{144}{6} = 24
$$

In dB: $10\log_{10}(24) \approx 13.8$ dB — this does **not** meet the 18 dB requirement.

So reducing the cluster size to $N = 4$ would increase capacity (more frequencies per cell) but at the cost of unacceptable interference. The operator would need advanced interference management techniques (like those used in LTE/5G with $N = 1$) to make smaller cluster sizes work.

---

## Problem 5: Link Budget — Cellular Uplink

A mobile phone transmits at 23 dBm on an LTE band at 1900 MHz. The base station antenna gain is 18 dBi (sector antenna), and the phone antenna gain is 0 dBi. The cell radius is 2 km in an urban environment with path loss exponent $n = 3.5$. Reference path loss at 1 m is $L_0 = 38$ dB. The base station receiver sensitivity is −104 dBm.

**(a)** What is the path loss at the cell edge?

**(b)** What is the received power at the base station?

**(c)** What is the link margin? Is it sufficient for a mobile environment?

### Solution

**(a)** Path loss at $d = 2000$ m:

$$
L = L_0 + 10n\log_{10}\!\left(\frac{d}{d_0}\right) = 38 + 10(3.5)\log_{10}(2000)
$$

$$
= 38 + 35 \times 3.301 = 38 + 115.54 = 153.54 \text{ dB}
$$

**(b)** Received power:

$$
P_r = P_t + G_t + G_r - L = 23 + 0 + 18 - 153.54 = -112.54 \text{ dBm}
$$

**(c)** Margin:

$$
\text{Margin} = P_r - S_{\min} = -112.54 - (-104) = -8.54 \text{ dB}
$$

The margin is **negative**, meaning the link fails at the cell edge under average conditions. The signal doesn't reach the base station with enough power. Solutions include:

- **Reduce cell radius** (add more towers)
- **Increase transmit power** (limited by battery and regulations)
- **Use a higher-gain base station antenna**
- **Lower the receiver noise figure** to improve sensitivity
- **Use MIMO** to get array gain

This illustrates why operators must carefully plan cell sizes and why dense urban areas need many small cells.
