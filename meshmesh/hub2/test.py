import argparse
import binascii
import datetime
import hashlib
import tempfile
import time
import xmlrpc.client
import progressbar
import networkx as nx
import os

import requests

from meshmesh.gui2.transport import RequestsTransport

# --firmware /home/stefano/Sviluppo/Stefano/Meshmesh/esphome/tests/testmesh2/.pioenvs/testmesh2/firmware.bins
# parameters
# --hub 127.0.0.1 --discovery 1
# --hub 127.0.0.1 --id 0x001c89ca --discovery 1 --discovery-entities 0x001c89ca
# --hub 127.0.0.1 --id 0x755BC9 --firmwarex /home/stefano/Sviluppo/Stefano/Meshmesh/esphome/tests/dallas/.pioenvs/dallas/firmware.bin

IP_SERVER = "127.0.0.1"
PORT_SERVER = 8801

ID_NODO_LOCALE = 0
MYID_NODO_LOCALE = 0
MYTAG_NODO_LOCALE = ''

SERVICE_BINARY = 2
SERVICE_SWITCH = 3
SERVICE_LIGHT = 4
services = ['All', 'Sensor', 'BinarySensor', 'Switch', 'Light']

DEVICE = xmlrpc.client.ServerProxy(f"http://{IP_SERVER}:{PORT_SERVER}/RPC2", transport=RequestsTransport())  # type: xmlrpc.client.ServerProxy

# 0.243..236.85
# ID_NODO = 0xF3EC55
# 0.209.70.249 - Lampada dali foglia
# ID_NODO = 0xD146F9
# 0.10.123.143
# ID_NODO = 0x0A7B8F
# 0.243.236.85 - Shelly 2.5
# ID_NODO= 0xF3EC55
# 0.117.91.237

ID_NODO = 0
GROUP_NODO = 0
ENTITY_HASH = None


def node_reboot(_id):
    global DEVICE
    print(f'node_reboot: reboot node "{_id}"')
    try:
        DEVICE.cmd_reboot(_id)
    except Exception as ex:
        print(str(ex))


def change_node_tag(tag, _id):
    global MYTAG_NODO_LOCALE
    print(f'change_node_tag: set tag as "{tag}" to node 0x{_id:08x}')
    try:
        MYTAG_NODO_LOCALE = DEVICE.cmd_node_tag(_id)
        print(f'change_node_tag: current node TAG is "{MYTAG_NODO_LOCALE}"')
    except Exception as ex:
        print(str(ex))
        return
    if MYTAG_NODO_LOCALE != tag:
        print(f'change_node_tag: changing NODE tag from "{MYTAG_NODO_LOCALE}" to "{tag}"')
        try:
            DEVICE.cmd_node_tag_set(tag, _id)
        except Exception as ex:
            print(str(ex))


def set_log_destination(dest, id):
    global MYTAG_NODO_LOCALE
    print(f'set_log_destination: log destination of node {id:06x} to node 0x{dest:06x}')
    try:
        olddest = DEVICE.cmd_log_destination(id)
        print(f'set_log_destination: current log destination is "{olddest:06x}"')
    except Exception:
        print('Comincation error!!!')
        return
    if olddest != dest:
        print(f'set_log_destination: changing log destination from "{olddest:08x}" to "{dest:08x}"')
        try:
            DEVICE.cmd_log_destination_set(dest, id)
        except Exception as ex:
            print(str(ex))


def set_filter_groups(dest, id):
    global MYTAG_NODO_LOCALE
    print(f'set_filter_groups: filter groups of node {id:06x} to node 0x{dest:06x}')
    try:
        olddest = DEVICE.cmd_filter_groups(id)
        print(f'set_filter_groups: current log destination is "{olddest:06x}"')
    except Exception:
        print('Comincation error!!!')
        return
    if olddest != dest:
        print(f'set_filter_groups: changing filter groups from "{olddest:08x}" to "{dest:08x}"')
        try:
            DEVICE.cmd_filter_groups_set(dest, id)
        except Exception as ex:
            print(str(ex))


