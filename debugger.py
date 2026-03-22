"""
F1 25 UDP Packet Debugger v2
-----------------------------
Receives ANY packet and dumps the first 30 bytes as hex + decimal
so we can find exactly where packetId lives and what packet IDs exist.

Run this, drive around, paste output back.
"""

import socket
import struct
from collections import defaultdict

UDP_PORT = 20725


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", UDP_PORT))
    sock.settimeout(10.0)

    print(f"Listening on UDP port {UDP_PORT} ...")
    print("Drive around and press throttle/brake.")
    print("Press Ctrl+C to stop.\n")

    count = 0
    seen_sizes = {}
    byte_values = defaultdict(set)

    try:
        while True:
            try:
                data, addr = sock.recvfrom(8192)
            except socket.timeout:
                print("No data received in 10 seconds.")
                print("Check: Settings > Telemetry > UDP Telemetry = On, Port = 20725")
                continue

            count += 1
            pkt_len = len(data)
            seen_sizes[pkt_len] = seen_sizes.get(pkt_len, 0) + 1

            for i in range(min(30, pkt_len)):
                byte_values[i].add(data[i])

            # Print first packet of each unique size in full detail
            if seen_sizes[pkt_len] == 1:
                print(f"\n{'='*65}")
                print(f"NEW PACKET SIZE: {pkt_len} bytes  (packet #{count})")
                print(f"  hex: {data[:30].hex(' ')}")
                print(f"  dec: {list(data[:30])}")

                if pkt_len >= 24:
                    # Try standard F1 header layout
                    try:
                        pkt_fmt, yr, mj, mn, pv, pid, uid, st, fi = struct.unpack_from("<HBBBBBQfI", data, 0)
                        print(f"  >> packetFormat={pkt_fmt} gameYear={yr} v={mj}.{mn} "
                              f"packetVersion={pv} packetId(byte6)={pid} frameId={fi}")
                        print(f"  >> byte[22]={data[22]}  byte[23]={data[23]}")
                    except Exception as e:
                        print(f"  header parse error: {e}")

                    print(f"  Individual bytes [0-9]: {[data[i] for i in range(min(10,pkt_len))]}")

            # Every 300 packets print summary
            if count % 300 == 0:
                print(f"\n--- {count} packets received ---")
                print(f"Sizes: {dict(sorted(seen_sizes.items()))}")
                print("Unique values per byte [0-11]:")
                for off in range(12):
                    print(f"  [{off:2d}]: {sorted(byte_values[off])}")

    except KeyboardInterrupt:
        print(f"\n\nTotal packets: {count}")
        print(f"Packet sizes seen: {dict(sorted(seen_sizes.items()))}")
        print("\nUnique values per byte position [0-11]:")
        for off in range(12):
            print(f"  [{off:2d}]: {sorted(byte_values[off])}")
        print("\nPaste ALL of this output and share it!")


if __name__ == "__main__":
    main()
