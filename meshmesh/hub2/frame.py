import struct
from enum import Enum

from .python2to3 import byteToInt, intToByte

CMD_UART_ECHO_REQ = b"\x00"
CMD_UART_ECHO_REP = b"\x01"
CMD_CONNPATH_REQUEST = b"\x7A"
CMD_SOCKET_REQUEST = b'\x7C'
CMD_SOCKET_REPLY = b'\x7D'

FROMUART_CONNECT_TO = b'\x00'
FROMUART_SEND_DATA = b'\x02'
FROMUART_DISCONECT_FROM = b'\x04'
FROMUART_SEND_DATA_WITH_ACK = b'\x06'

#TOUART_CONNECT_REJECTED = b'\x01'
#TOUART_CONNECT_ACCEPTED = b'\x02'
#TOUART_CONNECT_ACK = b'\x03'
#TOUART_DISCONNECT = b'\x04'
#TOUART_SEND_DATA = b'\x05'
#TOUART_SEND_DATA_ACK = b'\x06'


class ToUart(Enum):
    UNKOW_COMMAND = 0
    CONNECT_REJECTED = 1
    CONNECT_ACCEPTED = 2
    CONNECT_ACK = 3
    DISCONNECT = 4
    SEND_DATA = 5
    SEND_DATA_ACK = 6


class APIFrame:
    """
    Represents a frame of data to be sent to or which was received 
    from an XBee device
    """

    START_BYTE = b'\xFE'
    ESCAPE_BYTE = b'\xEA'
    END_BYTE = b'\xEF'
    ESCAPE_BYTES = (START_BYTE, ESCAPE_BYTE, END_BYTE)

    def __init__(self, data=b'', escaped=False):
        self.data = data
        self.raw_data = b''
        self.escaped = escaped
        self._unescape_next_byte = False

    def clear(self):
        self.data = b''
        self.raw_data = b''
        self._unescape_next_byte = False

    def checksum(self):
        """
        checksum: None -> single checksum byte

        checksum adds all bytes of the binary, unescaped data in the 
        frame, saves the last byte of the result, and subtracts it from 
        0xFF. The final result is the checksum
        """
        total = 0

        # Add together all bytes
        for byte in self.data:
            total += byteToInt(byte)

        # Only keep the last byte
        total = total & 0xFF

        return intToByte(0xFF - total)

    def verify(self, chksum):
        """
        verify: 1 byte -> boolean

        verify checksums the frame, adds the expected checksum, and 
        determines whether the result is correct. The result should 
        be 0xFF.
        """
        total = 0

        # Add together all bytes
        for byte in self.data:
            total += byteToInt(byte)

        # Add checksum too
        total += byteToInt(chksum)

        # Only keep low bits
        total &= 0xFF

        # Check result
        return total == 0xFF

    def len_bytes(self):
        """
        len_data: None -> (MSB, LSB) 16-bit integer length, two bytes

        len_bytes counts the number of bytes to be sent and encodes the 
        data length in two bytes, big-endian (most significant first).
        """
        count = len(self.data)
        return struct.pack("> h", count)

    def output(self):
        data = self.data
        # Only run the escaoe process if it hasn't been already
        if self.escaped and len(self.raw_data) < 1:
            self.raw_data = APIFrame.escape(data)

        if self.escaped:
            data = self.raw_data

        # Never escape start byte
        return APIFrame.START_BYTE + data + APIFrame.END_BYTE

    @staticmethod
    def escape(data):
        escaped_data = b""
        for byte in data:
            if intToByte(byteToInt(byte)) in APIFrame.ESCAPE_BYTES:
                escaped_data += APIFrame.ESCAPE_BYTE
                escaped_data += intToByte(byteToInt(byte))
            else:
                escaped_data += intToByte(byteToInt(byte))

        return escaped_data

    def fill(self, byte):
        escaped = False
        if self._unescape_next_byte:
            escaped = True
            self._unescape_next_byte = False
        elif self.escaped and byte == APIFrame.ESCAPE_BYTE:
            self._unescape_next_byte = True
            return False

        self.raw_data += intToByte(byteToInt(byte))
        return True if byte == APIFrame.END_BYTE and not escaped else False

    def remaining_bytes(self):
        remaining = 3

        if len(self.raw_data) >= 3:
            # First two bytes are the length of the data
            raw_len = self.raw_data[1:3]
            data_len = struct.unpack("> h", raw_len)[0]

            remaining += data_len

            # Don't forget the checksum
            remaining += 1

        return remaining - len(self.raw_data)

    def parse(self):
        if len(self.raw_data) < 3:
            ValueError("parse() may only be called on a frame containing at least 3 bytes of raw data (see fill())")

        self.data = self.raw_data[1:-1]


class APIFrameEcho(APIFrame):
    def __init__(self, data, escaped=False):
        super().__init__(CMD_UART_ECHO_REQ + data, escaped=escaped)


class APIFrameSocket(APIFrame):
    def __init__(self, command, escaped):
        super().__init__(CMD_SOCKET_REQUEST + command, escaped=escaped)

    @staticmethod
    def make_uart_connect_to(target, port, id):
        if isinstance(target, list):
            print(f"<{len(target)}IHH")
            payload = struct.pack(f"<{len(target)}IHH", *target, port, id)
        else:
            payload = struct.pack("<IHH", target, port, id)
        return APIFrameSocket(FROMUART_CONNECT_TO + payload, escaped=True)

    @staticmethod
    def make_uart_send_data(handle, data):
        payload = struct.pack("<H", handle) + data
        return APIFrameSocket(FROMUART_SEND_DATA + payload, escaped=True)

    @staticmethod
    def make_uart_send_data_ack(handle, data):
        payload = struct.pack("<H", handle) + data
        return APIFrameSocket(FROMUART_SEND_DATA_WITH_ACK + payload, escaped=True)

    @staticmethod
    def make_uart_disconnect_from(handle):
        payload = struct.pack("<H", handle)
        return APIFrameSocket(FROMUART_DISCONECT_FROM + payload, escaped=True)
