import asyncio
import sys
import serial_asyncio
import binascii
import time
import struct
import random

from hub.frame import APIFrame
from hub.python2to3 import intToByte

packet_index = 0

class Packet(object):
    def __init__(self, client, in_frame):
        global packet_index
        self.client = client    # type: SocketProtocol
        self.in_frame = in_frame
        self.out_frame = None
        self.sent = False
        self.sent_time = 0
        self.recv = False
        self.index = packet_index
        packet_index += 1

serial = None       # type: SerialProtocol
clients = []


class SerialProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        print('SerialProtocol.__init__')
        self._transport = None
        self._escaped = True
        self._frame = None
        self._in_frame = False
        self._packets = []
        self._packet = None

    def connection_made(self, transport):
        global serial
        self._transport = transport
        serial = self

    def connection_lost(self, exc):
        pass

    def data_received(self, data: bytes):
        for b in data:
            self.parse_byte(intToByte(b))
        sys.stdout.flush()

    def parse_byte(self, b):
        global clients
        if b != APIFrame.START_BYTE and not self._in_frame:
            try:
                print(b.decode('utf-8'), end='')
            except UnicodeDecodeError:
                pass

        if not self._in_frame:
            if b == APIFrame.START_BYTE:
                self._frame = APIFrame(escaped=self._escaped)
                self._in_frame = True
                print(binascii.hexlify(b))
                self._frame.fill(b)
        else:
            print(binascii.hexlify(b))
            if self._frame.fill(b):
                try:
                    self._frame.parse()
                    # Ignore empty frames
                    if len(self._frame.data) > 0:
                        handle, = struct.unpack("<H", self._frame.data[0:2])
                        out = self._frame.data[2:]
                        found = False
                        _serial = "UNKNOW"
                        for client in clients:
                            if client.handle == handle:
                                found = True
                                client.send_data(out)
                                _serial = binascii.hexlify(bytes(client.serial))
                                #_time = time.time() - self._packet.sent_time
                                #_index = self._packet.index
                        if not found:
                            print('SerialProtocol.parse_byte: No client available. Invalid handle {} in frame!!!!'.format(handle))

                        print('ToHass-> serial %s len %d data %s' % (_serial,  len(out), binascii.hexlify(out)))
                    self._frame = None
                    self._in_frame = False
                    self._packet = None
                    if len(self._packets) > 0:
                        pkt = self._packets.pop()
                        self._send_packet(pkt)

                except ValueError:
                    # Bad frame, so restart
                    self._frame = None
                    self._in_frame = False

    def send_packet(self, client, buffer):
        # type: (SocketProtocol, bytes) -> None
        buffer = b'\x78' + struct.pack("<H", client.handle) + buffer
        if client.serial:
            if client.serial[0] == 0x00 and client.serial[1] == 0x00 and client.serial[2] == 0x00 and client.serial[3] == 0x00:
                pass
            elif client.serial[0] == 0xFF and client.serial[1] == 0xFF and client.serial[2] == 0xFF and client.serial[3] == 0xFF:
                buffer = b'\x70' + buffer
            else:
                buffer = b'\x72' + bytes(client.serial) + buffer

        frame = APIFrame(buffer, self._escaped)
        pkt = Packet(client, frame)
        self._send_packet(pkt)
        #if not self._packet:
        #    self._send_packet(pkt)
        #else:
        #    self._packets.append(pkt)

    def _send_packet(self, pkt):
        # type: (Packet) -> None
        #if not self._packet:
        self._packet = pkt
        self._packet.sent_time = time.time()
        # print('SerialProtocol.send_packet')
        data = pkt.in_frame.output()
        self._transport.write(data)

        __serial = binascii.hexlify(bytes(pkt.client.serial)) if pkt.client.serial is not None else "direct"
        print('FromHass-> index %d serial %s len %d data %s' % (pkt.index, __serial, len(data), binascii.hexlify(data)))
        # self._transport.loop.call_later(1.25, self._timeout_expired, (pkt, ))
        #else:
        #    print("Serial is busy")

    def _timeout_expired(self, args):
        pkt, = args
        if self._packet is not None and self._packet.index == pkt.index:
            print('_timeout_expired on packet %d after %f s' % (self._packet.index, time.time() - self._packet.sent_time))
            self._packet = None
            if len(self._packets) > 0:
                pkt = self._packets.pop()
                self._send_packet(pkt)


class SocketProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        print('SocketProtocol.__init__')
        self._transport = None
        self._handshake = False
        self._serial = None
        self._port = 0
        self._handle = random.randint(1, 65535)

    @property
    def serial(self):
        return self._serial

    @property
    def handle(self):
        return self._handle

    def connection_made(self, transport):
        global clients
        print('SocketProtocol.connection_made')
        self._transport = transport
        clients.append(self)

    def connection_lost(self, exc):
        global clients
        print('SocketProtocol.connection_lost')
        clients.remove(self)

    def data_received(self, data: bytes):
        global serial, clients
        if self._serial:
            sertext = [chr(x) for x in self._serial]
            print('SocketProtocol.data_received handle={} handshake={} serial={}'.format(self._handle, self._handshake, sertext))
        else:
            print('SocketProtocol.data_received handle={} handshake={} serial=None'.format(self._handle, self._handshake))
        if not self._handshake:
            print(data)
            if len(data) > 4 and data[0:4] == b'INIT':
                fields = data.split(b'|')
                if len(fields) == 3:
                    _nums = fields[1].split(b'.')
                    if len(_nums) == 4:
                        self._serial = [int(i) for i in _nums]
                        self._serial = [self._serial[3], self._serial[2], self._serial[1], self._serial[0]]
                    else:
                        self._serial = None

                    self._port = 0
                    self._handshake = True
                    self._transport.write(b'!!OK!')
                    print('SocketProtocol.data_received handshake completed', self._serial, self._port)
            else:
                print('SocketProtocol.data_received handshake not fullfilled', self._serial, self._port)
                self._transport.close()

        else:
            serial.send_packet(self, data)

    def eof_received(self):
        pass

    def send_data(self, data):
        self._transport.write(data)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    prot = serial_asyncio.create_serial_connection(loop, SerialProtocol, '/dev/ttyUSB0', baudrate=115200)
    coro = loop.create_server(SocketProtocol, host='127.0.0.1', port=6053)
    loop.run_until_complete(coro)
    asyncio.ensure_future(prot)
    loop.call_later(3600, loop.stop)
    loop.run_forever()
