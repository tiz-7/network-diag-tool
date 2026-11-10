# Network Diagnostic and Path Analysis Tool

SDN + socket programming mini project (UE25CS243A, Computer Networks).

A socket-based network diagnostic application that measures delay, packet loss and
path characteristics with UDP probes, discovers the SDN topology, correlates every
measurement with the network path it used, detects failed paths and compares
alternative paths. It runs in Mininet with a Ryu OpenFlow controller.

## 1. Problem statement

Develop a socket-based network diagnostic application that measures delay, packet loss
and path characteristics, and correlates the results with the SDN network topology.

| Requirement | Done |
|---|---|
| Implement UDP diagnostic probes | Yes |
| Measure round-trip time | Yes |
| Detect packet loss | Yes |
| Implement path analysis | Yes |
| Discover SDN topology | Yes |
| Correlate application measurements with network paths | Yes |
| Identify failed paths | Yes |
| Compare alternative paths | Yes |

## 2. Architecture

```
                 +--------------------------------------+
                 |  Ryu SDN controller                  |
                 |  topology discovery (LLDP)           |
                 |  path computation and flow rules     |
                 |  failure handling, port monitoring   |
                 |  REST API (port 8080)                |
                 +----------+---------------^-----------+
                  OpenFlow 1.3|             | REST (HTTP/JSON)
                              |             |
   +--------------------------v-----+       |      analyzer.py
   |  Mininet                       |       +----- (runs experiments,
   |                                |              tags probe results
   |            +-- s2 --+          |              with the active path)
   |  h1,h3 -- s1         s4 -- h2,h4|
   |            +-- s3 --+          |
   +--------------------------------+
   Path A: s1-s2-s4   2 x 5 ms links, no loss
   Path B: s1-s3-s4   2 x 20 ms links, 2% loss on s1-s3
   h1 = probe client, h2 = probe server, h3 / h4 = background traffic (iperf)
```

| Component | File | Role |
|---|---|---|
| Probe server | `diag/probe_server.py` | UDP echo server on h2 |
| Probe client | `diag/probe_client.py` | Sends numbered, timestamped UDP probes; computes RTT, jitter and loss |
| SDN controller | `controller/diag_controller.py` | Topology discovery, path computation, flow rules, failure handling, REST API |
| Orchestrator | `diag/analyzer.py` | Runs the experiments, tags probe results with the active path, reports to the controller, draws graphs |
| Topology | `topology/diamond_topo.py` | 4 switches with two alternative paths between h1 and h2 |
| Repeat runner | `run_repeats.sh`, `diag/summarize.py` | Repeats each experiment and averages the results |

**Message flow**

1. The probe client on h1 sends UDP probes `[seq | timestamp | padding]` to the server on h2, which echoes them back.
2. For every probe window the analyzer asks the controller which path is active (`GET /path`).
3. It tags the window's RTT, jitter and loss with that path and sends them back (`POST /report`).
4. If a path's loss exceeds 20% or RTT exceeds 120 ms, the controller marks it DEGRADED and moves the flow to a healthy path. If a link goes down, it marks the path FAILED and reroutes.

## 3. Requirements and where they are implemented

| Requirement | Implementation |
|---|---|
| UDP diagnostic probes | `probe_client.py` and `probe_server.py` (low-level UDP sockets) |
| Measure round-trip time | Timestamp inside each probe; min, avg, max and jitter per window |
| Detect packet loss | Sequence numbers and a 0.5 s timeout; loss % and longest loss burst |
| Discover SDN topology | LLDP via Ryu (`--observe-links`); host locations learned from ARP; `GET /topology` |
| Implement path analysis | All simple paths between the hosts' switches; `GET /path`; verified against OpenFlow flow tables and counters |
| Correlate with network paths | Each probe window is tagged with the active path and posted to the controller (`POST /report`) |
| Identify failed paths | Control plane: link-down event removes the edge and the path is marked FAILED. Data plane: probe loss burst |
| Compare alternative paths | `POST /reroute` pins a path; the `compare` experiment measures each path idle and under load |

