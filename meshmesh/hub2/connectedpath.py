import asyncio
import binascii
import struct
import logging
import datetime

from typing import Optional, List, Callable

from .serialprotocol import SerialProtocol
from .network import GraphNetwork

from .frame import APIFrame

MESHMESH_PROTOCOL_CONNPATH = 7
CONNPATH_OPEN_CONNECTION_REQ = 1
CONNPATH_INVALID_HANDLE = 4
CONNPATH_SEND_DATA = 5
CONNPATH_OPEN_CONNECTION_ACK = 6
CONNPATH_OPEN_CONNECTION_NACK = 7
CONNPATH_DISCONNECT_REQ = 8
CONNPATH_SEND_DATA_ERROR = 9
CONNPATH_CLEAR_CONNECTIONS = 10
CMD_CONNPATH_REQUEST = 122
CMD_CONNPATH_REPLY = 123


def connectpath_receive_callback(data):
    ConnectedPathProtocol.get().receive_data(data)


class ConnectedPathError(Exception):
    pass


class ConnectionInvalidHandle(Exception):
    pass


class ConnectionSendDataError(Exception):
    pass


STATUS_CONN_INIT = 0
STATUS_CONN_ACTIVE = 1
STATUS_CONN_ERROR = 2


class ConnetionLogLine(object):
    def __init__(self, path, handle, port):
        self._path = path
        self._handle = handle
        self._port = port
        self._created_at = datetime.datetime.now()
        self._finished_at = None
        self._termination_reason = ''

    def close_connection(self, reason):
        self._termination_reason = reason
        self._finished_at = datetime.datetime.now()

    @property
    def handle(self):
        return self._handle

    @property
    def port(self):
        return self._port

    @property
    def path(self):
        return self._path

    @property
    def created_at(self):
        return self._created_at

    @property
    def finished_at(self):
        return self._finished_at

    @property
    def termination_reason(self):
        return self._termination_reason


