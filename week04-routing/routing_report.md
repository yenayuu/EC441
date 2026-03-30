# Week 04 — Routing: Link State, Distance Vector, and BGP

**Course:** EC 441 — Introduction to Computer Networking, Boston University, Spring 2026

**Type:** Report

**Sources:** Lecture 15 — Routing: Link State and Dijkstra’s Algorithm; Lecture 16 — Routing: Distance Vector, Bellman-Ford, and BGP (Introduction)

---

## 1. Introduction

Lectures 13–14 established that routers use forwarding tables (destination prefix → output link) populated from CIDR-style prefixes. The remaining control-plane question is **how those tables are built**. **Static routing** has a human configure every entry and does not scale. **Dynamic routing** lets routers compute tables automatically and adapt when the network changes. Two major families are **link-state** (Lecture 15) and **distance-vector** (Lecture 16). A useful duality: link-state **distributes local information globally** (each router shares its own links with everyone); distance-vector **distributes global information locally** (each router shares its distances to all destinations with only its neighbors).

---

## 2. Lecture 15 — Graph Model, Costs, and Shortest Paths

### 2.1 Networks as graphs

A network is modeled as a graph \(G = (V, E)\): **vertices** are routers; **edges** are physical or logical links. **Adjacent** means directly connected; **degree** is the number of links on a router; a **path** is a sequence of hops.

### 2.2 Edge weights

A **weighted graph** assigns a cost per edge; the meaning of the weight defines what “shortest path” means. Examples from the slides: **hop count** (fewer routers) — RIP uses cost 1 per link; **inverse bandwidth** — OSPF default \(10^8/B\) (transmission time in ms of 100 kb, tying cost to transmission delay and summing along a path like summing transmission delays); **propagation delay**; **administrative** (policy). **Undirected** edges are symmetric (typical full-duplex); **directed** edges can differ per direction (e.g., satellite uplink vs. downlink). The course primarily uses undirected graphs.

### 2.3 Paths, trees, and the routing problem

**Path cost** is the sum of edge costs along the path. A **shortest path** minimizes total cost. **Routing** is framed as finding shortest paths from each router to every destination. A **tree** is connected with no cycles. A **spanning tree** includes all vertices with exactly \(|V|-1\) edges. A **shortest-path tree (SPT)** rooted at \(u\) is a spanning tree where the path from \(u\) to every other vertex is a shortest path in the original graph. **Dijkstra’s algorithm computes an SPT**, which is what a router needs to build its forwarding table.

### 2.4 Tools mentioned (L15)

**traceroute** shows each hop as a vertex and each jump as an edge; paths depend on source location. **mtr** (My TraceRoute on Linux) combines traceroute with continuous ping for per-hop loss and latency; on macOS it can be installed via Homebrew and may require `sudo` for raw sockets.

---

## 3. Lecture 15 — Link-State Routing and Dijkstra

### 3.1 Big idea

**Every router gets a complete map** and **each computes shortest paths independently** (analogy: a full road map). The process has three phases: (1) **discover neighbors**, (2) **flood link-state advertisements (LSAs) everywhere**, (3) **run Dijkstra**. After flooding, every router has the same **topology database**. Dijkstra is deterministic, so all routers compute consistent forwarding tables.

### 3.2 Phases 1–2: Discovery and flooding

**Phase 1:** Routers send **hello** packets on all interfaces, discover neighbors and link costs, and record a **link-state advertisement (LSA)** per router. **Phase 2:** Each router **floods** its LSA to all others. **Flooding rules:** each LSA has a **sequence number** (discard duplicates); forward an LSA out all interfaces **except** the ingress; LSAs have **maximum age** and are refreshed (e.g., every 30 minutes in OSPF).

### 3.3 Phase 3: Dijkstra’s algorithm

**Given:** weighted graph \(G=(V,E)\) and source \(s\). **Find:** shortest path from \(s\) to every other node (Edsger Dijkstra, 1956 / published 1959). The algorithm maintains **\(D(v)\)** — current best-known cost from \(s\) to \(v\); **\(p(v)\)** — predecessor on the best-known path; **\(N'\)** — nodes whose shortest path is **finalized**. **Key property:** when a node \(w\) is added to \(N'\), \(D(w)\) is the true shortest-path cost if all edge weights are **non-negative** (other paths through unfinalized nodes cannot be shorter). **Relaxation:** if \(D(u)+c(u,v) < D(v)\), set \(D(v) = D(u)+c(u,v)\). **Complexity:** \(O(|V|^2)\) with an array; \(O((|V|+|E|)\log|V|)\) with a priority queue. **Negative weights** are not supported by Dijkstra; **Bellman–Ford** handles negatives (Lecture 16).