def test_local_node():
    global MYID_NODO_LOCALE, MYTAG_NODO_LOCALE
    MYID_NODO_LOCALE = DEVICE.cmd_node_id(ID_NODO_LOCALE)
    print(f"Local node ID is 0x{MYID_NODO_LOCALE:08x}")
    #MYTAG_NODO_LOCALE = DEVICE.cmd_node_tag(ID_NODO_LOCALE)
    #print(f"Local node TAG is '{MYTAG_NODO_LOCALE}'")


def test_remote_node(_id):
    read_id = DEVICE.cmd_node_id(_id)
    print(f"Node ID is 0x{read_id:08x}")
    read_tag = DEVICE.cmd_node_tag(_id)
    print(f"Node TAG is '{read_tag}'")
    #read_groupsh, read_groupsl = DEVICE.cmd_filter_groups(_id)
    #print(f"Node flter groups are 'high:{read_groupsh:04x} low:{read_groupsl:04X}'")


DISCOVERY_NODE_SEEN = 'inuse'
DISCOVERY_DISCOVERED = 'discover'
DISCOVERY_BUGGY = 'buggy'
DISCOVERY_COST1 = 'weight'
DISCOVERY_COST2 = 'weight2'


def discovery_add_node(_g, _id, _tag):
    _g.add_node(_id, tag=_tag, inuse=False, discover=False, buggy=False)


def discovery_nodes(repeats, id_, empty=False):
    local_id = DEVICE.cmd_node_id(id_)
    if id_ == 0:
        id_ = DEVICE.cmd_node_id(id_)
    id_hex_ = "0x%06X" % id_

    def download_graph():
        resp = requests.get(f'http://{IP_SERVER}:{PORT_SERVER}/download_xml')
        _, resptemp = tempfile.mkstemp()
        print(resptemp)
        with open(resptemp, 'wb') as fp:
            fp.write(resp.content)
        _g = nx.readwrite.read_graphml(resptemp)
        os.unlink(resptemp)
        return _g

    def upload_graph(_g):
        _, resptemp = tempfile.mkstemp()
        nx.readwrite.write_graphml(_g, resptemp)
        with open(resptemp, 'rb') as f:
            requests.post(f'http://{IP_SERVER}:{PORT_SERVER}/upload_xml', files={'graph': f.read()})
        os.unlink(resptemp)

    if empty:
        graph = nx.Graph()
    else:
        graph = download_graph()
    if not graph.has_node(id_hex_):
        print(f'discovery_nodes added new coordinator node {id_hex_}')
        discovery_add_node(graph, id_hex_, 'Main')
        upload_graph(graph)

    for n in graph.nodes:
        graph.nodes[n][DISCOVERY_DISCOVERED] = False
        graph.nodes[n][DISCOVERY_NODE_SEEN] = False
        graph.nodes[n][DISCOVERY_BUGGY] = False
        for f, t in graph.edges(n):
            if DISCOVERY_COST2 not in graph[f][t]:
                graph[f][t][DISCOVERY_COST2] = graph[f][t][DISCOVERY_COST1]

    graph.nodes[id_hex_][DISCOVERY_NODE_SEEN] = True

    def find_next_node(graph_):
        _found_id = None
        _found_node = None
        _found_cost = 1e6
        for _node_id in graph_:
            _node = graph.nodes[_node_id]
            if _node[DISCOVERY_NODE_SEEN] and not _node[DISCOVERY_DISCOVERED]:
                _path = DEVICE.shortest_path(int(_node_id[2:], 16))
                if len(_path) > 1:
                    _from = f"0x{_path[-2]:06X}"
                    _cost = max(graph[_from][_node_id][DISCOVERY_COST1], graph[_from][_node_id][DISCOVERY_COST2])
                    if _cost < _found_cost:
                        _found_id = _node_id
                        _found_node = _node
                        _found_cost = _cost
                else:
                    _found_id = _node_id
                    _found_node = _node
                    _found_cost = 0
        return _found_id, _found_node

    __run__ = True
    while __run__:
        curr_node_hex, curr_node = find_next_node(graph)
        if curr_node is None:
            print('No more nodes to discover.')
            break

        curr_node_id = int(curr_node_hex[2:], 16)
        print(f'## Selected node {curr_node_hex}')

        try:
            tag = DEVICE.cmd_node_tag(curr_node_id if curr_node_id != local_id else 0)    # type: str
            firm = DEVICE.cmd_firmware_version(curr_node_id if curr_node_id != local_id else 0)   # type: str

            graph.nodes[curr_node_hex]['tag'] = tag
            graph.nodes[curr_node_hex]['firmware'] = firm
            graph.nodes[curr_node_hex][DISCOVERY_DISCOVERED] = True

            print(f"** ID=0x{curr_node_hex} FIRM:{firm} TAG=\"{tag}\"")
        except xmlrpc.client.Fault as ex:
            print(f'{curr_node_hex} communication error {str(ex)}')
            graph.nodes[curr_node_hex][DISCOVERY_DISCOVERED] = True
            graph.nodes[curr_node_hex][DISCOVERY_BUGGY] = True
            continue

        discovery_nodes2(repeats, curr_node_id, graph, local_id)
        nx.spring_layout(graph)
        upload_graph(graph)

    DEVICE.save_graph('***')
    nx.readwrite.write_graphml(graph, 'discovery.graphml')

