import logging
import time
import serial
import struct
import binascii
import ipaddress

from meshmesh.hub import frame
from meshmesh.hub.frame import APIFrame, APIFrameEcho, APIFrameSocket, CMD_UART_ECHO_REP
from meshmesh.hub.python2to3 import intToByte, byteToInt

_LOGGER = logging.getLogger(__name__)

AF_INET = 2

SOCK_STREAM = 1

IPPROTO_TCP = 6
IPPROTO_UDP = 17

TCP_NODELAY = 1

SOL_SOCKET = 1

SO_SNDBUF = 7

_asyncio_loop = None
_async_serial = None


class error(Exception):
    pass


class socket(object):
    def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
        self._serial = serial.Serial('/dev/ttyUSB0', baudrate=460800, timeout=0)  # type: serial.Serial
        self._input_frame = None

        self._timeout = 10
        self._family = family
        self._type = type

        self._handle = 0
        self._test_device()

    def settimeout(self, timeout):
        self._timeout = timeout

    def connect(self, remote):
        remoteip, remoteport = remote
        _LOGGER.debug("Connecting to %s:%s", remoteip, remoteport)

        if remoteip == '0.244.38.24':
            target = [int(ipaddress.IPv4Address('0.185.229.69')), int(ipaddress.IPv4Address(remoteip))]
        else:
            target = int(ipaddress.IPv4Address(remoteip))
        apisock = APIFrameSocket.make_uart_connect_to(target=target, port=remoteport, id=1)

        repeat = 1
        recvok = False
        while repeat>0 and not recvok:
            start = time.time()
            print('socket_interface.connect write %d %s' % (len(apisock.output()), binascii.hexlify(apisock.output())))
            self._serial.write(apisock.output())
            timeout = 0.25 if self._handle == 0 else self._timeout
            timeout = 15
            while time.time() - start < timeout:
                cmd, recv = self._recv()
                if cmd is not None and cmd == frame.CMD_SOCKET_REPLY:
                    cmd = recv[0]
                    recv = recv[1:]
                    if cmd == frame.ToUart.CONNECT_ACCEPTED.value:
                        self._handle, = struct.unpack("<H", recv[0:2])
                        print('CONNECT_ACCEPTED received with handle', self._handle)
                        recvok = True
                        break
                    elif cmd == frame.ToUart.CONNECT_ACK.value:
                        self._handle, = struct.unpack("<H", recv[0:2])
                        timeout = self._timeout
                        print('CONNECT_ACK ack handle', self._handle)
                    elif cmd == frame.ToUart.CONNECT_REJECTED.value:
                        raise error('Connection rejected')

            repeat -= 1

        if not recvok:
            raise error()

    def close(self):
        pass

    def setsockopt(self, level, optname, value):
        pass

    def sendall(self, data):
        apisock = APIFrameSocket.make_uart_send_data(handle=self._handle, data=data)
        # print('socket_interface.sendall write %d bytes %s' % (len(data), binascii.hexlify(apisock.output()[0:10])))
        outdata = apisock.output()
        chunksize = 0x40
        outdatachunks = int(len(outdata)/chunksize+1)
        for i in range(0, outdatachunks):
            chunk = outdata[i*chunksize:(i+1)*chunksize]
            self._serial.write(chunk)
            # FIXME we lose some byte over serial.
            time.sleep(0.01)
        # self._serial.write(outdata)

    def wait_send_ack(self):
        ack = False
        print('socket_interface.wait_send_ack start')
        while not ack:
            cmd, recv = self._recv()
            if cmd is not None and cmd == frame.CMD_SOCKET_REPLY:
                cmd = recv[0]
                recv = recv[1:]
                if cmd == frame.ToUart.SEND_DATA.value:
                    print('socket_interface.wait_send_ack received')
                    return True

    def nonblock_recv(self):
        cmd, recv = self._recv()
        if cmd is not None and cmd == frame.CMD_SOCKET_REPLY:
            cmd = recv[0]
            recv = recv[1:]
            if cmd == frame.ToUart.SEND_DATA.value:
                handle, = struct.unpack("<H", recv[0:2])
                recv = recv[2:]
                if handle == self._handle:
                    print('recv bytes', len(recv))
                    return recv
        return b''

    def recv(self, buffersize, flags=None):
        res = b''
        start = time.time()
        second = 0
        while len(res) < buffersize:
            cmd, recv = self._recv()
            if cmd is not None and cmd == frame.CMD_SOCKET_REPLY:
                cmd = recv[0]
                recv = recv[1:]
                if cmd == frame.ToUart.SEND_DATA.value:
                    handle, = struct.unpack("<H", recv[0:2])
                    recv = recv[2:]
                    if handle == self._handle:
                        res += recv
                        # print('recv bytes', len(res))
            else:
                now = time.time()
                _second = int(time.time()-start)
                if _second != second:
                    second = _second
                    print(f'socket_interface.recv {len(res)} timeout {second}')
        return res

    def _test_device(self):
        echo = APIFrameEcho(b"\xC1\xA0", True)

        repeat = 10
        recvok = False
        while repeat>0 and not recvok:
            start = time.time()
            print('socket_interface._test_device write %s' % binascii.hexlify(echo.output()))
            self._serial.write(echo.output())
            while time.time() - start < 0.25:
                cmd, recv = self._recv()
                if cmd is not None and cmd == CMD_UART_ECHO_REP and recv[0] == 0xC1 and recv[1] == 0xA0:
                    recvok = True
                    break
            repeat -= 1

        if not recvok:
            raise error()

    def _recv(self):
        _bytes = self._serial.read(1)
        if len(_bytes) == 0:
            time.sleep(0.05)
        else:
            while len(_bytes) > 0:
                byte = intToByte(_bytes[0])
                # Print intra frame messages
                if byte != APIFrame.START_BYTE and not self._input_frame:
                    try:
                        print(byte.decode('utf-8'), end='')
                    except UnicodeDecodeError:
                        pass
                elif byte == APIFrame.START_BYTE and not self._input_frame:
                    # print('start frame')
                    self._input_frame = APIFrame(escaped=True)
                    self._input_frame.fill(byte)
                else:
                    if self._input_frame.fill(byte):
                        self._input_frame.parse()
                        data = self._input_frame.data
                        if len(data) > 0:
                            cmd = intToByte(data[0])
                            self._input_frame = None
                            return cmd, data[1:]
                        self._input_frame = None
                _bytes = self._serial.read(1)
        return None, None