The slides work a full example with source **u** on a six-node graph, showing step-by-step selection, updates, and that **\(u \rightarrow x\)** direct (cost 5) loses to **\(u \rightarrow w \rightarrow z \rightarrow x\)** (cost 4). Final costs from **u**: \(v\): 2; \(w\): 1; \(z\): 3; \(x\): 4; \(y\): 4.

### 3.4 From SPT to forwarding table

The SPT yields **next hop** for each destination: the router only needs the **first hop**, not the full path. In a real router, “destination” is an **IP prefix** and “next hop” is **interface + IP**; the principle matches the abstract table.

### 3.5 Every router runs Dijkstra

With \(N\) routers, each has the **same** topology database; each runs Dijkstra **rooted at itself**, producing a **different** SPT and forwarding table. **Recomputation** occurs when a new LSA arrives (failure, recovery, cost change), an LSA ages out, or a new router joins. In stable networks, Dijkstra runs infrequently. **Convergence** (all routers agreeing after a change) is **fast (seconds)** for link-state because flooding is fast and each router computes from the full topology.

### 3.6 OSPF (Open Shortest Path First)

OSPF is a widely deployed **link-state** protocol implementing the three phases: **Hello** (default every 10s on broadcast links), **LSA flooding** to build the **link-state database (LSDB)**, **SPF** (Dijkstra) → forwarding table. It runs **directly over IP** (**protocol number 89**, not TCP/UDP). **Dead interval:** if no hello for **40s**, neighbor is down → new LSA. References: **RFC 2328** (OSPFv2, IPv4), **RFC 5340** (OSPFv3, IPv6). **IS-IS** is another major link-state protocol (e.g., large ISPs).

**Hello protocol example:** messages exchange identities until **bidirectional** adjacency is confirmed, then LSA exchange begins. Purposes: neighbor discovery, bidirectional verification, failure detection (dead interval).

**OSPF areas:** In large networks, flooding everywhere is costly. **Area 0** is the **backbone**; other areas must connect through it. **ABR (Area Border Router)** connects areas and summarizes routes. Flooding is **contained within an area** (smaller LSDB, faster Dijkstra). The course focuses on **single-area** OSPF for the same algorithmic ideas.

**OSPF packet types (over IP, proto 89):** (1) Hello, (2) DB Description, (3) LS Request, (4) LS Update, (5) LS Acknowledgment. **Router ID** is often the highest IP on the router; **Area ID** e.g. `0.0.0.0` for backbone; **LSA age** counts up, max age **3600s** then flushed; **LS Update** carries link costs for Dijkstra. OSPF packets are **between routers**, not typically seen on a laptop capture; **Wireshark filter `ospf`** applies on router captures or lab tools (e.g., GNS3, Mininet).

### 3.7 Oscillation with load-sensitive costs

If costs follow **current traffic load**, paths shift → costs change → paths shift again → **instability**. **Mitigations:** do **not** use load-sensitive costs (OSPF/IS-IS use **static** bandwidth-based costs — standard practice); dampen with **exponentially weighted moving averages**; **randomize** recomputation times. Modern traffic engineering uses **MPLS** or **segment routing**, not OSPF cost churn.

### 3.8 Python (L15)

**networkx** can build the lecture graph and call `nx.single_source_dijkstra` with `weight="weight"`. A **from-scratch** demo (`dijkstra` with `relax`) matches the pseudocode; materials referenced include exploration notebooks and `demo dijkstra l15.py` / `lecture 15 exploration.py`.

### 3.9 Acronyms (L15)

Including: ABR, BFS, ECMP, IGP, IS-IS, LSA, LSDB, MTR, OSPF, SPF, SPT, TTL.

---

## 4. Lecture 16 — Bellman-Ford, Distance Vector, RIP

### 4.1 Bellman-Ford equation

Let \(d_x(y)\) be the least-cost path from node \(x\) to \(y\). Then:

\[
d_x(y) = \min_{v \in \text{neighbors}(x)} \bigl( c(x,v) + d_v(y) \bigr).
\]

**Optimal substructure:** if the shortest path from \(x\) to \(y\) goes through neighbor \(v\), the subpath from \(v\) to \(y\) must be shortest from \(v\) to \(y\).

### 4.2 Dijkstra vs. Bellman-Ford (slide comparison)

| | Dijkstra (L15) | Bellman-Ford (L16) |
|--|--|--|
| Information | Full graph at one place | Only neighbor info |
| Computation | Centralized | Distributed |
| Communication | Flood topology | Exchange DVs with neighbors |
| Negative weights | Not supported | Supported |
| Deployed as | OSPF, IS-IS | RIP |