def discovery_rssi_to_weight(_rssi):
    # type: (int) -> float
    if _rssi > 45:
        _rssi = 45
    if _rssi <= -1:
        _rssi = -_rssi * 2
    _weight = 1.0 - _rssi / 45.0
    return _weight if _weight > 0.05 else 0.05


def discovery_nodes2(repeats, id_, graph, local_id):
    # type: (int, int, nx.Graph, int) -> None
    id_hex = "0x%06X" % id_
    tnt = {}  # temporary neighbour table

    print('---------------------------------------------------')
    print("discovery_nodes target %06X" % id_)
    print('---------------------------------------------------')
    print('')
    print('|----------|-----|-----|')
    print('|  ID      | Rem | Loc |')
    print('|----------|-----|-----|')
    for f, t in graph.edges(id_hex):
        tnt[t] = {'last': None, 'next': (graph[f][t]["weight"], graph[f][t]["weight2"]), 'curr': None, 'orig': True}
        print(f'| {t} | {graph[f][t]["weight"]:1.1f} | {graph[f][t]["weight2"]:1.1f} |')
    print('|----------|-----|-----|')

    for _i in range(0, repeats):

        DEVICE.cmd_discovery_reset(id_ if id_ != local_id else 0)
        print('')
        print('Start discovery repetition %d' % _i)
        DEVICE.cmd_discovery_start(0, 0, 100, id_ if id_ != local_id else 0)
        time.sleep(3)
        size = DEVICE.cmd_discovery_count(id_ if id_ != local_id else 0)

        for k in tnt:
            tnt[k]['last'] = tnt[k]['next']
            tnt[k]['curr'] = None
            tnt[k]['next'] = None

        print("Discovery table size is %d" % size)
        for j in range(0, size):
            disc_ser, disc_rssi, disc_rssi2 = DEVICE.cmd_discovery_get(j, id_ if id_ != local_id else 0)
            disc_ser_hex = f"0x{disc_ser:06X}"

            if disc_ser_hex not in graph:
                discovery_add_node(graph, disc_ser_hex, '')
            else:
                graph.nodes[disc_ser_hex][DISCOVERY_NODE_SEEN] = True

            if disc_ser_hex not in tnt:
                tnt[disc_ser_hex] = {'last': None, 'next': None, 'curr': None, 'orig': False}
            tnt[disc_ser_hex]['curr'] = discovery_rssi_to_weight(disc_rssi), discovery_rssi_to_weight(disc_rssi2)
            tnt[disc_ser_hex]['next'] = tnt[disc_ser_hex]['curr'] \
                if tnt[disc_ser_hex]['last'] is None \
                else ((tnt[disc_ser_hex]['last'][0] + tnt[disc_ser_hex]['curr'][0]) / 2, (tnt[disc_ser_hex]['last'][1] +
                                                                                          tnt[disc_ser_hex]['curr'][1]) / 2)

        print('')
        print(f'|----------|---|------------|------------|------------|--------------|')
        print(f'| ID       | O | Last w.    | Curr w.    | Next w.    | Delta w.     |')
        print(f'|----------|---|------------|------------|------------|--------------|')

        for k in tnt:
            if tnt[k]['curr'] is None:
                tnt[k]['next'] = tnt[k]['last'][0] * 1.1, tnt[k]['last'][1] * 1.1
            kr = tnt[k]

            kw1 = kr['last']
            kw2 = kr['curr']
            kw3 = kr['next']
            kor = '*' if kr['orig'] else ' '

            if kw1 is None:
                print(f'| {k} | {kor} | ----, ---- | {kw2[0]:1.2f}, {kw2[1]:1.2f} | {kw3[0]:1.2f}, {kw3[1]:1.2f} | -----, ----- |')
            elif kw2 is None:
                print(f'| {k} | {kor} | {kw1[0]:1.2f}, {kw1[1]:1.2f} | ----, ---- | {kw3[0]:1.2f}, {kw3[1]:1.2f} | {kw3[0]:+1.2f}, {kw3[1]:+1.2f} |')
            else:
                print(f'| {k} | {kor} | {kw1[0]:1.2f}, {kw1[1]:1.2f} | {kw2[0]:1.2f}, {kw2[1]:1.2f} | {kw3[0]:1.2f}, {kw3[1]:1.2f} | '
                      f'{kw3[0]-kw1[0]:+1.2f}, {kw3[1]-kw1[1]:+1.2f} |')

        print(f'|----------|---|------------|------------|------------|--------------|')

    for k in tnt:
        if not tnt[k]['orig']:
            graph.add_edge(id_hex, k)
        if tnt[k]['next'][0] > 1 or tnt[k]['next'][1] > 1:
            graph.remove_edge(id_hex, k)
        else:
            graph[id_hex][k]['weight'] = tnt[k]['next'][0]
            graph[id_hex][k]['weight2'] = tnt[k]['next'][1]


