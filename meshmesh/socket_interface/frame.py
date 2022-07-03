import struct

from .python2to3 import byteToInt, intToByte


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
            return

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
