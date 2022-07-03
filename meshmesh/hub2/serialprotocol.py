import asyncio
import binascii
import logging
import time
from typing import Optional, List

from .frame import APIFrame
from .direct import DirectBase


class TxFrameHandler:
    def __init__(self, frame, lock_timeout=0):
        #  type: (APIFrame, float) -> None
        self._frame = frame  # type: APIFrame
        self._lock_timeout = lock_timeout  # type: float

    @property
    def frame(self):
        return self._frame

    @property
    def lock_timeout(self):
        #  type: () -> float
        return self._lock_timeout


class RxFrameHandler:
    def __init__(self, byte1, byte2=None):
        self._byte1 = byte1  # type: int
        self._byte2 = byte2  # type: int
        self._rx_frames = asyncio.Queue()  # type: asyncio.Queue
        self._callback = None

    @property
    def rx_frames(self):
        return self._rx_frames

    def set_callback(self, callback):
        self._callback = callback

    def is_mine(self, data):
        if len(data) > 0 and data[0] == self._byte1:
            if self._byte2 is None:
                return True
            else:
                return len(data) > 1 and data[1] == self._byte2
        return False

    def frame_received(self, data):
        if self._callback is not None:
            self._callback(data)
        else:
            self.rx_frames.put_nowait(data)


class SerialProtocol(asyncio.Protocol):
    _singleton = None  # type: Optional[SerialProtocol]

    @staticmethod
    def get():
        # type: () -> Optional[SerialProtocol]
        return SerialProtocol._singleton

    @property
    def rx_frames(self):
        return self._rx_frames

    @property
    def lock(self):
        # type: () -> asyncio.Lock
        return self._lock

    def __init__(self):
        super().__init__()
        print('SerialProtocol.__init__')
        self._input_frame = None  # type: Optional[APIFrame]
        self._transport = None  # type: Optional[asyncio.Transport]
        self._rx_frames = asyncio.Queue()  # type: asyncio.Queue
        self._tx_frames = asyncio.Queue()  # type: asyncio.Queue
        self._callbacks = []  # type: List[RxFrameHandler]
        self._lock = asyncio.Lock()  # type: asyncio.Lock
        self._tx_lock = False  # type: bool
        self._tx_lock_event = asyncio.Event()  # type: asyncio.Event
        self._tx_lock_time = 0  # type: int
        self._file = None
        self.spare_bytes = ''

    def connection_made(self, transport: asyncio.Transport):
        print('SerialProtocol.connection_made')
        self._transport = transport
        self._file = open('/tmp/serial_received.dat', 'wb')
        SerialProtocol._singleton = self

    def connection_lost(self, exc):
        print('SerialProtocol.connection_lost', exc)
        self._file.close()

    def data_received(self, data: bytes):
        self._file.write(data)
        for b in data:
            b = bytes([b])
            # Print every character the is not inside an API frame.
            if b != APIFrame.START_BYTE and self._input_frame is None:
                try:
                    if b == b'\x0A' or b == b'\x0D':
                        if len(self.spare_bytes) > 0:
                            logging.debug(f'Node said: {self.spare_bytes}')
                            self.spare_bytes = ''
                    else:
                        self.spare_bytes += b.decode('utf-8')
                except UnicodeDecodeError:
                    pass

            if self._input_frame is None:
                if b == APIFrame.START_BYTE:
                    # print('start')
                    self._input_frame = APIFrame(escaped=True)
                    self._input_frame.fill(b)
            else:
                if self._input_frame.fill(b):
                    try:
                        self._input_frame.parse()
                        # if self._input_frame.data[0] != 0x39:
                        #   logging.debug(f'SerialProtocol.data_received  frame
                        #   {len(self._input_frame.data)} {binascii.hexlify(self._input_frame.data)}')
                        self.frame_received(self._input_frame.data)
                        self._input_frame = None
                    except ValueError:
                        # Bad frame, so restarts
                        self._input_frame = None

    def frame_received(self, data):
        # print('SerialProtocol.frame_received', data[0])
        if data[0] == 0x39:
            frame = DirectBase.split_response(data)
            logging.info(f"Log from 0x{frame['from']:08X} level {frame['level']} {frame['line'].decode()}")
        else:
            for cb in self._callbacks:
                if cb.is_mine(data):
                    cb.frame_received(data)
                    data = None
            if data is not None:
                self._rx_frames.put_nowait(data)

    def unlock_tx_frame(self):
        logging.debug(f'SerialProtocol.unlock_tx_frame frames {self._tx_frames.qsize()}')
        if self._tx_lock:
            self._tx_lock = False
            self._tx_lock_event.set()
        try:
            txhandler = self._tx_frames.get_nowait()  # type: TxFrameHandler
            self._send_api_frame(txhandler.frame, txhandler.lock_timeout)
        except asyncio.QueueEmpty:
            pass

    def send_api_frame(self, frame, timeout=0):
        #  type: (APIFrame, float) -> None
        if self._tx_lock:
            self._tx_frames.put_nowait(TxFrameHandler(frame, timeout))
            if time.time() - self._tx_lock_time > 0.250:
                logging.error("SerialProtocol.send_api_frame lock active for too much time! Foce unlock ")
                self.unlock_tx_frame()
        else:
            self._send_api_frame(frame, timeout)
        if not self._tx_frames.empty():
            logging.debug(f'SerialProtocol.send_api_frame queue {self._tx_frames.qsize()}')

    def _lock_timeout(self, timeout):
        #  type: (float) -> None
        async def _timeout(to):
            try:
                await asyncio.wait_for(self._tx_lock_event.wait(), to)
            except asyncio.TimeoutError:
                logging.error("SerialProtocol._lock_timeout force unlock after reach timeout")
                self.unlock_tx_frame()
        asyncio.create_task(_timeout(timeout))

    def _send_next_frame(self):
        try:
            txhandler = self._tx_frames.get_nowait()  # type: TxFrameHandler
            self._send_api_frame(txhandler.frame, txhandler.lock_timeout)
        except asyncio.QueueEmpty:
            pass

    def _send_api_frame(self, frame, timeout=0):
        #  type: (APIFrame, float) -> None
        async def _wait_tx_future():
            #  type: () -> None
            await asyncio.sleep(0.02)
            self._send_next_frame()

        self._tx_lock = True if timeout > 0 else False
        if self._tx_lock:
            self._tx_lock_time = time.time()
            self._lock_timeout(timeout)

        if not self._tx_frames.empty():
            # if queue is not empty i must create a future for send next frame
            asyncio.create_task(_wait_tx_future())

        chunksize = 0x40
        data = frame.output()
        # logging.info(f'send_api_frame {binascii.hexlify(data)}')
        outdatachunks = int(len(data) / chunksize + 1)
        for i in range(0, outdatachunks):
            chunk = data[i * chunksize:(i + 1) * chunksize]
            self._transport.write(chunk)
            # FIXME we lose some byte over serial.
            time.sleep(0.005)

    def register_callback(self, callback, byte1, byte2=None):
        cb = RxFrameHandler(byte1, byte2)
        cb.set_callback(callback)
        self._callbacks.append(cb)
        return cb


async def test_serial_device():
    pass