### SDN behaviour (dynamic functionality)

| Trigger | Controller action |
|---|---|
| Link goes down | Path marked FAILED, old flows deleted, new path installed in both directions (reason `LINK_FAILURE`) |
| Application report with loss above 20% or RTT above 120 ms | Path marked DEGRADED for 30 s, flow moved to a healthy path (reason `REPORT`) |
| Port utilisation above 80% (port statistics every 2 s) | Path state shown as CONGESTED and avoided |
| `POST /reroute` | Flow pinned to a chosen path (used for the path comparison) |
| `POST /mode {"dynamic": false}` | Automatic rerouting off: this is the static baseline |

REST API: `GET /topology`, `GET /path?src=&dst=`, `POST /report`, `GET /events`, `GET /stats`, `POST /reroute`, `POST /mode`.

## 4. Repository structure

```
controller/diag_controller.py   Ryu SDN controller + REST API
diag/probe_server.py            UDP echo server
diag/probe_client.py            UDP probe client (RTT, jitter, loss)
diag/analyzer.py                experiments (correlate, failure, compare, congestion)
diag/summarize.py               averages repeated runs into a table
topology/diamond_topo.py        Mininet topology with two alternative paths
run_repeats.sh                  runs every experiment several times
results/                        graphs, CSV files, summary.md, repeats.log
docs/RESULT.pdf                 terminal screenshots of every test case
```

## 5. Setup

Tested on Ubuntu 22.04 in VirtualBox. Ryu needs Python 3.9.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install mininet openvswitch-switch python3-pip git curl iperf3 -y
sudo mn --test pingall                 # check that Mininet works

# Python 3.9 for Ryu (Ubuntu 22.04)
sudo add-apt-repository ppa:deadsnakes/ppa -y && sudo apt update
sudo apt install python3.9 python3.9-venv -y

python3.9 -m venv ~/ryuenv && source ~/ryuenv/bin/activate
pip install setuptools==67.6.1 wheel
pip install eventlet==0.30.2 ryu networkx
python3 -c "import ryu, networkx; print('ryu ok')"
```

Matplotlib for the graphs: `sudo apt install python3-matplotlib -y`.

## 6. How to run

Before every experiment, reset with `sudo mn -c` and restart the controller.

**Terminal 1: controller**
```bash
cd ~/netdiag && source ~/ryuenv/bin/activate
ryu-manager --observe-links controller/diag_controller.py
```

**Terminal 2: manual network (optional)**
```bash
sudo python3 topology/diamond_topo.py
mininet> pingall
mininet> link s1 s2 down        # break the fast path
mininet> link s1 s2 up
```

**Terminal 3: inspect the controller**
```bash
curl -s localhost:8080/topology | python3 -m json.tool
curl -s "localhost:8080/path?src=10.0.0.1&dst=10.0.0.2" | python3 -m json.tool
curl -s localhost:8080/events | python3 -m json.tool
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

**Experiments (each starts its own Mininet)**
```bash
sudo python3 diag/analyzer.py correlate
sudo python3 diag/analyzer.py failure            # dynamic controller
sudo python3 diag/analyzer.py failure --static   # baseline, no rerouting
sudo python3 diag/analyzer.py compare
sudo python3 diag/analyzer.py congestion
sudo python3 diag/analyzer.py congestion --static
```

**All repeats and the averaged table**
```bash
sudo ./run_repeats.sh 3        # writes results/summary.md
```

Graphs and CSV files are written to `results/`. Run `sudo chown -R $USER results/` to open them.

## 7. Test cases

Raw terminal screenshots for every test are in [`docs/RESULT.pdf`](docs/RESULT.pdf).

