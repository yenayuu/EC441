# Week 08 — Cryptography and Security: From Primitives to TLS

**Course:** EC 441 — Introduction to Computer Networking, Boston University, Spring 2026

**Type:** Report

**Source:** Lecture 24 — Cryptography and Security: From Primitives to TLS

---

## 1. Introduction

Lecture 24 is the security capstone of the course. Up to this point, every protocol the course covered — Ethernet, IP, TCP, UDP, DNS, HTTP — runs in **cleartext** by default. Lecture 23 ended with the blunt observation that "everything you watched today, `tcpdump` could read." Lecture 24 supplies the answer: a small set of cryptographic primitives, and the way **TLS 1.3** assembles them into the security the modern web depends on.

The lecture is split into two halves:

1. **Session 1 — mathematical:** the four core security goals, symmetric vs. asymmetric crypto, hash functions, and a worked derivation of **RSA** from Euler's theorem.
2. **Session 2 — practical:** how the primitives compose into MACs, digital signatures, **PKI**, and a full **TLS 1.3** handshake.

Throughout, the lecture uses three actors: **α** (sender), **β** (receiver), and **τ** (adversary).

---

## 2. Threat Model and the Four Security Requirements

Every cryptographic primitive in the lecture answers a specific threat from a single table.

| Attack | What τ does | Requirement |
|---|---|---|
| Eavesdrop | Read the message | **Confidentiality** |
| Modify | Flip bits in flight | **Integrity** |
| Impersonate | Pretend to be the peer | **Authentication** |
| Replay | Resend a captured message | **Freshness** |
| Deny | "I never sent that" | **Non-repudiation** |

Building security is the process of addressing these threats one at a time, each with an appropriate primitive. Every later section maps back to a row of this table.

---

## 3. Symmetric Cryptography

α and β share a secret key `k`. The same key is used for both encryption and decryption:

```
c = E_k(m)         m = D_k(c)
```

**Workhorse: AES.** The Advanced Encryption Standard (Rijndael, NIST FIPS 197, 2001) operates on **128-bit blocks** with **128/192/256-bit keys**. Hardware-accelerated on essentially every modern CPU via **AES-NI** instructions, so AES-GCM runs at multiple GB/s per core on a laptop — effectively free.

**Block cipher modes.** The raw block cipher only encrypts a single 128-bit block. Longer messages need a *mode of operation*:

| Mode | Property | Notes |
|---|---|---|
| **ECB** (Electronic Codebook) | Each block independently | Plaintext patterns leak (the famous "ECB penguin"). Never use. |
| **CBC** (Cipher Block Chaining) | XOR with previous ciphertext + IV | Confidentiality only, no integrity. Legacy. |
| **GCM** (Galois Counter Mode) | **AEAD** — confidentiality + integrity in one primitive | What TLS 1.3 uses. |

### The key distribution problem

Symmetric crypto only works if α and β already share `k`. How do they agree on `k` if τ is on the wire? The lecture gives three answers, each developed in the sections that follow:

- **Pre-shared keys** — works, doesn't scale to the open Internet.
- **Asymmetric crypto** to transport the key — the classic TLS 1.2 pattern.
- **Diffie–Hellman key agreement** — the TLS 1.3 pattern.

---

## 4. Hash Functions

A hash function maps an arbitrary-length input to a fixed-length **digest**:

```
h : {0,1}* → {0,1}^n
```

**SHA-256** has n = 256; **SHA-512** has n = 512.

**Not encryption.** There is no key, and no way to "decrypt." A hash is a one-way **fingerprint** of the data.

### Three security properties

1. **Preimage resistance.** Given y = h(m), it is infeasible to find any m' with h(m') = y. (You cannot invert the hash.)
2. **Second-preimage resistance.** Given m, infeasible to find a different m' with h(m') = h(m).
3. **Collision resistance.** Infeasible to find *any* pair m ≠ m' with h(m) = h(m').

By the **birthday paradox**, collision resistance on an n-bit hash gives only ~2^(n/2) security. SHA-256 therefore offers ~2^128 collision resistance — well beyond practical attack.

**Uses.** File integrity (publish a SHA-256 next to a download), password storage (`h(salt || password)` — never the password itself), commitment schemes, blockchain block linking, and as a building block for MACs and digital signatures.

The lecture's `demo_hash_l24.py` script reinforces three observations:

- Output size is fixed regardless of input size (0 B, 1 B, and 1 MB inputs all produce 256-bit outputs).
- **Avalanche effect:** changing one character flips ~50% of output bits.
- A toy commitment scheme: α publishes `h(nonce || bid)` and can only "open" it to the original bid.

---

## 5. Asymmetric Cryptography and RSA

Each party holds a **key pair**: public key `K_pub` and private key `K_priv`. The keys are mathematically linked, but knowing `K_pub` does not reveal `K_priv`. Two operations:

- **Encryption.** Anyone with β's *public* key can encrypt; only β (with the matching *private* key) can decrypt. → confidentiality.
- **Signing.** The holder of a private key produces a signature anyone can verify with the public key. → authentication, integrity, non-repudiation.

> Encryption uses the **receiver's public key**; signing uses the **sender's private key**. This asymmetry is the whole point.

### 5.1 Number theory background

**Euler's totient.** φ(n) is the count of integers in [1, n] coprime to n.

- For prime p: φ(p) = p − 1.
- For n = pq (distinct primes): φ(n) = (p − 1)(q − 1).

**Euler's theorem.** If gcd(a, n) = 1, then

```
a^φ(n) ≡ 1 (mod n)
```

Fermat's little theorem is the prime-n special case. RSA is essentially a three-line corollary.

### 5.2 RSA key generation

1. Choose two large primes p, q (1024 bits each in practice).
2. Compute n = pq and φ(n) = (p − 1)(q − 1).
3. Choose a public exponent e with gcd(e, φ(n)) = 1. Almost always **e = 65537**.
4. Compute d = e^(−1) mod φ(n) using the **extended Euclidean algorithm**.

**Public key:** (n, e). **Private key:** (n, d).

### 5.3 Encryption / decryption

Encode the message as an integer m with 0 ≤ m < n.

```
Encrypt:  c = m^e mod n
Decrypt:  m = c^d mod n
```

### 5.4 Why it works

We chose ed ≡ 1 (mod φ(n)), so ed = 1 + kφ(n) for some integer k. For m coprime to n:

```
c^d = m^(ed) = m · (m^φ(n))^k ≡ m · 1^k ≡ m (mod n)
```

by Euler's theorem. The case gcd(m, n) > 1 also works via the Chinese Remainder Theorem but is rarely relevant for properly-sized RSA.

### 5.5 Why it's secure

An attacker who knows (n, e) and wants d needs φ(n) = (p − 1)(q − 1), which requires **factoring** n. Factoring a 2048-bit semiprime is believed to take ~2^112 operations classically — well beyond feasibility. **Shor's algorithm** on a sufficiently large quantum computer factors in polynomial time, which is why **post-quantum cryptography** is an active research area.

### 5.6 Worked numerical example

Using the lecture's tiny example (`demo_rsa_math_l24.py`):

- p = 11, q = 13.
- n = 11 · 13 = **143**.
- φ(n) = 10 · 12 = **120**.
- Pick e = 7 (coprime to 120).
- Solve 7d ≡ 1 (mod 120) → **d = 103** (check: 7 · 103 = 721 = 6·120 + 1). ✓

Encrypt m = 9:

```
c = 9^7 mod 143 = 4,782,969 mod 143 = 48
```

Decrypt c = 48:

```
m = 48^103 mod 143 = 9   ✓
```

The full math fits on one page — that is the lecture's point about RSA's elegance.

### 5.7 Signing

RSA signing reuses the same math with the key roles **swapped**:

```
Sign:    s = h(m)^d mod n
Verify:  s^e mod n  ?=  h(m)
```

The signer applies the *private* exponent; any verifier applies the *public* exponent. We sign a **hash** of the message — never the raw message — for two reasons:

1. **Efficiency.** One exponentiation handles any message length.
2. **Security.** Textbook RSA on raw m has known forgery attacks via its multiplicativity. **RSA-PSS** padding avoids them.

---

## 6. Diffie–Hellman Key Exchange

Where asymmetric encryption *transports* a key, Diffie–Hellman *agrees* on one without ever transmitting it.

**Public parameters:** a large prime p and a generator g of (ℤ/pℤ)*. Both can be public knowledge.

**Protocol:**

1. α picks private a; sends A = g^a mod p.
2. β picks private b; sends B = g^b mod p.
3. α computes B^a = g^(ab) mod p.
4. β computes A^b = g^(ab) mod p.

α and β now share **g^(ab) mod p** without ever having sent it. τ saw only g^a and g^b on the wire and would have to solve the **discrete logarithm problem** to recover the secret — believed hard.

### Ephemeral DH and forward secrecy

Every modern TLS connection uses **ephemeral** Diffie–Hellman, usually on an elliptic curve (**ECDHE**). The server's long-term RSA or ECDSA key is used **only to sign** the DH public share, never to transport the session key. Consequence: even if the server's long-term private key leaks tomorrow, traffic captured today cannot be decrypted, because the session key was derived from ephemeral values that were immediately discarded. This property is **forward secrecy**, and it is precisely why TLS 1.3 *removed* the older RSA key-transport mode entirely.

---

## 7. Mapping Primitives to Requirements

With every primitive in hand, the threat-model table from §2 becomes concrete:

