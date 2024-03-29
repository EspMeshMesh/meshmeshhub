import struct

def byteToInt(byte):
    """
    byte -> int

    Determines whether to use ord() or not to get a byte's value.
    """
    if hasattr(byte, 'bit_length'):
        # This is already an int
        return byte
    return ord(byte) if hasattr(byte, 'encode') else byte[0]


def intToByte(i):
    """
    int -> byte

    Determines whether to use chr() or bytes() to return a bytes object.
    """
    return chr(i) if hasattr(bytes(), 'encode') else bytes([i])


def stringToBytes(s):
    """
    string -> bytes

    Converts a string into an appropriate bytes object
    """
    return s.encode('ascii')


def bytesToInt(b):
    return struct.unpack("<i", b)