| # | Test | Expected | Result |
|---|---|---|---|
| 1 | UDP echo, 20 probes (plain Mininet) | 0 lost | 20 sent, 20 received, 0% loss, avg RTT 0.73 ms |
| 2 | RTT with 10 ms per link | about 40 ms (4 link crossings) | min 41.9 ms, avg 46.12 ms |
| 3 | 10% loss per link | about 34% (1 - 0.9^4) | 36.0% (72 of 200 lost), longest burst 4 |
| 4 | Topology discovery | 4 switches, 4 links, hosts learned | 4 switches, 4 links (s1-s2, s1-s3, s2-s4, s3-s4), 4 hosts |
| 5 | Path analysis h1 to h2 | 2 paths, active s1-s2-s4 | 2 paths both UP, active s1-s2-s4 |
| 6 | Flow tables | rules on s1 and s2, none for the pair on s3 | s1 and s2 have rules (h1 to h2 out of the s2 port); s3 only default rules |
| 7 | Correlation | counters only on s1, s2, s4 | 27 / 27 / 0 / 28; RTT 23.8 to 27.0 ms on s1-s2-s4, 0% loss |
| 8 | Link failure, dynamic | fast reroute | 0.5 s outage, 3 probes lost, detect 20 ms, reroute 21 ms |
| 9 | Link failure, static | no reroute until link returns | 14.11 s outage, 28 probes lost, reroute None |
| 10 | Path comparison, idle and loaded | A faster idle, B steadier loaded | see section 8.3 |
| 11 | Congestion, dynamic | reroute away from the flooded path | 2 path changes per run, loss 6.4 to 11.2% (section 8.4) |
| 12 | Congestion, static | stays on path A | 0 path changes, loss 10.2 to 10.6% |

### What each test shows

- **1 to 3** validate the probe client without any SDN: measured delay and loss match what was configured on the links.
- **4 to 6** validate the SDN side: the controller's graph, its chosen path, and the real flow tables agree.
- **7** ties probe measurements to a path and proves it on the data plane: only the switches on the reported path counted packets.
- **8 and 9** are the same link failure with and without the controller reacting.
- **10** shows that no path is best under all conditions.
- **11 and 12** repeat that idea with congestion instead of a failure.

## 8. Results

### 8.1 Link failure: dynamic vs static (link s1-s2 down at 8 s, up at 22 s)

| Metric | Static baseline | Dynamic controller |
|---|---|---|
| Outage, single run (test 8/9) | 14.11 s | 0.50 s |
| **Outage, average of 3 runs** | **13.84 s** (13.65 to 14.17) | **0.51 s** (0.50 to 0.51) |
| Probes lost, average of 3 runs | 27.3 | 4.0 |
| Failure detected | about 10 to 20 ms | about 10 to 20 ms |
| Reroute installed | never | about 10 to 21 ms |

Dynamic rerouting reduced the application-visible outage by about 96%. Detection takes the same time in both modes because the controller sees the link event either way. The difference is that only the dynamic controller then moves the flow. The remaining 0.5 s outage is the probe timeout: probes already in flight when the link died are lost, and the next ones take path B.

![Failure, dynamic](results/failure_dynamic.png)
![Failure, static](results/failure_static.png)

### 8.2 Correlation of measurements with the path

| Window | Path | Avg RTT (ms) | Expected (ms) | Loss |
|---|---|---|---|---|
| 1 | s1-s2-s4 | 27.01 | 20 | 0.0% |
| 2 | s1-s2-s4 | 26.72 | 20 | 0.0% |
| 3 | s1-s2-s4 | 23.80 | 20 | 0.0% |
| 4 | s1-s2-s4 | 25.21 | 20 | 0.0% |
| 5 | s1-s2-s4 | 24.87 | 20 | 0.0% |

Flow-table packet counters moved during the probes: s1 = 27, s2 = 27, s3 = 0, s4 = 28. Only the switches on the controller's active path carried the traffic. Measured RTT is a constant 4 to 7 ms above the configured link delays, which is software-switch and VM overhead.

### 8.3 Comparison of alternative paths (single run, 8 windows per path)

