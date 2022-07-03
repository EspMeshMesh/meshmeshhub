import asyncio
import logging
import struct
import time

from xmlrpc.client import Fault

from typing import Optional, List, Any

from .connectedpath import ConnectedPathProtocol, Connection, STATUS_CONN_ACTIVE
from .serialprotocol import SerialProtocol
from .network import GraphNetwork

server = None  # type: Optional[Any]
clients = []  # type: List[SocketProtocol]


class SocketProtocol(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        logging.debug('SocketProtocol.__init__')
        self._transport = None
        self._handshake_started = False
        self._handshake = False
        self._serial = None  # type: Optional[SerialProtocol]
        self._address = None
        self._port = 0
        self._connection = None  # type: Optional[Connection]
        self._timeout = 0
        self._timeout_task = None  # type: Optional[asyncio.Task]

    @property
    def serial(self):
        return self._address

    @property
    def connection(self):
        return self._connection

    async def check_timeout(self):
        # This task is continously checking that other socket end is sending data otherwise will
        # close connection after 5 minutes
        while True:
            await asyncio.sleep(1)
            if time.time() - self._timeout > 300:
                logging.warning(f"SocketProtocol.check_timeout. No dat for 300s. Closing transport")
                break
        self.close_transport()

    def close_transport(self):
        if self._transport:
            logging.warning(f"SocketProtocol.close_transport is_clsing:{self._transport.is_closing()}")
            self._transport.close()

    def connection_made(self, transport):
        global clients
        logging.warning('SocketProtocol.connection_made')
        self._transport = transport
        self._serial = SerialProtocol.get()
        self._timeout = time.time()
        self._timeout_task = asyncio.get_event_loop().create_task(self.check_timeout())
        clients.append(self)

    def connection_lost(self, exc):
        global clients
        logging.warning(f'SocketProtocol.connection_lost handshake {self._handshake}')
        if self._timeout_task and not self._timeout_task.done():
            self._timeout_task.cancel()
        if self._handshake:
            self._connection.disconnect_from_client()
        clients.remove(self)

    def init_done_remote(self):
        if self._connection.status == STATUS_CONN_ACTIVE:
            self._handshake = True
            self._transport.write(b'!!OK!')
            logging.warning(f'SocketProtocol.make_connection_done {self._address:06X}:{self._connection.handle:04x}')
        else:
            self.close_transport()

    def data_received_remote(self, data):
        self._transport.write(data)

    def disconnect_remote(self):
        logging.debug(f"SocketProtocol.disconnect_remote {self._connection.target:06X}:{self._connection.handle:04X}")
        self._transport.close()

    def data_received(self, data: bytes):
        global clients
        # logging.debug(f'SocketProtocol.data_received {self._handshake} {data[0]} {self._handle} {binascii.hexlify(data)}')
        if not self._handshake:
            if not self._handshake_started:
                self._handshake_started = True
                if len(data) > 4 and data[0:4] == b'INIT':
                    fields = data.split(b'|')
                    if len(fields) == 3:
                        self._port = int(fields[2].strip())
                        _nums = fields[1].split(b'.')
                        if len(_nums) == 4:
                            self._address = [int(i) for i in _nums]
                            self._address = [self._address[3], self._address[2], self._address[1], self._address[0]]
                            self._address, = struct.unpack("<I", bytes(self._address))
                            self.init_connection()
                        else:
                            self._address = None
                        self._port = 0
                else:
                    logging.error('Invalid handshake received. Closing connection')
                    self._transport.close()
        else:
            # cmd = data[0]
            self._timeout = time.time()
            ConnectedPathProtocol.get().send_data_async(data, self._connection.handle)

    def eof_received(self):
        return False

    def init_connection(self):
        logging.debug(f"SocketProtocol.init_connection addr 0x{self._address:00x} port {self._port}")
        try:
            path = GraphNetwork.instance().shortest_path(self._address) if GraphNetwork.instance().is_network_loaded() else self._address
        except Fault:
            self._transport.close()
            return

        if path is not None:
            cp = ConnectedPathProtocol.get()  # type: ConnectedPathProtocol
            self._connection = cp.make_connection_async(path, self._port, self.init_done_remote, self.data_received_remote,
                                                        self.disconnect_remote)  # type: Connection


def esphomeapi_setup(loop: asyncio.AbstractEventLoop):
    global server
    coro = loop.create_server(SocketProtocol, host='0.0.0.0', port=6053)
    server = loop.run_until_complete(coro)


def esphomeapi_shutdown():
    global server, clients
    if server:
        server.close()
    for client in clients:
        client.close_transport()
