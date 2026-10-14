#!/usr/bin/env python3
import argparse, csv, json, socket, statistics, struct, time
HDR = struct.Struct('!Id')

def run_probes(dst, port, count, interval, timeout, size):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rows = []                                           # (seq, time sent, rtt_ms or None)
    for seq in range(count):
        t_send = time.time()
        sock.sendto(HDR.pack(seq, t_send) + b'x' * max(0, size - HDR.size), (dst, port))
        rtt = None
        while True:                                     # wait for the reply to THIS seq
            left = t_send + timeout - time.time()
            if left <= 0:                               # REQ 3: timeout -> probe is lost
                break
            sock.settimeout(left)
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                break
            if len(data) >= HDR.size:
                r_seq, ts = HDR.unpack(data[:HDR.size])
                if r_seq == seq:                        # REQ 3: match reply to request by seq
                    rtt = (time.time() - ts) * 1000     # REQ 2: RTT in milliseconds
                    break
                # a reply with a different seq is a late/duplicate packet: ignore it
        rows.append((seq, t_send, rtt))
        time.sleep(max(0, interval - (time.time() - t_send)))
    return rows

def summarize(rows):
    rtts = [r for _, _, r in rows if r is not None]
    lost = len(rows) - len(rtts)
    run = longest = 0                                   # REQ 3: longest burst of lost probes
    for _, _, r in rows:
        run = run + 1 if r is None else 0
        longest = max(longest, run)
    out = {'sent': len(rows), 'received': len(rtts), 'lost': lost,
           'loss_pct': round(100 * lost / len(rows), 2), 'max_loss_burst': longest}
    if rtts:                                            # REQ 2: min/avg/max/jitter
        diffs = [abs(a - b) for a, b in zip(rtts[1:], rtts)]
        out.update(rtt_min=round(min(rtts), 2), rtt_avg=round(statistics.mean(rtts), 2),
                   rtt_max=round(max(rtts), 2),
                   jitter=round(statistics.mean(diffs), 2) if diffs else 0.0)
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dst', required=True)
    ap.add_argument('--port', type=int, default=9000)
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--interval', type=float, default=0.1)
    ap.add_argument('--timeout', type=float, default=0.5)
    ap.add_argument('--size', type=int, default=64)
    ap.add_argument('--log', help='write per-probe CSV here')
    a = ap.parse_args()
    rows = run_probes(a.dst, a.port, a.count, a.interval, a.timeout, a.size)
    if a.log:
        with open(a.log, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['seq', 'sent_at', 'rtt_ms'])
            for seq, t, rtt in rows:
                w.writerow([seq, '%.6f' % t, '' if rtt is None else '%.3f' % rtt])
    print(json.dumps(summarize(rows)))
