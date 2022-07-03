import asyncio
import sys
import serial_asyncio
import binascii
import time
import struct
import random

from meshmesh.hub import frame
from meshmesh.hub.frame import APIFrame
from meshmesh.hub.python2to3 import intToByte, byteToInt

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


def find_client(handle):
    found = None
    _serial = "UNKNOW"
    for client in clients:
        if client.handle == handle:
            found = client
            break
    if not found:
        print('ERROR: No client available. Invalid handle %d!!!!' % handle)
    return found



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
                self._frame.fill(b)
        else:
            # print(binascii.hexlify(b))
            if self._frame.fill(b):
                try:
                    self._frame.parse()
                    # Ignore empty frames
                    if len(self._frame.data) > 0:
                        print("FromUART<-", binascii.hexlify(self._frame.data))
                        if self._frame.data[0] == byteToInt(frame.CMD_SOCKET_REPLY):
                            if self._frame.data[1] == byteToInt(frame.TOUART_CONNECT_ACCEPTED):
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                time.sleep(0.5)
                                print("SerialProtocol.parse_byte TOUART_CONNECT_ACCEPTED handle %d" % handle)
                                client = find_client(0xFFFF)
                                if client:
                                    client.end_handshake(handle)
                            elif self._frame.data[1] == byteToInt(frame.TOUART_CONNECT_ACK):
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                print("SerialProtocol.parse_byte TOUART_CONNECT_ACK handle %d" % handle)
                            elif self._frame.data[1] == byteToInt(frame.TOUART_SEND_DATA):  # STREAM_UART_SEND_DATA
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                print("SerialProtocol.parse_byte send_data handle %d size %d" % (handle, len(self._frame.data[4:])))
                                client = find_client(handle)
                                if client:
                                    client.send_data(self._frame.data[4:])
                            elif self._frame.data[1] == 0x25:  # STREAM_UART_SEND_DATA_NACK
                                handle, = struct.unpack("<H", self._frame.data[2:4])
                                # print("SerialProtocol.parse_byte send_data_nack handle %d" % handle)
                                client = find_client(handle)
                                if client:
                                    client.recv_data_nack()
                            elif self._frame.data[1] == byteToInt(frame.TOUART_DISCONNECT):
                                pass

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
        # if not self._packet:
        self._packet = pkt
        self._packet.sent_time = time.time()
        # print('SerialProtocol.send_packet')
        data = pkt.in_frame.output()
        print('FromHass-> index %d serial %s len %d data %s' % (pkt.index, pkt.client.serial, len(data), binascii.hexlify(data)))
        self._transport.write(data)

    def _timeout_expired(self, args):
        pkt, = args
        if self._packet is not None and self._packet.index == pkt.index:
            print('_timeout_expired on packet %d after %f s' % (self._packet.index, time.time() - self._packet.sent_time))
            self._packet = None
            if len(self._packets) > 0:
                pkt = self._packets.pop()
                self._send_packet(pkt)

    def request_handle(self, client, serial):
        frame_ = frame.APIFrameSocket.make_uart_connect_to(target=serial, port=6053)
        pkt = Packet(client, frame_)
        self._send_packet(pkt)

    def disconnect_from(self, client, handle):
        frame_ = frame.APIFrameSocket.make_uart_disconnect_from(handle)
        pkt = Packet(client, frame_)
        self._send_packet(pkt)

    def send_data(self, client, handle, data):
        frame_ = frame.APIFrameSocket.make_uart_send_data(handle, data)
        pkt = Packet(client, frame_)
        print("SerialProtocol.send_data handle %d size %d" % (handle, len(data)))
        self._send_packet(pkt)


class SocketProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        print('SocketProtocol.__init__')
        self._transport = None
        self._handshake_started = False
        self._handshake = False
        self._serial = None
        self._port = 0
        self._handle = 0xFFFF

    @property
    def serial(self):
        return self._serial

    @property
    def handle(self):
        return self._handle

    def close_transport(self):
        print("SocketProtocol.close_transport for handle %d" % self._handle)
        if self._transport:
            print("SocketProtocol.close_transport", self._transport.is_closing())
            self._transport.abort()

    def end_handshake(self, handle):
        self._handle = handle
        self._handshake = True
        self._transport.write(b'!!OK!')

        print('SocketProtocol.data_received handshake completed from serial {} with handle {}'.format(self._serial, self._handle))

    def connection_made(self, transport):
        global clients
        print('SocketProtocol.connection_made')
        self._transport = transport
        clients.append(self)

    def connection_lost(self, exc):
        global clients
        print('SocketProtocol.connection_lost', exc)
        serial.disconnect_from(self, self.handle)
        clients.remove(self)

    def data_received(self, data: bytes):
        global serial, clients
        # print('SocketProtocol.data_received', self._handshake, self._serial, len(clients))
        if not self._handshake_started:
            self._handshake_started = True
            if len(data) > 4 and data[0:4] == b'INIT':
                fields = data.split(b'|')
                if len(fields) == 3:
                    _nums = fields[1].split(b'.')

                    if len(_nums) == 4:
                        self._serial = [int(i) for i in _nums]
                        self._serial = [self._serial[3], self._serial[2], self._serial[1], self._serial[0]]
                        self._serial, = struct.unpack("<I", bytes(self._serial))
                        serial.request_handle(self, self._serial)
                    else:
                        self._serial = None

                    self._port = 0
        else:
            print("SocketProtocol.data_received received %d bytes" % len(data))
            serial.send_data(self, self._handle, data)

    def eof_received(self):
        pass

    def send_data(self, data):
        print("SocketProtocol.send_data handle %d size %d" % (self._handle, len(data)))
        self._transport.write(data)

    def recv_data_nack(self):
        print("SocketProtocol.recv_data_nack handle %d" % self._handle)
        self._transport.close()


async def loop_terimation(server):
    print('\n\nClosing server.....')
    server.close()
    await server.wait_closed()

    for client in clients:
        print('Close client')
        client.close_transport()
    while len(clients) > 0:
        await asyncio.sleep(0.10)
    loop.call_later(500, loop.stop)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    prot = serial_asyncio.create_serial_connection(loop, SerialProtocol, '/dev/ttyUSB0', baudrate=115200)

    coro = loop.create_server(SocketProtocol, host='127.0.0.1', port=6053)
    server = loop.run_until_complete(coro)

    asyncio.ensure_future(prot)
    try:
        loop.run_forever()
    except KeyboardInterrupt as e:
        loop.run_until_complete(loop_terimation(server))
    finally:
        loop.close()
