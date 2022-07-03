import asyncio
import sys
import binascii
import time
import struct

from .python2to3 import intToByte
from .frame import APIFrame


class StreamClient(object):
    def __init__(self):
        self._handle = None

    @property
    def handle(self):
        return self._handle

    def recv_from_uart(self, data):
        pass

    def disconnect_from(self):
        pass

class Packet(object):
    def __init__(self, frame):
        # type: (APIFrame) -> None
        self._frame = frame # type: APIFrame

    @property
    def frame(self):
        return self._frame


class SerialProtocol(asyncio.Protocol):
    STREAM_PROTOCOL_FRAME = 0x7A
    STREAM_PROTOCOL_FRAME_REPLY = 0x7B

    STREAM_UART_CONNECT_TO = 0x02
    STREAM_UART_CONNECT_OK = 0x03
    STREAM_UART_SEND_DATA = 0x05
    STREAM_UART_DISCONECT_FROM = 0x6

    STREAM_UART_SEND_DATA_NACK = 0x25

    serial = None

    def __init__(self):
        super().__init__()
        print('SerialProtocol.__init__')
        self._transport = None
        self._escaped = True
        self._frame = None
        self._in_frame = False
        self._packets = []
        self._packet = None

        self._clients = [] # type: list[StreamClient]
        self._recv_handle_callback = None # type: callable

    def register_client(self, client):
        # type: (StreamClient) -> None
        print('SerialProtocol.register_client', client.handle)
        self._clients.append(client)

    def unregister_client(self, client):
        print('SerialProtocol.unregister_client', client.handle)
        try:
            self._clients.remove(client)
        except ValueError:
            pass


    def find_client(self, handle):
        # type: (int) -> StreamClient
        found = None
        for c in self._clients:
            if c.handle == handle:
                found = c
                break
        return found

    def connection_made(self, transport):
        print('SerialProtocol.connection_made')
        self._transport = transport
        SerialProtocol.serial = self

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
                self._frame.fill(b)
        else:
            # print(binascii.hexlify(b))
            if self._frame.fill(b):
                try:
                    self._frame.parse()
                    # Ignore empty frames
                    if len(self._frame.data) > 0:
                        print("From UART", binascii.hexlify(self._frame.data))
                        if self._frame.data[0] == SerialProtocol.STREAM_PROTOCOL_FRAME_REPLY:
                            if self._frame.data[1] == SerialProtocol.STREAM_UART_CONNECT_OK:
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                if self._recv_handle_callback is not None:
                                    self._recv_handle_callback(handle, True)
                            elif self._frame.data[1] == SerialProtocol.STREAM_UART_SEND_DATA:
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                print("SerialProtocol.parse_byte send_data handle %d size %d"% (handle, len(self._frame.data[4:])))
                                client = self.find_client(handle)
                                if client:
                                    client.recv_from_uart(self._frame.data[4:])
                                else:
                                    print('Client not found!!!!')
                            elif self._frame.data[1] == SerialProtocol.STREAM_UART_SEND_DATA_NACK:  # STREAM_UART_SEND_DATA_NACK
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                print("SerialProtocol.parse_byte send_data_nack handle %d" % handle)
                                client = self.find_client(handle)
                                # FIXME
                            elif self._frame.data[1] == SerialProtocol.STREAM_UART_DISCONECT_FROM:
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                print("SerialProtocol.parse_byte STREAM_UART_DISCONECT_FROM handle %d" % handle)
                                client = self.find_client(handle)
                                if client:
                                    client.disconnect_from()
                                else:
                                    print("SerialProtocol.parse_byte STREAM_UART_DISCONECT_FROM handle not found %d" % handle)

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

    def _send_packet(self, pkt):
        # type: (Packet) -> None
        self._packet = pkt
        self._packet.sent_time = time.time()
        data = pkt.frame.output()
        print("_send_packet", binascii.hexlify(data))
        self._transport.write(data)

    def _timeout_expired(self, args):
        pkt, = args
        if self._packet is not None and self._packet.index == pkt.index:
            print('_timeout_expired on packet %d after %f s' % (self._packet.index, time.time() - self._packet.sent_time))
            self._packet = None
            if len(self._packets) > 0:
                pkt = self._packets.pop()
                self._send_packet(pkt)

    def request_handle(self, serial, callback):
        # type: (int, callable) -> None
        self._recv_handle_callback = callback
        buffer = struct.pack("<BB", SerialProtocol.STREAM_PROTOCOL_FRAME, SerialProtocol.STREAM_UART_CONNECT_TO) + \
            serial.to_bytes(4, byteorder='little')
        frame = APIFrame(buffer, self._escaped)
        pkt = Packet(frame)
        self._send_packet(pkt)

    def disconnect_from(self, handle):
        # type: (int) -> None
        print("SerialProtocol.disconnect_from handle %d" % handle)
        buffer = struct.pack("<BBH", SerialProtocol.STREAM_PROTOCOL_FRAME, SerialProtocol.STREAM_UART_DISCONECT_FROM, handle)
        frame = APIFrame(buffer, self._escaped)
        pkt = Packet(frame)
        self._send_packet(pkt)

    def send_data(self, handle, data):
        # type: (int, bytes) -> None
        print("SerialProtocol.send_data handle %d size %d" % (handle, len(data)))
        buffer = struct.pack("<BBH", SerialProtocol.STREAM_PROTOCOL_FRAME, SerialProtocol.STREAM_UART_SEND_DATA, handle) + data
        frame = APIFrame(buffer, self._escaped)
        pkt = Packet(frame)
        self._send_packet(pkt)