| Condition | Path | Avg RTT (ms) | Max RTT (ms) | Jitter (ms) | Loss % |
|---|---|---|---|---|---|
| idle | s1-s2-s4 (A) | 24.14 | 32.87 | 2.27 | 0.0 |
| idle | s1-s3-s4 (B) | 84.74 | 93.10 | 2.75 | 5.42 |
| loaded | s1-s2-s4 (A) | 27.29 | 219.01 | 5.33 | 30.83 |
| loaded | s1-s3-s4 (B) | 86.38 | 108.44 | 4.29 | 2.50 |

"Loaded" means a 20 Mbit/s UDP iperf flow over path A (10 Mbit/s links). When idle, A is about 3.5 times faster and lossless, while B loses about 5% because of the 2% link loss. Under load, A drops 30% of probes and its worst-case RTT rises from 33 ms to 219 ms, while B is unaffected. The average RTT of A under load looks fine only because it counts replied probes; use the loss column for that case.

### 8.4 Congestion: dynamic vs static

Four runs of each mode (three from `run_repeats.sh` plus the run in `docs/RESULT.pdf`):

| Run | Dynamic loss % | Dynamic avg RTT (ms) | Static loss % | Static avg RTT (ms) |
|---|---|---|---|---|
| 1 | 7.8 | 59.41 | 10.4 | 28.06 |
| 2 | 6.8 | 62.86 | 10.6 | 29.32 |
| 3 | 6.4 | 57.85 | 10.2 | 26.96 |
| 4 (docs/RESULT.pdf) | 11.2 | 48.35 | 10.2 | 25.59 |
| **Mean** | **8.05** | **57.12** | **10.35** | **27.48** |

Path changes: 2 in every dynamic run, 0 in every static run.

In three of four runs the controller reduced loss by about a third (10.4% down to 6.4 to 7.8%), because probe reports marked the flooded path DEGRADED and the flow moved to path B. In run 4 the loss was 11.2%, slightly worse than static. The cause is path oscillation: the controller moves from A to B and then back toward A, so how much time is spent on the flooded path depends on timing. The benefit under congestion is therefore real but modest and variable. Average RTT is higher with the controller because part of each run uses the slower path B, so the controller trades latency for reliability.

![Congestion, dynamic](results/congestion_dynamic.png)
![Congestion, static](results/congestion_static.png)

The summary table of all repeated runs is in [`results/summary.md`](results/summary.md).

**Evidence that the application drives the SDN.** After a congestion run, `GET /events` contains `PATH_DEGRADED s1-s2-s4` followed by `PATH_INSTALLED s1-s3-s4` with reason `REPORT` and old path `s1-s2-s4`. That reroute was caused by a probe report posted by the socket application, not by a link event.

## 9. Discussion

- Dynamic rerouting cut the link-failure outage from 13.84 s to 0.51 s on average (about 96%). The controller detects and reroutes in tens of milliseconds; the 0.5 s that remains is the probe timeout.
- No path is best in all conditions: A is faster when idle (24 ms against 85 ms) but loses 30% under load, while B is slower but steadier. A fixed shortest-path choice is wrong under load, which is the argument for measuring and rerouting.
- Failures are detected two independent ways: the controller's link event (control plane) and a burst of consecutive lost probes (data plane).
- Path analysis cannot use `traceroute`, because the switches are Layer 2. The controller's graph is the source of truth, and it is verified against OpenFlow flow tables and per-switch packet counters.

## 10. Limitations

- Under sustained congestion the controller can oscillate between the two paths (2 path changes per run). Adding hysteresis, so it waits for a clear improvement before switching back, would stabilise it and make the congestion benefit more consistent.
- Only one host pair (h1 to h2) is probed; flows are routed per host pair.
- The path-comparison table is a single run; failure and congestion results are averages of 3 runs (congestion also includes a fourth run).
- Measured RTT is 4 to 7 ms above the configured link delay because of software switches and VM scheduling.
- One congestion run recorded a maximum RTT of 7139 ms, far above the 500 ms probe timeout. This is attributed to a VM clock adjustment, so jitter and maximum RTT are not used as headline congestion metrics.
- Rerouting decisions from application reports are made per probe window (about 1 s granularity).