| Requirement | Primitive | Notes |
|---|---|---|
| Confidentiality | AES-GCM (or other AEAD) | Fast, shared key |
| Integrity (message) | MAC or AEAD | Hash + key |
| Authentication (peer) | Signature or MAC | "Who are you?" |
| Authentication (message origin) | MAC | "Someone with the key wrote this" |
| **Non-repudiation** | **Signature** (asymmetric only) | Third-party verifiable |
| Freshness | Nonces, timestamps | Protocol-level |

> **Why signatures, not MACs, give non-repudiation.** A MAC proves "somebody who knows `k` wrote this." But α and β *both* know `k`, so neither can prove to a third party which of them sent the message. A signature is made with a private key only one party holds, and the signature is verifiable by anyone with the public key. That is why legal and financial systems are built on signatures rather than MACs.

---

## 8. MACs and Digital Signatures

### 8.1 MAC — Message Authentication Code

Given a shared key `k`, a MAC simultaneously provides:

- **Integrity:** the message has not been modified.
- **Authentication:** it came from someone who knows `k`.

**HMAC** (RFC 2104) is the standard construction:

```
HMAC_k(m) = h( (k ⊕ opad) || h( (k ⊕ ipad) || m ) )
```

The two-level hash defends against length-extension attacks on naive `h(k || m)`. **HMAC-SHA-256** is a common default. In modern TLS, MACs are subsumed by **AEAD** (e.g., AES-GCM), which folds encryption and authentication into a single primitive.

### 8.2 Digital signatures

```
s = Sign(K_priv, h(m))
Verify(K_pub, s, h(m)) ∈ {True, False}
```

Signatures provide integrity, peer authentication, **and** non-repudiation — the last because only the private-key holder could have produced `s`, and any third party can check it.

**Modern alternatives to RSA.** Elliptic-curve signatures are dramatically smaller for the same security:

| Scheme | Signature size |
|---|---|
| RSA-2048 | 256 bytes |
| Ed25519 | ~64 bytes |

Most new systems default to **Ed25519** or **ECDSA**.

---

## 9. Public Key Infrastructure (PKI)

We have signatures, but a public key on its own is just bits — it says nothing about *whose* key it is. An attacker τ can generate any number of key pairs and claim to be anyone. The fix is **certificates**:

```
cert = { identity, K_pub, validity, ... } + signature by a CA
```

A **Certificate Authority (CA)** is a trusted third party. Browsers and operating systems ship a **root store**: a preinstalled list of CA public keys.

### Chain of trust

In practice, certificates chain:

```
leaf cert  ──signed by──▶  intermediate CA  ──signed by──▶  root CA
```

A browser walks the chain from leaf to a root in its store. Roots are few (hundreds globally), intermediates are many, leaves are one per domain (or wildcard).

### 9.1 Let's Encrypt

Free, automated (the **ACME** protocol), launched in 2016. HTTPS share of web traffic went from ~30% in 2015 to ~95% today, largely because Let's Encrypt made certificates **free and automatic**. It changed the economics of "HTTPS by default."

### 9.2 When CAs go bad

CA compromise is a catastrophic trust failure. Two real cases:

- **DigiNotar (2011).** Compromised; attacker issued fraudulent `*.google.com` certificates used to intercept Iranian users' Gmail. Removed from every major root store; the company went bankrupt within weeks.
- **Symantec (2017–18).** Google progressively distrusted Symantec's CA hierarchy after a string of mis-issuance incidents. Symantec eventually sold its CA business to DigiCert.

These show the recovery process *works*: compromised CAs are removed and the rest of the system keeps functioning.

**Certificate pinning.** Apps (and selectively, browsers, for a curated set of domains) can "pin" to a specific expected certificate or public key rather than trusting the entire root store. Defense in depth, but operationally fragile — a hard-coded pin means certificate rotation requires an app update.

### 9.3 Inspecting a real cert chain

The lecture's `demo_openssl_client_l24.sh` uses:

```bash
openssl s_client -connect bu.edu:443 -servername bu.edu < /dev/null
openssl s_client -connect expired.badssl.com:443 -servername expired.badssl.com
```

Things to look for in the output:

- **Depth counter:** 0 = leaf, higher = intermediates, top = a root in your local store.
- **`subject` and `issuer`** lines.
- **`Server Temp Key`** — the ephemeral DH share for this session (forward secrecy in action).
- **`Cipher: TLS_AES_256_GCM_SHA384`** — AES-GCM bulk encryption with a SHA-384 KDF. The entire L24 toolkit on a single line.

---

## 10. TLS 1.3 — Every Primitive in One Handshake

**TLS 1.3** (RFC 8446, 2018) is where every primitive of the lecture composes into one real protocol.

### 10.1 The handshake

