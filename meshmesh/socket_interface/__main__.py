import asyncio
import serial_asyncio
import time

from .serial import SerialProtocol, StreamClient


class TestLocalNode(StreamClient):
    def __init__(self, serial, address):
        # type: (SerialProtocol, int) -> None
        super().__init__()
        self._connected = False
        self._delete_me = False
        self._counter = 1
        self._serial = serial # type: SerialProtocol
        self._last_text = b""
        self._address = address
        self._last_connection_time = 0
        serial.register_client(self)

    def __del__(self):
        self._serial.unregister_client(self)

    @property
    def is_connected(self):
        return self._connected

    @property
    def delete_me(self):
        return self._delete_me

    @property
    def counter(self):
        return self._counter

    @property
    def last_connection_time(self):
        return self._last_connection_time

    def recv_from_uart(self, data):
        print('TestLocalNode.recv_from_uart size ', len(data))
        print(data, self._last_text)

    def disconnect_from(self):
        print('TestLocalNode.disconnect_from', self._handle)
        self._serial.unregister_client(self)
        self._handle = None
        self._connected = False
        self._delete_me = True

    def connect_with(self):
        print('TestLocalNode.connect_with %08X' % self._address)
        self._serial.request_handle(self._address, self.recv_handle_callback)
        self._last_connection_time = time.time()

    def send_data(self, data):
        self._last_text = data
        self._serial.send_data(self._handle, data)

    def send_disconnect_from(self):
        self._serial.disconnect_from(self._handle)

    def send_echo_data(self):
        self.send_data(b"Pippo%03d" % self._counter)
        self._counter += 1

    def recv_handle_callback(self, handle, is_connected):
        print('TestLocalNode.recv_handle_callback', handle)
        self._handle = handle
        self._connected = is_connected


test1 = None
test2 = None


def node_task(node):
    # type: (TestLocalNode) -> TestLocalNode
    now = time.time()
    if node.delete_me:
        print('delete object test1')
        node = None
    elif node.handle is None:
        if node.last_connection_time + 5.0 < now:
            node.connect_with()
    elif node.is_connected:
        if node.counter > 15:
            node.send_disconnect_from()
        else:
            node.send_echo_data()
    return node


async def periodic_task():
    global  test1, test2

    while True:
        await asyncio.sleep(1)
        if False and not test1:
            if SerialProtocol.serial:
                test1 = TestLocalNode(SerialProtocol.serial, 0)
        if not test2:
            if SerialProtocol.serial:
                test2 = TestLocalNode(SerialProtocol.serial, 0xA7B8F)
        else:
            if test1:
                test1 = node_task(test1)
            if test2:
                test2 = node_task(test2)


async def loop_terimation():
    print('\n\nloop_terimation.....')
    await asyncio.sleep(1.0)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    coro = serial_asyncio.create_serial_connection(loop, SerialProtocol, '/dev/ttyUSB0', baudrate=115200)
    asyncio.ensure_future(coro)

    task = loop.create_task(periodic_task())

    try:
        loop.run_forever()
    except KeyboardInterrupt as e:
        loop.run_until_complete(loop_terimation())
    finally:
        loop.close()