def set_group_entity_state(_hash, _value, _group):
    _value = DEVICE.brd_service_set_entity_state(SERVICE_SWITCH, _hash, 1 if _value is True else 0, _group)


def set_entity_state(_hash, _value, _id):
    _value = DEVICE.cmd_service_set_entity_state(SERVICE_SWITCH, _hash, 1 if _value is True else 0, _id)


def test_entities_for_node(_id):
    _services = ['All', 'Sensor', 'BinarySensor', 'Switch', 'Light']
    _entities = DEVICE.cmd_service_get_entities(_id)
    if len(_entities) != len(_services):
        _services = ['All', 'Sensor', 'BinarySensor', 'Switch', 'Light', 'Texts']
    print(f"Found {_entities[0]} entities on node ID is 0x{_id:08x}")
    for _i in range(1, len(_services)):
        if _entities[_i] > 0:
            print(f"  Found {_entities[_i]} {_services[_i]}")
    print("--------------------------------------------")

    if len(_entities) and _entities[0] > 0:
        print(f'Requesting hash for {_entities[0]} entities in node: 0x{_id:08x}')

        _discovery = []
        for _i in range(1, len(_entities)):
            for j in range(0, _entities[_i]):
                _hash, info = DEVICE.cmd_service_get_entity_info(_i, j, _id)
                _discovery.append((_services[_i], j, _hash, info))
                time.sleep(0.1)
        print(f'Request hash done......')
        return _discovery
    return []


def test_entitites_reading(_entities, _id):
    _services = ['All', 'Sensor', 'BinarySensor', 'Switch', 'Light']
    if len(_entities) != len(_services):
        _services = ['All', 'Sensor', 'BinarySensor', 'Switch', 'Light', 'Texts']

    print("")
    print("--------------|--|----|-------|---------------------------")
    print("Type          |nm|hash|  value| info")
    print("--------------|--|----|-------|---------------------------")
    if _entities is None:
        _entities = test_entities_for_node(_id)
    for service, index, hash, info in _entities:
        value = 0
        try:
            value = DEVICE.cmd_service_get_entity_state(_services.index(service), hash, _id)
        except Exception as ex:
            value = 0
            print(str(ex))
        if isinstance(value, str):
            print(f"{service:14}|{index:2}|{hash:04x}|{value}|{info}")
        else:
            print(f"{service:14}|{index:2}|{hash:04x}|{value / 10.0:7.1f}|{info}")