1. **ClientHello.** α sends supported ciphers and an ephemeral DH share `g^a`.
2. **ServerHello.** β picks a cipher and sends:
   - its own ephemeral DH share `g^b`,
   - its **certificate chain**,
   - a **signature** over the handshake transcript using β's long-term private key.
3. **Client verifies.** α verifies β's certificate chain against its root store, then verifies β's transcript signature — confirming β actually holds the private key matching the certificate.
4. **Both derive session keys.** Both compute `g^(ab)`, run it through **HKDF** (a hash-based key-derivation function), and produce the symmetric **AES-GCM** keys for the session.
5. **Application data.** Each record is encrypted under AES-GCM, getting both confidentiality and integrity from the single AEAD primitive.

### 10.2 Mapping the handshake back to the primitives

| Step | Primitive | Covered in |
|---|---|---|
| Ephemeral key share | Diffie–Hellman | §6 |
| Cert chain verification | Signatures + PKI | §8, §9 |
| Handshake authenticity | Signature on transcript | §8 |
| Bulk data encryption | AES-GCM (AEAD) | §3 |
| Bulk data integrity | AES-GCM (AEAD) | §3 |
| Session key derivation | HKDF (hash-based) | §4 |

### 10.3 The division of labor

- **Asymmetric crypto** is used **once**, at the handshake (tens of milliseconds per session): ephemeral DH for key agreement, and RSA/ECDSA for the transcript signature.
- **Symmetric crypto** is used **everywhere else**, at multi-GB/s and effectively free: AES-GCM on every record.

That split is the entire performance story: modern TLS has essentially **no throughput penalty** over plaintext.

### 10.4 Loop-back to Lecture 23: QUIC

Lecture 23 introduced **QUIC** as HTTP/3's transport: UDP-based, with TLS *built into* the transport handshake itself. Concretely:

- **One round-trip** establishes the connection *and* the crypto.
- **0-RTT resumption** sends application data in the very first packet on return visits.
- Streams are independently encrypted, and even packet **headers** are partially encrypted.

This closes the loop the course has been building toward all semester: every layer, encrypted by default, in one round-trip.

---

## 11. Connections to Earlier Lectures

| Lecture concept | How L24 builds on it |
|---|---|
| L1–L9 — bits, framing, link layer | Provides the cleartext substrate that crypto must protect |
| L13–L22 — IP, TCP, UDP | Defines *what* is being encrypted (TCP segments, UDP datagrams) |
| L21 — `tcpdump`, Wireshark | Motivates encryption (anyone on path can read everything) |
| L22 — Scapy, sockets | Where one might *test* TLS handshake behavior programmatically |
| L23 — HTTP, DNS, QUIC | Real-world consumers of TLS; QUIC integrates TLS 1.3 directly |

The lecture frames itself as the "answer key" to a semester's worth of plaintext protocols.

---

## 12. The Course Arc and What Comes Next

Lecture 24 closes the course's content arc in three sentences:

1. **L1–L9.** What bits mean, how they travel, how they survive noise, how a local network works.
2. **L13–L22.** How packets cross the world, how reliability is built on best-effort, and the tools that let you see and touch it.
3. **L23–L24.** What people actually build on top — HTTP, DNS, QUIC, TLS — and the cryptography that makes any of it safe.

**Seeds for further study** (not on the exam, just pointers):

- IPv6 deployment and the long migration.
- BGP and the economics of Internet routing.
- Software-defined networking (SDN, OpenFlow, P4).
- Net neutrality, surveillance, and privacy-enhancing technologies.
- **Post-quantum cryptography** — the next decade of TLS.
- High-throughput systems: DPDK, RDMA, kernel bypass.

The vocabulary built in EC 441 is now sufficient to read into any of these areas.

**Next up.** L25 (Thursday, April 30): **project demo day** — the conclusion of the semester.

---

## 13. Acronym Reference

| Acronym | Expansion |
|---|---|
| ACME | Automatic Certificate Management Environment |
| AES | Advanced Encryption Standard |
| AEAD | Authenticated Encryption with Associated Data |
| CA | Certificate Authority |
| CBC | Cipher Block Chaining |
| DH / ECDHE | Diffie–Hellman / Ephemeral Elliptic-Curve DH |
| ECB | Electronic Codebook |
| ECDSA | Elliptic-Curve Digital Signature Algorithm |
| FIPS | Federal Information Processing Standard |
| GCM | Galois/Counter Mode |
| HKDF | HMAC-based Key Derivation Function |
| HMAC | Hash-based Message Authentication Code |
| MAC | Message Authentication Code (note: ≠ Media Access Control of L7/L8) |
| NIST | National Institute of Standards and Technology |
| PKI | Public Key Infrastructure |
| QUIC | Quick UDP Internet Connections |
| RSA | Rivest–Shamir–Adleman |
| SHA | Secure Hash Algorithm |
| TLS | Transport Layer Security |