class Connection(object):
    def __init__(self, parent, target, handle, port):
        #  type: (ConnectedPathProtocol, int, int, int) -> None
        loop = asyncio.get_running_loop()
        self._handle = handle  # type: int
        self._target = target  # type: int
        self._port = port  # type: int
        self._status = STATUS_CONN_INIT  # type: int
        self._init_done = loop.create_future()  # type: asyncio.Future
        self._reply_received = None  # type: Optional[asyncio.Future]
        self._init_done_callback = None  # type: Optional[Callable]
        self._receive_callback = None  # type: Optional[Callable]
        self._disconnect_callback = None  # type: Optional[Callable]
        self._parent = parent  # type: ConnectedPathProtocol
        self._log_line = None  # type: Optional[ConnetionLogLine]

        self._init_done.add_done_callback(self.init_done_callback)

    def receive_data(self, subprot, buffer):
        if subprot == CONNPATH_OPEN_CONNECTION_ACK:
            if self._status == STATUS_CONN_INIT:
                self.init_done()
            else:
                logging.error('CONNPATH_OPEN_CONNECTION_ACK on already active connection for {self.target:06X}:{self._handle:04X}')
        elif subprot == CONNPATH_OPEN_CONNECTION_NACK:
            self.init_error()
        elif subprot == CONNPATH_SEND_DATA:
            if self.receive_callback is not None:
                self.receive_callback(buffer)
            elif self._reply_received is not None and not self._reply_received.done():
                self._reply_received.set_result(buffer)
        elif subprot in [CONNPATH_SEND_DATA_ERROR, CONNPATH_INVALID_HANDLE]:
            self.data_error()

    def register_callbacks(self, init_done, receive, disconnect):
        # type: (Optional[Callable], Optional[Callable], Optional[Callable]) -> None
        self._init_done_callback = init_done
        self._receive_callback = receive
        self._disconnect_callback = disconnect

    def unregister_callbacks(self):
        self._receive_callback = None
        self._disconnect_callback = None

    def make_connection(self):
        asyncio.create_task(self.wait_init_done())

    def disconnect_from_client(self):
        logging.debug(f'Connection.disconnect_from_client {self.target:06X}:{self.handle:04X}')
        self.unregister_callbacks()
        self._parent.request_disconnection(self.handle)
        self._log_line.close_connection('CD')
        self._parent.remove_connection(self)

    def send_data_from_client(self, data):
        #  type: (bytes) -> None
        self._parent.send_data_async(data, self._handle)

    async def wait_reply_from_server(self):
        #  type: () -> bytes
        loop = asyncio.get_running_loop()
        self._reply_received = loop.create_future()

        try:
            await asyncio.wait_for(self._reply_received, 5)
        except asyncio.TimeoutError:
            raise ConnectedPathError('Reply not received')

        try:
            result = self._reply_received.result()
        except asyncio.CancelledError:
            raise ConnectedPathError('Data tansmission error')
        except asyncio.InvalidStateError:
            raise ConnectedPathError('Invalid state error')

        self._reply_received = None
        return result

    def init_done_callback(self, fut):
        #  type: (asyncio.Future) -> None
        try:
            res = fut.result()
            logging.debug(f'Connection.init_done_callback to {self.target:06X}:{self._handle:04X} result {res}')
            if res and self._init_done_callback is not None:
                self._init_done_callback()
        except asyncio.CancelledError:
            logging.debug(f'Connection.init_done_callback to {self.target:06X}:{self._handle:04X} CancelledError')
        except asyncio.InvalidStateError:
            logging.debug(f'Connection.init_done_callback to {self.target:06X}:{self._handle:04X} InvalidStateError')

    async def wait_init_done(self):
        try:
            await asyncio.wait_for(self._init_done, 1.3)
        except asyncio.TimeoutError:
            print('Connection.init_terminated TimeoutError after 1.3s')
            self.init_error()

    def init_done(self):
        self._status = STATUS_CONN_ACTIVE
        try:
            self._init_done.set_result(True)
        except asyncio.InvalidStateError as ex:
            logging.error(f'Connection.init_error {self.target:06X}:{self._handle:04X} {str(ex)}')

    def init_error(self):
        self._status = STATUS_CONN_ERROR
        logging.error(f'Connection.init_error {self.target:06X}:{self._handle:04X}')
        try:
            self._init_done.set_result(False)
        except asyncio.InvalidStateError as ex:
            logging.error(f'Connection.init_error {str(ex)}')
        if self._disconnect_callback is not None:
            self._disconnect_callback()
        self._log_line.close_connection('IE')
        self._parent.remove_connection(self)

    def data_error(self):
        self._status = STATUS_CONN_ERROR
        if self._disconnect_callback is not None:
            self._disconnect_callback()
        elif self._reply_received is not None and not self._reply_received.done():
            self._reply_received.cancel('Data receive error')
        self._log_line.close_connection('DE')
        self._parent.remove_connection(self)

    @property
    def handle(self):
        return self._handle

    @property
    def target(self):
        return self._target

    @property
    def port(self):
        return self._port

    @property
    def status(self):
        return self._status

    @property
    def init_done_future(self):
        #  type: () -> asyncio.Future
        return self._init_done

    @property
    def receive_callback(self):
        return self._receive_callback

    @property
    def disconnect_callback(self):
        return self._disconnect_callback

    @property
    def log_line(self):
        #  type: () -> ConnetionLogLine
        return self._log_line

    @log_line.setter
    def log_line(self, value):
        #  type: (ConnetionLogLine) -> None
        self._log_line = value


