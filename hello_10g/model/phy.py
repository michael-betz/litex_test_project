'''
Model of a network PHY
writes a packet dump to stderr. To Show in wireshark:

  python udp_sender.py sim 2> phydump.hex
  text2pcap -D -l 274 phydump.hex phydump.pcap
  wireshark phydump.pcap
'''
#
# This file is part of LiteEth.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from sys import stderr
from litex.soc.interconnect.stream_sim import *

from liteeth.common import *

# Helpers ------------------------------------------------------------------------------------------

def print_phy(s):
    print_with_prefix(s, "[PHY]")


def bytes_to_words(bs, width):
    ws = []
    n_words = len(bs) // width
    for i in range(n_words):
        tmp = bs[i * width: (i + 1) * width]
        ws.append(merge_bytes(tmp[::-1]))
    return ws


# PHY Source ---------------------------------------------------------------------------------------

class PHYSource(PacketStreamer):
    def __init__(self, dw):
        PacketStreamer.__init__(self, eth_phy_description(dw))

# PHY Sink -----------------------------------------------------------------------------------------

class PHYSink(PacketLogger):
    def __init__(self, dw):
        PacketLogger.__init__(self, eth_phy_description(dw))

# PHY ----------------------------------------------------------------------------------------------

class PHY(Module):
    def __init__(self, dw, debug=False):
        self.dw    = dw
        self.debug = debug

        self.submodules.phy_source = PHYSource(dw)
        self.submodules.phy_sink   = PHYSink(dw)

        self.source = self.phy_source.source
        self.sink   = self.phy_sink.sink

        self.mac_callback = None

    def set_mac_callback(self, callback):
        self.mac_callback = callback

    def send(self, datas):
        datas_w = bytes_to_words(datas, self.dw // 8)
        packet = Packet(datas_w)
        print("O 0000 ", file=stderr, end='')
        for d in datas:
            print(f"{d:02x} ", file=stderr, end='')
        print(file=stderr)
        if self.debug:
            r = ">>>>>>>>\n"
            r += "length " + str(len(packet)) + "\n"
            for d in packet:
                r += f'{d:0{self.dw // 4}x} '
            print_phy(r)
        self.phy_source.send(packet)

    def receive(self):
        yield from self.phy_sink.receive()
        p = self.phy_sink.packet
        if self.debug:
            r = "<<<<<<<<\n"
            r += "length " + str(len(p)) + "\n"
            for d in p:
                r += f'{d:0{self.dw // 4}x} '
            print_phy(r)
        self.packet = [b for p in p for b in split_bytes(p, 8, "little")]
        print("I 0000 ", file=stderr, end='')
        for d in self.packet:
            print(f"{d:02x} ", file=stderr, end='')
        print(file=stderr)

    @passive
    def generator(self):
        while True:
            yield from self.receive()
            if self.mac_callback is not None:
                self.mac_callback(self.packet)