def test_switches(entities, id):
    for service, index, hash, info in entities:
        if service == 'Switch':
            #try:
            #    value = DEVICE.cmd_service_set_entity_state(3, hash, 0, id)
            #except Exception as ex:
            #    print(str(ex))
            #time.sleep(1)
            try:
                value = DEVICE.cmd_service_set_entity_state(3, hash, 1, id)
            except Exception as ex:
                print(str(ex))


def test_dali_lights(entities, id):
    print(entities)
    for service, index, hash, info in entities:
        if service == 'Light':
            for i in [256, 512, 728, 512, 0]:
                try:
                    value = DEVICE.cmd_service_set_entity_state(4, hash, i, id)
                    print('dimming %d,%d' % (hash,i))
                    #value = DEVICE.cmd_custom_dali_set_power(i, id)
                except Exception as ex:
                    print(str(ex))
                time.sleep(1.5)


def rssi_check(target, id, duration=60):
    start_time = time.time()
    last_time = start_time
    while True:
        now = time.time()
        if now - start_time > duration:
            break
        elif now - last_time > 1.5:
            remote, local = DEVICE.cmd_rssicheck_start(target, id)
            last_time = now
            print(remote, local)
        else:
            time.sleep(0.1)


#def test_dali_bank(id):
#    for register in REGISTERS:
#        reply = DEVICE.cmd_custom_dali_query(register['bank'], register['offset'], register['size'], id)
#        print(reply)


def get_md5_timeout(address, size, id):
    tout = 0
    while True:
        try:
            erased, md5 = DEVICE.cmd_spiflash_getmd5(address, size, id)
            return erased, md5
        except Exception as ex:
            tout += 1
            print('timout %d')
            if tout > 5:
                raise ex


def spiflash_erase_timeout(address, size, id):
    tout = 0
    while True:
        try:
            res = DEVICE.cmd_spiflash_erase(address, size, id)
            return res
        except Exception as ex:
            tout += 1
            print('timout %d')
            if tout > 5:
                raise ex


def spiflash_write_timeout(address, chunk, id):
    tout = 0
    while True:
        try:
            error = DEVICE.cmd_spiflash_write(address, chunk, id)
            return error
        except Exception as ex:
            tout += 1
            print('timout %d')
            if tout > 5:
                raise ex