**Advantage of Bellman–Ford:** no node needs the full topology—only **direct link costs** \(c(x,v)\) and **neighbors’ distance vectors** \(D_v(y)\) for all \(y\).

### 4.3 Distance-vector algorithm

Each node \(x\) maintains **\(D_x = [D_x(y)\ \text{for all}\ y]\)**. Steps: **Initialize** \(D_x(x)=0\), \(D_x(v)=c(x,v)\) for neighbors, \(\infty\) otherwise; **send** \(D_x\) to all neighbors; **on receiving** \(D_v\) from \(v\), for each \(y\), if \(c(x,v)+D_v(y) < D_x(y)\), update \(D_x(y)\) and set **next hop\((y)=v\)**; **if anything changed**, send updated \(D_x\) to neighbors; **repeat** until convergence. Properties: **iterative**, **asynchronous**, **distributed**, **self-terminating**.

The slides trace convergence on a five-node example through rounds; **node A**’s final forwarding table sends **B, C, D, E** via **B** with costs 1, 3, 4, 4.

### 4.4 Convergence rounds

DV converges in **at most \(|V|-1\)** rounds (longest shortest path has at most \(|V|-1\) edges; each round extends knowledge one hop). The example converges in **2–3 rounds**. **Dijkstra** needs the full graph but runs in one shot (\(O(|V|^2)\) or \(O(|E|\log|V|)\)); **DV** needs multiple rounds but only **local** work per node.

### 4.5 Good news vs. bad news

When a link cost **decreases**, improvements can propagate **quickly** (e.g., one round). **Good news travels fast; bad news travels slow.**

### 4.6 Count-to-infinity

After **B–C** fails, **B** may wrongly use **A**’s stale distance to **C** even though **A**’s route goes through **B**. Costs increment each round—**counting to infinity**. **Root cause:** **B** uses information from **A** that **depends on B**. Packets can **loop** between **A** and **B** during convergence.

### 4.7 Split horizon and poisoned reverse

**Split horizon:** if **A** routes to **C** via **B**, **A** does **not** advertise the route to **C** back to **B**. **Poisoned reverse:** **A** tells **B** \(d_A(C)=\infty\) for that route. These fix **two-node** loops; **three or more** nodes may still need **hold-down timers** and **route poisoning**.

### 4.8 LS vs. DV (convergence summary)

| | Link-State (OSPF) | Distance-Vector (RIP) |
|--|--|--|
| Good news | Fast (one flood + recompute) | Fast (few rounds) |
| Bad news | Fast (same mechanism) | Slow (count-to-infinity) |
| Loop-free? | Yes (full topology) | Not guaranteed during convergence |

**OSPF** has largely **replaced RIP** in production for faster convergence, richer metrics, and no 15-hop limit.

### 4.9 RIP (Routing Information Protocol)

**Metric:** hop count (1 per link). **Max distance:** **15 hops** (**16 = \(\infty\)**). **Updates:** every **30 seconds**, full DV broadcast. **Transport:** **UDP port 520**. **Triggered updates** on route change. **Timeout:** **180 seconds** without update → routes to \(\infty\). Hop count ignores bandwidth/delay/congestion. Max 15 limits count-to-infinity duration (e.g., ≤16 rounds ≈ 8 min at 30s) but **cannot** span networks **>15 hops**. RIP was **dominant in the 1980s–90s**; still used in **small networks** and for **teaching**.

### 4.10 `netstat -rn`

Shows the **routing table** (destination, gateway, flags, interface, **metric**). **RIP** fills **metric** with hop count; **OSPF** with computed link-state costs. Structure is **protocol-independent**. RIP’s place today: largely replaced by OSPF.

### 4.11 Acronyms (L16)

Including: AS, ASN, BGP, DV, EGP, IGP, IS-IS, LS, OSPF, RIP, RPKI, UDP.

---

## 5. Lecture 16 — Why One Algorithm Is Not Enough; AS and BGP

### 5.1 Barriers to running OSPF/RIP globally

The internet has **75,000+** independently administered networks, **hundreds of millions** of IP prefixes, and diverse policies and business relationships. **Barriers:** (1) **Scale** — full topology at every router is unsustainable. (2) **Administrative autonomy** — different policies; no single metric fits all. (3) **Business relationships** — e.g., an ISP may refuse to carry a competitor’s traffic despite a shorter path. **Solution:** **hierarchical routing** — **within** an organization: OSPF or RIP; **between** organizations: **BGP**.

