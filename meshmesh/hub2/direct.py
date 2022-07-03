import binascii
import copy
import logging
import struct, threading, time
from serial import SerialException
from binascii import hexlify, unhexlify
from .frame import APIFrame
from. api import api_commands, api_replies
from .python2to3 import byteToInt, intToByte

LOCAL_NODE_SERIAL = 0
BROADCAST_SERIAL = -1


class ThreadQuitException(Exception):
    pass


class CommandFrameException(KeyError):
    pass


class DirectBase(threading.Thread):

    def __init__(self, ser, shorthand=True, callback=None, escaped=False, error_callback=None):
        super(DirectBase, self).__init__()
        self.serial = ser
        self.shorthand = shorthand
        self._callback = None
        self._thread_continue = False
        self._escaped = escaped
        self._error_callback = error_callback
        self._counter = 0
        self._debug = False

        if callback:
            self._callback = callback
            self._thread_continue = True
            self.start()

    def set_debug(self, debug):
        self._debug = debug

    def halt(self):
        if self._callback:
            self._thread_continue = False
            self.join()
            self.serial.close()

    def _write(self, data):
        frame = APIFrame(data, self._escaped).output()
        if self._debug:
            print(__class__, "_write", hexlify(frame).upper())
        self._counter += 1
        self.serial.write(frame)


    def run(self):
        while True:
            try:
                self._callback(self.wait_read_frame())
            except ThreadQuitException:
                print("direct: ThreadQuitException")
                break
            except SerialException as e:
                print("direct: SerialException" + str(e))
                break
            except ValueError as e:
                print(__class__, str(e))
                break
            except Exception as e:
                print("direct: Exception " + str(e))
                if self._error_callback:
                    self._error_callback(e)
                break
        print("direct: Thread exiting")

    def _wait_for_frame(self):
        frame = APIFrame(escaped=self._escaped)

        while True:
            if self._callback and not self._thread_continue:
                raise ThreadQuitException

            if self.serial.inWaiting() == 0:
                time.sleep(.01)
                continue

            byte = self.serial.read()

            if byte != APIFrame.START_BYTE:
                try:
                    print(byte.decode("utf-8"), end='')
                except UnicodeDecodeError:
                    pass
                continue

            # Save all following bytes, if they are not empty
            if len(byte) == 1:
                frame.fill(byte)

            while True:
                byte = self.serial.read()
                #print("%02X" % int.from_bytes(byte, byteorder='big'))
                if len(byte) == 1:
                    if frame.fill(byte):
                        break

            try:
                # Try to parse and return result
                frame.parse()

                # Ignore empty frames
                if len(frame.data) == 0:
                    frame = APIFrame()
                    continue

                return frame
            except ValueError:
                # Bad frame, so restart
                frame = APIFrame(escaped=self._escaped)

    @staticmethod
    def get_api_def(cmd: str):
        cmd_def = None
        prefix = bytearray()

        if cmd.count('/') > 0:
            cmdf = cmd.split('/')
            try:
                api = api_commands
                for cmd in cmdf:
                    cmd_def = api[cmd]
                    prefix.append(cmd_def['id'])
                    if 'submenu' in cmd_def:
                        api = cmd_def['submenu']
            except KeyError:
                logging.error(f"FATAL!!! {cmd} not found in api_commands")
                pass

        else:
            try:
                cmd_def = api_commands[cmd]
                prefix.append(cmd_def['id'])
            except KeyError:
                pass

        if cmd_def:
            cmd_def['prefix'] = prefix
        return cmd_def

    @staticmethod
    def build_command(cmd, **kwargs):
        # if cmd != 'unicast' and cmd != 'polite':
        #    logging.debug("Build command %s %s", cmd, str(kwargs))

        cmd_def = DirectBase.get_api_def(cmd)
        if cmd_def is None:
            raise NotImplementedError(f"{cmd} not found in API")

        cmd_id = cmd_def['id']
        cmd_prefix = cmd_def['prefix'] if 'prefix' in  cmd_def else None
        cmd_spec = cmd_def['args']

        if cmd_prefix is not None:
            packet = b'' + cmd_prefix
        else:
            packet = b'' + intToByte(cmd_id)

        for field in cmd_spec:
            default_value = field.get('default', None)
            try:
                # Read this field's name from the function arguments dict
                data = kwargs[field['name']]
            except KeyError:
                # Data wasn't given
                # Only a problem if the field has a specific length
                if field['len'] is not None:
                    # Was a default value specified?
                    default_value = field['default']
                    if default_value:
                        data = default_value
                    else:
                        # Otherwise, fail
                        raise KeyError("The expected field %s of length %d was not provided" % (field['name'], field['len']))
                else:
                    # No specific length, ignore it
                    data = None

            # Ensure that the proper number of elements will be written
            if 'encode' in field:
                if default_value is not None and isinstance(default_value, list):
                    for d in data:
                        packet += struct.pack(field['encode'], d)
                    continue
                else:
                    data = struct.pack(field['encode'], data)
            else:
                if field['len'] and len(data) != field['len']:
                    raise ValueError(
                        "The data provided for '%s' was not %d bytes long" % (field['name'], field['len']))

            if data:
                packet += data

        return packet

    @staticmethod
    def _size_of_reply(packet):
        size = 0
        structure = packet['structure']
        for field in structure:
            if field['len'] is None:
                return None
            else:
                size += field['len']
        return size

    @staticmethod
    def _get_reply_definition(data):
        delta = 0
        packet = None

        api = api_replies
        while api is not None:
            id = "%s" % byteToInt(data[delta])
            if id in api:
                packet = api[id]
                if 'submenu' in packet:
                    delta += 1
                    id = str(byteToInt(data[delta]))
                    api = packet['submenu']
                    packet = None
                else:
                    api = None
            else:
                api = None

        if packet is not None:
            if isinstance(packet, list):
                pkts = packet
                packet = None
                for pkt in pkts:
                    _size = DirectBase._size_of_reply(pkt)
                    if _size is None or _size == len(data)-delta-1:
                        packet = pkt
                        break

        return packet, delta

    @staticmethod
    def split_response(data):
        # print(binascii.hexlify(data))
        packet, delta = DirectBase._get_reply_definition(data)
        if packet is None:
            logging.error(f'Reply can\'t be decoded using api database {binascii.hexlify(data)}')
            raise NotImplementedError("API response specifications could not be found; use a derived class which defines 'api_replies'.")

        # Current byte index in the data socket_interface
        index = 1 + delta

        # Result info
        info = {'id':packet['id']}

        if packet['id'] == 'get':
            if len(data) == 11:
                packet = copy.deepcopy(packet)
                del packet['structure'][3]
                print(len(data), packet)
                info['rssi2'] = -1

        packet_spec = packet['structure']
        # Parse the packet in the order specified
        for field in packet_spec:
            if field['len'] is not None:
                # Store the number of bytes specified

                # Are we trying to read beyond the last data element?
                expected_len = index + field['len']
                if expected_len > len(data):
                    raise ValueError("Response packet was shorter than expected; expected: %d, got: %d bytes" % (expected_len, len(data)))

                field_data = data[index:index + field['len']]
                if 'decode' in field:
                    info[field['name']], = struct.unpack(field['decode'], field_data)
                else:
                    info[field['name']] = field_data

                index += field['len']
            # If the data field has no length specified, store any
            #  leftover bytes and quit
            else:
                field_data = data[index:]
                # Were there any remaining bytes?
                if field_data:
                    # If so, store them
                    info[field['name']] = field_data
                    index += len(field_data)
                else:
                    info[field['name']] = ''
                break

        # If there are more bytes than expected, raise an exception
        if index < len(data):
            print(packet, delta, data)
            raise ValueError("Response packet was longer than expected; expected: %d, got: %d bytes" % (index, len(data)))

        # Apply parsing rules if any exist
        if 'parsing' in packet:
            for parse_rule in packet['parsing']:
                # Only apply a rule if it is relevant (raw data is available)
                if parse_rule[0] in info:
                    # Apply the parse function to the indicated field and
                    # replace the raw data with the result
                    print('XXXXX Warning removed parsing')
                    # info[parse_rule[0]] = parse_rule[1](self, info)
        return info

    def _parse_samples_header(self, io_bytes):
        """
        _parse_samples_header: binary data in XBee IO data format ->
                        (int, [int ...], [int ...], int, int)

        _parse_samples_header will read the first three bytes of the
        binary data given and will return the number of samples which
        follow, a list of enabled digital inputs, a list of enabled
        analog inputs, the dio_mask, and the size of the header in bytes
        """
        header_size = 3

        # number of samples (always 1?) is the first byte
        sample_count = byteToInt(io_bytes[0])

        # part of byte 1 and byte 2 are the DIO mask ( 9 bits )
        dio_mask = (byteToInt(io_bytes[1]) << 8 | byteToInt(io_bytes[2])) & 0x01FF

        # upper 7 bits of byte 1 is the AIO mask
        aio_mask = (byteToInt(io_bytes[1]) & 0xFE) >> 1

        # sorted lists of enabled channels; value is position of bit in mask
        dio_chans = []
        aio_chans = []

        for i in range(0,9):
            if dio_mask & (1 << i):
                dio_chans.append(i)

        dio_chans.sort()

        for i in range(0,7):
            if aio_mask & (1 << i):
                aio_chans.append(i)

        aio_chans.sort()

        return sample_count, dio_chans, aio_chans, dio_mask, header_size

    def _parse_samples(self, io_bytes):
        """
        _parse_samples: binary data in XBee IO data format ->
                        [ {"dio-0":True,
                           "dio-1":False,
                           "adc-0":100"}, ...]

        _parse_samples reads binary data from an XBee device in the IO
        data format specified by the API. It will then return a
        dictionary indicating the status of each enabled IO port.
        """

        sample_count, dio_chans, aio_chans, dio_mask, header_size = self._parse_samples_header(io_bytes)
        samples = []

        # split the sample data into a list, so it can be pop()'d
        sample_bytes = [byteToInt(c) for c in io_bytes[header_size:]]

        # repeat for every sample provided
        for sample_ind in range(0, sample_count):
            tmp_samples = {}

            if dio_chans:
                # we have digital data
                digital_data_set = (sample_bytes.pop(0) << 8 | sample_bytes.pop(0))
                digital_values = dio_mask & digital_data_set

                for i in dio_chans:
                    tmp_samples['dio-{0}'.format(i)] = True if (digital_values >> i) & 1 else False

            for i in aio_chans:
                analog_sample = (sample_bytes.pop(0) << 8 | sample_bytes.pop(0))
                tmp_samples['adc-{0}'.format(i)] = analog_sample

            samples.append(tmp_samples)

        return samples

    def send(self, serial, cmd, **kwargs):
        binary = self.build_command(cmd, **kwargs)
        if serial == LOCAL_NODE_SERIAL:
            pass
        elif serial == BROADCAST_SERIAL:
            binary = self.build_command('broadcast', payload=binary)
        else:
            binary = self.build_command('unicast', target=serial, payload=binary)
        self._write(binary)

    def wait_read_frame(self):
        frame = self._wait_for_frame()
        return self.split_response(frame.data)