def test_send_update(firmware_path, id):
    global DEVICE

    if not os.path.exists(firmware_path) or not os.path.isfile(firmware_path):
        print(f"{firmware_path} not exists or is not readable")
        return

    node_firmware = DEVICE.cmd_firmware_version(id)
    node_firmware_time = datetime.datetime.strptime(node_firmware, "%b %d %Y, %H:%M:%S")

    if node_firmware_time.date() < datetime.date(2020, 7, 12):
        print('Firmware node is too old!!! %s' % node_firmware)
        return

    with open(firmware_path, 'rb') as file_handle:
        baseanme = os.path.basename(firmware_path)
        statinfo = os.stat(firmware_path)
        file_md5 = hashlib.md5(file_handle.read()).hexdigest()
        print(f'Uploading {statinfo.st_size} bytes from {baseanme} to {id:08X}')
        file_handle.seek(0)

        bar = progressbar.ProgressBar(maxval=statinfo.st_size)
        bar.start()

        START_ADDRESS = 0x80000
        address = START_ADDRESS
        no_error = True
        new_sector = True
        sector = None

        while no_error:
            if new_sector:
                sector = file_handle.read(4096)
            new_sector = True

            if not sector:
                break
            m = hashlib.md5()
            m.update(sector)

            erased, md5 = get_md5_timeout(address, len(sector), id)
            #erased, md5 = DEVICE.cmd_spiflash_getmd5(address, len(sector), id)
            if md5 == binascii.hexlify(m.digest()).decode():
                address += len(sector)
                bar.update(address - 0x80000)
                continue

            if erased == 0:
                res = spiflash_erase_timeout(address, 4096, id)
                #res = DEVICE.cmd_spiflash_erase(address, 4096, id)
            else:
                if md5 != '6ae59e64850377ee5470c854761551ea':
                    print('memory erased but md5 is ', md5)

            CHUNK_SIZE = 1024
            if md5 != binascii.hexlify(m.digest()):
                sector_steps = int((len(sector) - 1) / CHUNK_SIZE) + 1
                for i in range(0, sector_steps):
                    chunk = sector[CHUNK_SIZE * i:CHUNK_SIZE * (i + 1)]
                    error = spiflash_write_timeout(address, chunk, id)
                    address += len(chunk)
                    bar.update(address - 0x80000)
                    if error:
                        no_error = False
                        break

            erased, md5 = get_md5_timeout(address-len(sector), len(sector), id)
            #erased, md5 = DEVICE.cmd_spiflash_getmd5(address, len(sector), id)
            if md5 != binascii.hexlify(m.digest()).decode():
                print('Errrrrrrrrr')
                address -= len(sector)
                bar.update(address - 0x80000)
                new_sector = False

        bar.finish()
        if no_error:
            erased, md5 = get_md5_timeout(START_ADDRESS, statinfo.st_size, id)
            if md5 == file_md5:
                print('It\'s all ok rebbooting device!!!')
                DEVICE.cmd_spiflash_eboot(START_ADDRESS, statinfo.st_size, id)
                DEVICE.cmd_reboot(id)
            else:
                print(md5, file_md5)


def test_send_update2(firmware_path, id):
    global DEVICE

    if not os.path.exists(firmware_path) or not os.path.isfile(firmware_path):
        print(f"{firmware_path} not exists or is not readable")
        return

    node_firmware = DEVICE.cmd_firmware_version(id)
    node_firmware_time = datetime.datetime.strptime(node_firmware, "%b %d %Y, %H:%M:%S")

    version = 0
    if node_firmware_time.date() > datetime.date(2020, 3, 9):
        version = 1

    with open(firmware_path, 'rb') as file_handle:
        baseanme = os.path.basename(firmware_path)
        statinfo = os.stat(firmware_path)
        file_md5 = hashlib.md5(file_handle.read()).hexdigest()
        print(f'Uploading {statinfo.st_size} bytes from {baseanme} to {id:08X}')
        file_handle.seek(0)

        bar = progressbar.ProgressBar(max_value=statinfo.st_size)

        error, remaining, progress, bufferlen = DEVICE.cmd_update_chunk(b'', id)
        already_sent = progress + bufferlen
        if already_sent > 0:
            print('Update already start please reboot device!!!!')
            return

        error = DEVICE.cmd_update_start(statinfo.st_size, file_md5, id)
        if error == 0:
            offset = 0
            while error == 0:
                print("tell %d" % file_handle.tell())
                sector = file_handle.read(4096)
                if not sector:
                    break
                time.sleep(0.1)
                if version > 0:
                    m = hashlib.md5()
                    m.update(sector)

                    isdone = False
                    retry = 6
                    progress = 0
                    bufferlen = 0
                    res = 0
                    while not isdone and retry > 0:
                        try:
                            res, remaining, progress, bufferlen = DEVICE.cmd_update_memmd5(len(sector), m.digest(), id)
                            print(error, progress)
                            isdone = True
                        except Exception as ex:
                            retry -= 1
                            time.sleep(1)
                    if not isdone and retry == 0:
                        print("Too many timeouts giving up!!!!")
                        error = 1
                        break

                    bar.update(progress + bufferlen)
                    if res == 1:
                        continue
                sector_steps = int((len(sector)-1)/1024)+1
                for i in range(0, sector_steps):
                    chunk = sector[1024*i:1024*(i+1)]
                    offset += len(chunk)

                    isdone = False
                    retry = 6
                    progress = 0
                    bufferlen = 0
                    res = 0

                    while not isdone and retry > 0:
                        try:
                            error, remaining, progress, bufferlen = DEVICE.cmd_update_chunk(chunk, id)
                            print(error, progress)
                            isdone = True
                        except Exception as ex:
                            retry -= 1
                            time.sleep(1)

                    if not isdone and retry == 0:
                        print("Too many timeouts giving up!!!!")
                        error = 1
                        break

                    bar.update(progress+bufferlen)
                    if error != 0:
                        break

            if error == 0:
                print('File sent try to finalize update')
                error = DEVICE.cmd_update_digest(0, id)
                if error == 0:
                    print('Update finalized try to reboot device')
                    DEVICE.cmd_reboot(id)