class ConnectedPathProtocol(object):
    _singleton = None  # type: Optional[ConnectedPathProtocol]

    @staticmethod
    def get():
        # type: () -> ConnectedPathProtocol
        if ConnectedPathProtocol._singleton is None:
            ConnectedPathProtocol._singleton = ConnectedPathProtocol()
        return ConnectedPathProtocol._singleton

    def __init__(self):
        super().__init__()
        self._next_handle = 1  # type: int
        self._sequence_number = 1  # type: int
        self._timeout = 3.0  # type: float
        self._connections = []  # type: List[Connection]
        self._serial_lock = asyncio.Lock()  # type: asyncio.Lock
        self._log_lines = []  # type: List[ConnetionLogLine]
        logging.info("ConnectedPathProtocol.__init__")

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def sequence_number(self):
        seq = self._sequence_number
        self._sequence_number += 1
        if self._sequence_number > 65535:
            self._sequence_number = 1
        return seq

    @property
    def next_handle(self):
        handle = self._next_handle
        self._next_handle += 1
        if self._next_handle > 65535:
            self._next_handle = 1
        return handle

    @property
    def version(self):
        return '1.0.0'

    async def send_and_receive_data(self, data, target):
        #  type: (bytes, int) -> bytes
        logging.debug(f"send_and_receive_data target:0x{target:06X} {binascii.hexlify(data)}")
        conn = self._find_connection(target, 0)
        if conn is None:
            targets = GraphNetwork.instance().shortest_path(target)
            conn = self.make_connection_async(targets, 0)
            await conn.init_done_future
        conn.send_data_from_client(data)
        return await conn.wait_reply_from_server()

    def send_clear_all_connections(self):
        # type: () -> None
        self.send_sub_protocol(0, CONNPATH_CLEAR_CONNECTIONS)

    def send_invalid_handle(self, handle):
        # type: (int) -> None
        self.send_sub_protocol(handle, CONNPATH_INVALID_HANDLE)

    def send_data_async(self, data, handle):
        # type: (bytes, int) -> None
        self.send_sub_protocol(handle, CONNPATH_SEND_DATA, data)

    def send_sub_protocol(self, handle, subprot, data=b''):
        # type: (int, int, bytes) -> None
        buffer = struct.pack(f"<BBBHHHH", CMD_CONNPATH_REQUEST, MESHMESH_PROTOCOL_CONNPATH, subprot, handle, 0, self.sequence_number, len(data))
        if len(data) > 0:
            buffer += data
        self._send_api_frame(buffer)

    def make_connection_async(self, targets, port, init_done=None, receive=None, disconnect=None):
        # type: (List[int], int, Optional[Callable], Optional[Callable], Optional[Callable]) -> Connection
        path_len = len(targets)
        data_length = 4*path_len+3

        handle = self.next_handle
        buffer = struct.pack(f"<BBBHHHHHB", CMD_CONNPATH_REQUEST, MESHMESH_PROTOCOL_CONNPATH, CONNPATH_OPEN_CONNECTION_REQ,
                             handle, 0, self.sequence_number, data_length, port, path_len)
        if path_len > 0:
            buffer += struct.pack(f"{path_len}I", *targets)

        log_line = ConnetionLogLine(targets, handle, port)
        self._log_lines.append(log_line)

        conn = Connection(self, targets[-1], handle, port)
        self._connections.append(conn)
        conn.log_line = log_line
        conn.register_callbacks(init_done, receive, disconnect)
        conn.make_connection()
        self._send_api_frame(buffer, 0.5)

        logging.debug(f"make_connection_async active connections {len(self._connections)}")
        for i in range(len(self._connections)):
            c = self._connections[i]
            logging.debug(f"make_connection_async {i} {c.target:06X}:{c.handle:04X}")
        return conn

    def request_disconnection(self, handle):
        # type: (int) -> None
        buffer = struct.pack(f"<BBBHHHH", CMD_CONNPATH_REQUEST, MESHMESH_PROTOCOL_CONNPATH, CONNPATH_DISCONNECT_REQ,
                             handle, 0, self._sequence_number, 0)
        self._sequence_number += 1
        self._send_api_frame(buffer)

    def receive_data(self, buffer):
        #  type: (bytes) -> None
        prot, subprot, handle = struct.unpack("<BBH", buffer[0:4])
        for conn in self._connections:
            if handle == conn.handle:
                break
        else:
            logging.error(f'receive_data invalid handle {handle}')
            self.send_invalid_handle(handle)
            return

        conn.receive_data(subprot, buffer[4:])
        if subprot in [CONNPATH_OPEN_CONNECTION_ACK, CONNPATH_OPEN_CONNECTION_NACK, CONNPATH_SEND_DATA_ERROR, CONNPATH_INVALID_HANDLE]:
            self._unlock_frame()

    def register_callback(self, init_done_cb, receive_cb, disconnect_cb, handle):
        # type: (Callable, Callable, Callable, int) -> None
        conn = self._connection(handle)
        if conn:
            conn.register_callbacks(init_done_cb, receive_cb, disconnect_cb)

    def unregister_callback(self, handle):
        # type: (int) -> None
        conn = self._connection(handle)
        if conn:
            conn.unregister_callbacks()

    def remove_connection(self, connection):
        #  type: (Connection) -> None
        try:
            self._connections.remove(connection)
        except ValueError:
            logging.error(f'remove_connection already removed!')

    def connection_error(self, connection):
        #  type: (Connection) -> None
        connection.init_error() if connection.status == STATUS_CONN_INIT else connection.data_error()
        if connection.disconnect_callback is not None:
            connection.disconnect_callback()
        self._connections.remove(connection)

    async def save_log_lines(self):
        #  type: () -> None
        while True:
            with open('/dev/shm/connectedpath.log', 'w') as f:
                f.write('indx | port | hndl | Created on           | Elapsed         | Tr | path\n')
                f.write('-----|------|------|----------------------|-----------------|----|-------------------------------\n')
                for i in range(len(self._log_lines)):
                    line = self._log_lines[i]
                    path = self._format_path(line.path)
                    created = line.created_at.strftime("%m/%d/%Y, %H:%M:%S")
                    endtime = line.finished_at if line.finished_at is not None else datetime.datetime.now()
                    delta = endtime - line.created_at  # type: datetime.timedelta
                    elapsed = f'{delta}'
                    f.write(f'{i:04d} | {line.port:04d} | {line.handle:04X} | {created:20} | {elapsed:15} | {line.termination_reason:2} | { path}\n')
            await asyncio.sleep(5)

    def _connection(self, handle):
        #  type: (int) -> Optional[Connection]
        for c in self._connections:
            if c.handle == handle:
                return c
        else:
            return None

    def _find_connection(self, target, port):
        #  type: (int, int) -> Optional[Connection]
        for c in self._connections:
            if c.target == target and c.port == port:
                return c
        else:
            return None

    @staticmethod
    def _format_path(targets):
        path = None
        for target in targets:
            if path is None:
                path = f'{target:06X}'
            else:
                path += f' -> {target:06X}'
        return path

    @staticmethod
    def _send_api_frame(buffer, timeout=0):
        #  type: (bytes, float) -> None
        serial = SerialProtocol.get()  # type: SerialProtocol
        if serial is None:
            raise Exception('Serial protocol not initialized')
        frame = APIFrame(buffer, escaped=True)
        serial.send_api_frame(frame, timeout)

    @staticmethod
    def _unlock_frame():
        serial = SerialProtocol.get()  # type: SerialProtocol
        if serial is None:
            raise Exception('Serial protocol not initialized')
        serial.unlock_tx_frame()


def connectedpath_setup():
    cp = ConnectedPathProtocol.get()  # type: ConnectedPathProtocol
    logging.info(f'connectedpath_setup initialized {cp.name} {cp.version}')
    SerialProtocol.get().register_callback(connectpath_receive_callback, CMD_CONNPATH_REPLY)
    cp.send_clear_all_connections()


def connectedpath_pre_run(loop):
    #  type: (asyncio.AbstractEventLoop) -> None
    cp = ConnectedPathProtocol.get()  # type: ConnectedPathProtocol
    loop.create_task(cp.save_log_lines())
