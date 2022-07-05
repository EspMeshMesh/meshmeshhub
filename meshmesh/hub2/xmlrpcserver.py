import asyncio
import binascii
import logging
import os
import tempfile
from typing import List

from aiohttp_xmlrpc import handler
from aiohttp.web import Application, AppRunner, TCPSite, Request, Response
from asyncio import AbstractEventLoop, wait_for, TimeoutError, sleep

from .direct import DirectBase
from .frame import APIFrame

from .serialprotocol import SerialProtocol
from .connectedpath import ConnectedPathProtocol
from .network import GraphNetwork

globalProtocol = 'unicast'


def set_global_protocol(value):
    # type: (str) -> None
    global globalProtocol

    if value in ['unicast', 'beacons', 'multipath', 'polite', 'connpath']:
        globalProtocol = value
    else:
        logging.error('Invalid protocol requested')


class XMLRPCHub(handler.XMLRPCView):
    def __init__(self, request):
        super(XMLRPCHub, self).__init__(request)
        self._timeout = 3.0  # type: float

    def _flush_rx_queue(self, serprot):
        while not serprot.rx_frames.empty():
            print('Flush queue')
            try:
                serprot.rx_frames.get_nowait()
            except asyncio.QueueEmpty:
                pass

    async def _rpc_standard_req(self, buffer, serial, protocol):
        # type: (bytes, int, str) -> bytes
        serprot = SerialProtocol.get()  # type: SerialProtocol
        if serial == 0:
            frame = APIFrame(buffer, escaped=True)
        elif protocol == 'unicast':
            buffer = DirectBase.build_command('unicast', target=serial, payload=buffer)
            frame = APIFrame(buffer, escaped=True)
        elif GraphNetwork.instance().is_network_loaded():
            path = GraphNetwork.instance().shortest_path(serial)
            if len(path) == 0:
                pass
            elif len(path) == 1:
                buffer = DirectBase.build_command('unicast', target=serial, payload=buffer)
            else:
                path = path[0:-1]
                buffer = DirectBase.build_command('multipath', target=serial, pathlen=len(path), path=path,
                                                  payload=buffer)
            frame = APIFrame(buffer, escaped=True)
        else:
            buffer = DirectBase.build_command('unicast', target=serial, payload=buffer)
            frame = APIFrame(buffer, escaped=True)

        while not serprot.rx_frames.empty():
            print('Flush queue')
            try:
                serprot.rx_frames.get_nowait()
            except asyncio.QueueEmpty:
                pass

        async with serprot.lock:
            serprot.send_api_frame(frame)

        timeout_ex = None
        buffer = None
        try:
            buffer = await wait_for(serprot.rx_frames.get(), timeout=self._timeout)
        except TimeoutError as ex:
            timeout_ex = ex
        if timeout_ex is not None:
            logging.error(f"Timeout error while waiting for reply from node {serial:08x}")
            raise Exception('Timeout error while waiting for reply')

        return buffer

    @staticmethod
    async def _rpc_connpath_req(buffer, serial):
        # type: (bytes, int) -> bytes
        connpath = ConnectedPathProtocol.get()
        return await connpath.send_and_receive_data(buffer, serial)

    async def _rpc_request(self, serial, reply, cmd, **cmdkwargs):
        global globalProtocol

        commands = cmd.split('/')
        in_buffer = DirectBase.build_command(cmd, **cmdkwargs)

        if isinstance(serial, str):
            serial = int(serial, 16)

        if serial > 0 and globalProtocol == 'connpath':
            buffer = await XMLRPCHub._rpc_connpath_req(in_buffer, serial)
        else:
            buffer = await self._rpc_standard_req(in_buffer, serial, globalProtocol)

        frame = DirectBase.split_response(buffer)
        if frame['id'] != commands[-1]:
            if frame['id'] == 'error':
                logging.error(f"Reply Error from node {serial:08x} data is {binascii.hexlify(frame['data'])}")
                raise Exception('Error request %s' % binascii.hexlify(frame['data']))
            else:
                print(frame['id'], commands[-1])
                logging.error(f"Reply mismateched from node {serial:08x}")
                raise Exception('Malformed meshmesh packet %s' % binascii.hexlify(buffer))
        else:
            if globalProtocol == 'polite':
                await sleep(0.5)
            if reply is None:
                return True
            if isinstance(reply, str):
                if reply not in frame:
                    raise Exception(f'Invalid reply received {reply} not found')
                return frame[reply]
            elif isinstance(reply, tuple):
                result = []
                replies = list(reply)
                for reply in replies:
                    optional = False
                    if reply[0] == '*':
                        reply = reply[1:]
                        optional = True
                    if reply not in frame:
                        if not optional:
                            raise Exception('Invalid reply received')
                    else:
                        result.append(frame[reply])
                return tuple(result)

        return frame[reply]

    async def _rpc_polite_broadcast_rquest(self, group, cmd, **cmdkwargs):
        global globalProtocol
        serprot = SerialProtocol.get()  # type: SerialProtocol
        in_buffer = DirectBase.build_command(cmd, **cmdkwargs)
        in_buffer = DirectBase.build_command('filter', target=group, payload=in_buffer)
        in_buffer = DirectBase.build_command('polite', target=0xFFFFFFFF, payload=in_buffer)
        print(binascii.hexlify(in_buffer))
        frame = APIFrame(in_buffer, escaped=True)
        self._flush_rx_queue(serprot)
        async with serprot.lock:
            serprot.send_api_frame(frame)

    @staticmethod
    def rpc_load_graph(filename):
        # type: (str) -> None
        if os.path.exists(filename):
            GraphNetwork.instance().load_network(filename)

    @staticmethod
    def rpc_save_graph(filename):
        # type: (str) -> None
        GraphNetwork.instance().save_network(filename, True)

    @staticmethod
    def rpc_shortest_path(serial):
        # type: (int) -> List[int]
        return GraphNetwork.instance().shortest_path(serial, full_path=True)

    async def rpc_cmd_node_id(self, serial):
        # type: (int) -> int
        return await self._rpc_request(serial, 'serial', 'nodeId')

    async def rpc_cmd_node_tag(self, serial: int) -> str:
        tag = await self._rpc_request(serial, 'tag', 'nodetag')
        tag = tag[0:tag.find(b'\x00')]
        tag = tag.decode('ascii')
        return tag

    async def rpc_cmd_node_tag_set(self, tag: str, serial: int) -> str:
        tag = tag.encode('ascii', 'ignore')
        return await self._rpc_request(serial, None, 'nodetagSet', tag=tag)

    async def rpc_cmd_update_start(self, size, md5, serial):
        # type: (int, str, int) -> int
        __md5__ = md5.encode() + b'\0'
        return await self._rpc_request(serial, 'error', 'updateStart', size=size, md5=__md5__)

    async def rpc_cmd_update_chunk(self, chunk, serial):
        # type: (bytes, int) -> int
        return await self._rpc_request(serial, ('error', 'remaining', 'progress', 'bufferlen'), 'updateChunk',
                                       chunk=chunk)

    async def rpc_cmd_update_digest(self, options, serial):
        # type: (bytes, int) -> int
        return await self._rpc_request(serial, 'error', 'updateDigest', options=options)

    async def rpc_cmd_update_memmd5(self, size, md5, serial):
        # type: (int, bytes, int) -> int
        return await self._rpc_request(serial, ('result', 'remaining', 'progress', 'bufferlen'), 'updateMemMD5',
                                       size=size, md5=md5)

    async def rpc_cmd_log_destination(self, serial):
        # type: (int) -> int
        return await self._rpc_request(serial, 'serial', 'logDestination')

    async def rpc_cmd_log_destination_set(self, target, serial):
        # type: (int, int) -> bool
        return await self._rpc_request(serial, None, 'setLogDestination', target=target)

    async def rpc_cmd_filter_groups(self, serial):
        # type: (int) -> (int, int)
        groups = await self._rpc_request(serial, 'serial', 'filterGroups')
        return int((groups & 0xFFFF0000) >> 16), int(groups & 0xFFFF)

    async def rpc_cmd_filter_groups_set(self, groupsh, groupl, serial):
        # type: (int, int, int) -> bool
        groups = (int(groupsh) << 16) + int(groupl)
        return await self._rpc_request(serial, None, 'setFilterGroups', target=groups)

    async def rpc_cmd_firmware_version(self, serial: int) -> str:
        revision = await self._rpc_request(serial, 'revision', 'firm')
        return revision.rstrip(b'\r\n\0')

    async def rpc_cmd_flash_read(self, address, size, serial):
        if address == 0x7D000 and size == 16:
            return await self.rpc_cmd_node_tag(serial)
        else:
            return "Flash read undefined"

    async def rpc_cmd_reboot(self, serial):
        return await self._rpc_request(serial, None, 'reboot')

    async def rpc_cmd_discovery_reset(self, serial):
        return await self._rpc_request(serial, None, 'discovery/reset')

    async def rpc_cmd_discovery_start(self, mask, filter_, slots, serial):
        return await self._rpc_request(serial, None, 'discovery/start', mask=mask, filter=filter_, slots=slots)

    async def rpc_cmd_discovery_count(self, serial):
        return await self._rpc_request(serial, 'size', 'discovery/count')

    async def rpc_cmd_discovery_get(self, index, serial):
        index, serial, rssi1, rssi2, flags = await self._rpc_request(serial, ('index', 'serial', 'rssi1', 'rssi2',
                                                                              'flags'), 'discovery/get', index=index)
        return serial, rssi1, (rssi2 if rssi2 >= 0 else rssi1)

    async def rpc_cmd_rssicheck_start(self, target, serial):
        remote, local = await self._rpc_request(serial, ('remote', 'local'), 'rssicheck/startcheck', target=target)
        return remote, local

    async def rpc_cmd_spiflash_getmd5(self, address, length, serial):
        erased, md5 = await self._rpc_request(serial, ('erased', 'md5'), 'spiflash/getmd5', address=address,
                                              length=length)
        return erased[0], binascii.hexlify(md5)

    async def rpc_cmd_spiflash_erase(self, address, length, serial):
        result = await self._rpc_request(serial, 'result', 'spiflash/erase', address=address, length=length)
        return result

    async def rpc_cmd_spiflash_write(self, address, payload, serial):
        error = await self._rpc_request(serial, 'error', 'spiflash/write', address=address, payload=payload)
        return error

    async def rpc_cmd_spiflash_eboot(self, address, length, serial):
        return await self._rpc_request(serial, None, 'spiflash/eboot', address=address, length=length)

    async def rpc_cmd_clima_set_ac_state(self, mode, temp, fan, vane, serial):
        return await self._rpc_request(serial, 'res', 'climaGrp/setstate', mode=mode, temp=temp, fan=fan, vame=vane)

    async def rpc_cmd_custom_presence_get(self, serial):
        return await self._rpc_request(serial, 'presence', 'customGrp/presenceGrp/get')

    async def rpc_cmd_digital_in(self, mask, serial):
        return await self._rpc_request(serial, ('mask', 'value'), 'digitalIn', mask=mask)

    async def rpc_cmd_custom_thermo_sample(self, num, serial):
        return await self._rpc_request(serial, ('num', 'temp'), 'customGrp/thermoGrp/sample', num=num)

    async def rpc_cmd_service_get_entities(self, serial):
        return await self._rpc_request(serial, ('all', 'sensors', 'binaries', 'switches', 'lights', '*texts'),
                                       'serviceEntitiesCount')

    async def rpc_cmd_service_get_entity_info(self, service, index, serial):
        return await self._rpc_request(serial, ('hash', 'info'), 'serviceEntityHash', service=service, index=index)

    async def rpc_cmd_service_get_entity_state(self, type_, hash_, serial):
        return await self._rpc_request(serial, 'value', 'serviceEntityState', type=type_, hash=hash_)

    async def rpc_cmd_service_set_entity_state(self, type_, hash_, value, serial):
        return await self._rpc_request(serial, None, 'serviceEntityStateSet', type=type_, hash=hash_, value=value)

    async def rpc_cmd_service_set_entity_preferences(self, type_, hash_, num_, value, serial):
        return await self._rpc_request(serial, None, 'entities/setprefvalue', type=type_, hash=hash_, num=num_,
                                       value=value)

    async def rpc_cmd_service_get_entity_preferences(self, type_, hash_, num_, serial):
        """

        :param type_:
        :param hash_:
        :param num_:
        :param serial:
        :return:
        """
        return await self._rpc_request(serial, 'value', 'entities/getprefvalue', type=type_, hash=hash_, num=num_)

    async def rpc_cmd_service_get_entity_preferences_num(self, type_, hash_, serial):
        """
        Get the maximum number of preferences that can be set in the selected entity.
        :param type_: Type of service (Binary, ecc.)
        :param hash_: Unique ID of service inside the selected entity
        :param serial: Unique ID of entity (serial number)
        :return: The number of preferences that can be set in the selected entity
        """
        return await self._rpc_request(serial, 'value', 'entities/countpref', type=type_, hash=hash_)

    async def rpc_brd_service_set_entity_state(self, type_, hash_, valueoup):
        group = 0xFF000000 | group
        print(hash_, group)
        return await self._rpc_polite_broadcast_rquest(group, 'serviceEntityStateSet', type=type_, hash=hash_, value=value)

    def rpc_exception(self):
        raise Exception("YEEEEEE!!!")


async def upload_xml(request):
    # type: (Request) -> Response
    response = 'KO'
    post = await request.post()
    graph = post.get("graph")
    if graph:
        fp = tempfile.NamedTemporaryFile()
        fp.write(graph.file.read())
        fp.flush()
        GraphNetwork.instance().load_network(fp.name, is_temporary=True)
        fp.close()
        response = 'OK'
    return Response(text=response)


async def download_xml(request):
    # type: (Request) -> Response
    _, filename = tempfile.mkstemp()
    GraphNetwork.instance().save_network(filename)
    with open(filename, 'r') as fp:
        body = fp.read()
    print(filename, body)
    os.unlink(filename)
    return Response(body=body, content_type='application/xml')


def xmlrpcserver_setup(loop: AbstractEventLoop, protocol: str, port: int):
    global globalProtocol

    if protocol:
        set_global_protocol(protocol)

    app = Application()
    app.router.add_route('*', '/RPC2', XMLRPCHub)
    app.router.add_route('POST', '/upload_xml', upload_xml)
    app.router.add_route('GET', '/download_xml', download_xml)
    runner = AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = TCPSite(runner, host='0.0.0.0', port=port)
    loop.run_until_complete(site.start())