def auto_int(x):
    return int(x, 0)


def auto_bool(v):
    if isinstance(v, bool):
       return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def main():
    global ID_NODO, ID_NODO_LOCALE, GROUP_NODO, PORT_SERVER, IP_SERVER, ENTITY_HASH, DEVICE
    parser = argparse.ArgumentParser(description='Test Meshmesh protocol')
    parser.add_argument('--hub', dest='hub', default='127.0.0.1', type=str, help='IP address of the hub2 server')
    parser.add_argument('--port', dest='port', default=8801, type=int, help='port address of the hub2 server')
    parser.add_argument('--id', dest='id', default=0, type=auto_int, help='node id')
    parser.add_argument('--group', dest='group', default=0, type=auto_int, help='node group')
    parser.add_argument('--test-repeats', dest='test_repeats', default=1, type=auto_int, help='repeat tests N times')
    parser.add_argument('--hash', dest='hash', default=0, type=auto_int, help='entity hash')
    parser.add_argument('--firmware', dest='firmware', default=None, help='firmware file tu upload to node')
    parser.add_argument('--node-tag', dest='node_tag', default=None, help='set the tag of node')
    parser.add_argument('--log-destination', dest='log_destination', default=-1, type=auto_int, help='set the log destination of node')
    parser.add_argument('--node-reboot', dest='node_reboot', default=None, type=auto_int, help='reboot node')
    parser.add_argument('--discovery', dest='discovery', default=0, type=auto_int, help='discovery nodes around')
    parser.add_argument('--discovery-entities', dest='discovery_entities', default=False, action='store_true', help='look for entitie')
    parser.add_argument('--read-entities', dest='read_entities', default=None, type=auto_int, help='Read entities')
    parser.add_argument('--set-entity-state', dest='set_entity_state', default=None, type=auto_int, help='Set entity state')
    parser.add_argument('--set-entity-prefs', dest='set_entity_prefs', default=None, type=auto_int, help='Set entity preferences')
    parser.add_argument('--test-switches', dest='test_switches', default=False, type=bool, help='test switches')
    parser.add_argument('--test-dali', dest='test_dali', default=False, type=bool, help='test DALI lights')
    parser.add_argument('--rssi-check', dest='rssi_check', default=None, type=auto_int, help='RSSI test procedure')
    parser.add_argument('--rssi-check-duration', dest='rssi_check_duration', default=60, type=auto_int, help='RSSI test procedure duration')
    parser.add_argument('--set-switch-state', dest='set_switch_state', default=None, type=auto_bool, help='set switch state')
    parser.add_argument('--filter-groups', dest='filter_groups', default=False, action='store_true', help='get filter groups')
    parser.add_argument('--filter-groups-set', dest='filter_groups_set', default=None, type=auto_int, help='get filter groups')
    parser.add_argument('--bind-clear', dest='bind_clear', default=False, action='store_true', help='reset binded coordinator of node')

    args = parser.parse_args()
    if args.id:
        ID_NODO = args.id
    if args.group:
        GROUP_NODO = args.group
    if args.hash:
        ENTITY_HASH = args.hash
    if args.hub:
        IP_SERVER = args.hub
    if args.port:
        PORT_SERVER = args.port

    DEVICE = xmlrpc.client.ServerProxy(f"http://{IP_SERVER}:{PORT_SERVER}/RPC2", transport=RequestsTransport())
    print(DEVICE)

    time.sleep(0.2)
    test_local_node()
    entities = test_entities_for_node(0)

    if ID_NODO > 0:
        time.sleep(0.2)
        test_remote_node(ID_NODO)

    if args.node_tag:
        change_node_tag(args.node_tag, ID_NODO)
    if args.log_destination >= 0:
        set_log_destination(args.log_destination, ID_NODO)
    if args.filter_groups:
        grouph, groupl = DEVICE.cmd_filter_groups(ID_NODO)
    #if args.filter_groups_set is not None and args.filter_groups_set >= 0:
    #    set_filter_groups(args.filter_groups_set, ID_NODO)
    if args.filter_groups_set:
        grouph = (int(args.filter_groups_set) & 0xFFFF0000) >> 16
        groupl = (int(args.filter_groups_set) & 0xFFFF)
        try:
            print(grouph, groupl)
            DEVICE.cmd_filter_groups_set(grouph, groupl, ID_NODO)
        except Exception as ex:
            print(str(ex))

    #if entities is not None:
        #test_entitites_reading(entities, ID_NODO)
        #for i in range(1,100):
            #test_entitites_reading(entities, ID_NODO)
            #time.sleep(1)

    if args.node_reboot is not None:
        node_reboot(args.node_reboot)
    if args.firmware is not None:
        test_send_update(args.firmware, ID_NODO)
    if args.discovery > 0:
        discovery_nodes(args.discovery, ID_NODO, True)

    entities = None
    for i in range(0, args.test_repeats):
        if args.read_entities is not None:
            entities = test_entities_for_node(args.read_entities)
            #test_dali_lights(e, args.read_entities)
            #time.sleep(2)
            test_entitites_reading(entities, args.read_entities)

        if args.set_entity_state is not None:
            if ENTITY_HASH is None:
                print("Fatal: Hash is required for this operation.")
            else:
                if GROUP_NODO > 0:
                    _value = DEVICE.brd_service_set_entity_state(SERVICE_LIGHT, ENTITY_HASH, args.set_entity_state, GROUP_NODO)
                else:
                    _value = DEVICE.cmd_service_set_entity_state(SERVICE_LIGHT, ENTITY_HASH, args.set_entity_state, ID_NODO)

        if args.set_entity_prefs is not None:
            if ENTITY_HASH is None:
                print("Fatal: Hash is required for this operation.")
            else:
                _value = DEVICE.cmd_service_get_entity_preferences_num(SERVICE_BINARY, ENTITY_HASH, ID_NODO)
                print('Set preference 1/%d' % _value)
                _value = DEVICE.cmd_service_get_entity_preferences(SERVICE_BINARY, ENTITY_HASH, 1, ID_NODO)
                print('Old preference is %d' % _value)
                DEVICE.cmd_service_set_entity_preferences(SERVICE_BINARY, ENTITY_HASH, 1, args.set_entity_prefs, ID_NODO)
                _value = DEVICE.cmd_service_get_entity_preferences(SERVICE_BINARY, ENTITY_HASH, 1, ID_NODO)
                print('New preference is %d' % _value)

        if args.set_switch_state is not None:
            if ID_NODO > 0:
                set_entity_state(ENTITY_HASH, args.set_switch_state, ID_NODO)
            if GROUP_NODO > 0:
                set_group_entity_state(ENTITY_HASH, args.set_switch_state, GROUP_NODO)

        if args.test_switches:
            if entities is not None:
                test_switches(entities, ID_NODO)
            else:
                print('To test switches must disocer entities first')

        if args.test_dali:
            if entities is not None:
                test_dali_lights(entities, ID_NODO)
            else:
                print('To test dali must disocer entities first')

        if args.rssi_check is not None:
            rssi_check(args.rssi_check, ID_NODO)

        if args.bind_clear:
            if ID_NODE > 0:
                DEVICE.cmd_bind_clear(ID_NODO)


if __name__ == "__main__":
    main()