### 5.2 Autonomous systems

An **autonomous system (AS)** is a collection of IP networks and routers under **one** organization with a **common routing policy**. Types (examples): **stub** (single upstream, not transit); **multi-homed** (multiple ISPs, redundancy); **transit** (carries traffic between ASes). Each AS has an **ASN** (originally **16-bit**, now **32-bit**).

| | Intra-AS (IGP) | Inter-AS (BGP) |
|--|--|--|
| Scope | Within one AS | Between ASes |
| Goal | Shortest/cheapest path | Enforce routing **policy** |
| Protocols | OSPF, RIP, IS-IS | BGP |
| Metric | Link cost, hop count | Business relationships |
| Convergence | Seconds | Minutes |

### 5.3 Demo: ASes on a path

**traceroute -a** shows AS numbers per hop; **whois** (e.g., `whois -h whois.radb.net AS15169`) can identify AS names. Traffic crossing from one AS to another is determined by **BGP** per **business agreements**.

### 5.4 BGP (Border Gateway Protocol)

**BGP** is the **inter-AS** routing protocol; every AS connected to the internet runs it. **Three jobs:** (1) **advertise reachability** (“my AS can reach these prefixes”); (2) **propagate paths** (e.g., AS-path \([7922, 3356, 111]\)); (3) **enforce policy** (carry or refuse traffic). Called **“the glue that holds the internet together”** — without BGP, ASes would be isolated.

**Path vector:** BGP is **neither** pure link-state nor distance-vector; it advertises a **complete AS-path**. If a router sees **its own ASN** in the **AS-PATH**, it **rejects** the route — **loop prevention** without count-to-infinity.

| | Distance Vector | Link State | Path Vector (BGP) |
|--|--|--|--|
| Advertises | Distance to dest | Full local link info | Complete AS-path |
| Loop prevention | Split horizon | Full topology | Reject own ASN |
| Metric | Numeric cost | Numeric cost | **Policy-based** |

### 5.5 BGP and business relationships

**Customer–provider:** customer pays; provider advertises customer routes globally. **Peer–peer:** two ASes exchange traffic for free, **only for their own customers**, not as general transit. **Valley-free rule:** traffic flows **up** (customer→provider), **across** a peering link **at most once**, then **down** (provider→customer). A well-configured system avoids **customer→provider→peer→provider→customer**.

### 5.6 Why BGP is hard

**Policy over optimality** — “best” route satisfies contracts, not necessarily shortest path. **No global view** of all policies. **Slow convergence** — minutes vs. seconds for OSPF. **Scale** — global table **over 1 million prefixes**. **Trust-based** announcements — **limited verification** infrastructure. **Incidents cited:** Pakistan/YouTube **2008** (more-specific prefix announcement, ~2 hours); Facebook **2021** (BGP withdrawal, ~6 hours).

### 5.7 Routing landscape (L16 summary)

| Lecture | Algorithm | Type | Scope | Deployed as |
|--|--|--|--|--|
| L15 | Dijkstra | Link-state | Intra-AS | OSPF, IS-IS |
| L16 | Bellman-Ford | Distance-vector | Intra-AS | RIP |
| L16 | Path vector | Policy-based | Inter-AS | BGP |

**Intra-AS:** OSPF or RIP (shortest path). **Inter-AS:** BGP (policy).

### 5.8 LS vs. DV — when to use (intra-AS)

| Consider… | Link-State (OSPF) | Distance-Vector (RIP) |
|--|--|--|
| Network size | Large (100s of routers) | Small (<15 hops) |
| Convergence | Fast | Slow (count-to-infinity) |
| Memory/CPU | Higher (full topology) | Lower (DV only) |
| Complexity | More complex | Simpler |
| Metric | Rich (bandwidth, delay) | Typically hop count |

**Optional further reading** listed on the slides: BGP mechanics (eBGP vs. iBGP, LOCAL PREF, MED, AS-PATH length), hot potato routing, traffic engineering, RPKI/BGPsec; tools such as BGP looking glasses (e.g., BGP.he.net), RIPE Stat, RouteViews.

---

## 6. What’s Next (from the slides)

**Lecture 15 “What’s Next”** listed: L16 distance-vector (Bellman-Ford, count-to-infinity, RIP); L17 autonomous systems and BGP; L18 IPv4 datagram, NAT, IPv6, DHCP.

**Lecture 16 “What’s Next”** listed: L17 IPv4 datagram format, ICMP, NAT, IPv6, DHCP; L18 Wireshark lab (L13–L17).

*(Note: L16’s closing slide revises the numbering vs. L15’s preview for topics after L16.)*
