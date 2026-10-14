#!/usr/bin/env python3
import argparse, socket, struct, threading, time
HDR = struct.Struct('!Id')            # seq (uint32) + timestamp (float64) = 12 bytes

ap = argparse.ArgumentParser()
ap.add_argument('port', type=int, nargs='?', default=9000)
args = ap.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', args.port))

clients, lock = {}, threading.Lock()      # packets echoed per client IP

def reporter():                           # background thread: print stats every 5 s
    while True:
        time.sleep(5)
        with lock:
            print('echoed per client:', dict(clients), flush=True)
threading.Thread(target=reporter, daemon=True).start()

print('UDP echo server listening on port', args.port, flush=True)
while True:
    data, addr = sock.recvfrom(4096)
    if len(data) < HDR.size:              # malformed packet: ignore it
        continue
    sock.sendto(data, addr)               # echo the packet back unchanged
    with lock:
        clients[addr[0]] = clients.get(addr[0], 0) +1
