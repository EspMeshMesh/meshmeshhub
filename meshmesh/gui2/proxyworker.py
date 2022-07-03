import binascii
import hashlib
import os
import time
import datetime
import traceback
import tempfile
import xmlrpc.client
from typing import List, Any, Optional

import networkx as nx
import requests
from PySide2.QtCore import Slot, QAbstractTableModel, QObject, QModelIndex, Qt, Signal, QThread, QAbstractItemModel

from .devicemodel import DevicesTableModel, DeviceItem


def discovery_rssi_to_weight(_rssi):
    # type: (int) -> float
    if _rssi > 45:
        _rssi = 45
    if _rssi <= 0:
        _rssi = 0
    _weight = 1.0 - _rssi / 45.0
    return _weight if _weight > 0.05 else 0.05


class EntityItem:
    services = ['All', 'Sensor', 'BinarySensor', 'Switch', 'Light']

    def __init__(self, service, index):
        self._service = service
        self._index = index
        self._hash = 0
        self._info = 0
        self._state = 0

    @property
    def service(self):
        return self._service

    @property
    def service_name(self):
        return EntityItem.services[self._service]

    @property
    def index(self):
        return self._index

    @property
    def hash(self):
        return self._hash

    @hash.setter
    def hash(self, value):
        self._hash = value

    @property
    def info(self):
        return self._info

    @info.setter
    def info(self, value):
        self._info = value

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value / 10.0


class EntitiesTableModel(QAbstractTableModel):
    def __init__(self, parent=QObject()):
        QAbstractTableModel.__init__(self, parent)
        self._entities = []  # type: List[EntityItem]

    @property
    def entities(self):
        return self._entities

    def getEntity(self, index):
        # type: (QModelIndex) -> EntityItem
        return self._entities[index.row()]

    def beginUpdateStates(self):
        pass

    def endUpdateStates(self):
        self.dataChanged.emit(self.index(0, 3), self.index(self.rowCount()-1, 3))

    def addEntity(self, service, srvindex):
        # type: (int, int) -> EntityItem
        new_index = len(self._entities)
        self.beginInsertRows(QModelIndex(), new_index, new_index)
        entity = EntityItem(service, srvindex)
        self._entities.append(entity)
        self.endInsertRows()
        return entity

    def rowCount(self, parent=QModelIndex()):
        return len(self._entities)

    def columnCount(self, parent=QModelIndex()):
        return 5

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        # type: (int, Qt.Orientation, int) -> Any
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section == 0:
                    return 'Service'
                elif section == 1:
                    return 'Idx'
                elif section == 2:
                    return 'Hash'
                elif section == 3:
                    return 'INfo'
                elif section == 4:
                    return 'State'
        return None

    def data(self, index, role=Qt.DisplayRole):
        # type: (QModelIndex, int) -> Any
        if role == Qt.DisplayRole:
            entity = self._entities[index.row()]
            if index.column() == 0:
                return entity.service_name
            elif index.column() == 1:
                return f'{entity.index}'
            elif index.column() == 2:
                return "0x%04X" % entity.hash
            elif index.column() == 3:
                return entity.info
            elif index.column() == 4:
                return entity.state
            else:
                return ''


class ComunicationWorker(QObject):
    READ_NODE_PROPERTIES = 1
    READ_ENTITIES_STATE = 2
    DISCOVERY_NODES = 3
    NODE_INFO = 4
    UPLOAD_FIRMWARE = 5
    DISCOVER_ENTITIES = 6

    discovery_failed = Signal(str)

    firmwareLoaded = Signal(int)
    firmwareProgress = Signal(int)
    firmwareFailed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, target, proxy: xmlrpc.client.ServerProxy, base_uri: str, parent=None):
        super().__init__(parent)
        self._operation = 0
        self._target = target
        self._base_uri = base_uri
        self._proxy = proxy
        self._model = None  # type: Optional[QAbstractItemModel]
        self._firmware = None  # type: Optional[str]
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self.executeWork)
        self._progress_max = 0
        self._progress_cur = 0
        self._lastError = None

    @property
    def operation(self):
        return self._operation

    @operation.setter
    def operation(self, value):
        self._operation = value

    @property
    def thread(self):
        # type: () -> QThread
        return self._thread

    @property
    def isRunning(self):
        return self._thread.isRunning()

    @property
    def lastError(self):
        return self._lastError

    def startReadNodeProperties(self, model, target):
        # type: (DevicesTableModel, int) -> None
        self._operation = ComunicationWorker.READ_NODE_PROPERTIES
        self._model = model
        self._target = target
        self._thread.start()

    def readNodePropertiesWorker(self):
        row, device = self._model.get_device_by_node_id(self._target)
        self.progress_set_max(5)
        try:
            self._proxy.cmd_node_id(self._target)
            self.progress_next()
            device.tag = self._proxy.cmd_node_tag(self._target)
            self.progress_next()
            device.firmware = self._proxy.cmd_firmware_version(self._target)
            self.progress_next()
            if device.firmware_time.date() > datetime.date(2020, 3, 9):
                device.log_destination = self._proxy.cmd_log_destination(self._target)
                self.progress_next()
                device.entities = self._proxy.cmd_service_get_entities(self._target)
                self.progress_next()
            else:
                self.progress_set_max(self._progress_max - 2)
        except requests.exceptions.ConnectionError as ex:
            self._lastError = str(ex)

    def start_discover_entities(self, model, target):
        # type: (EntitiesTableModel, int) -> None
        self._operation = ComunicationWorker.DISCOVER_ENTITIES
        self._model = model
        self._target = target
        self._thread.start()

    def discover_entities_worker(self):
        self.progress_init(2)
        self.progress_next()
        entities = self._proxy.cmd_service_get_entities(self._target)
        self.progress_set_max(self._progress_cur+entities[0]*2)
        self.progress_next()
        for i in range(1, 5):
            for j in range(0, entities[i]):
                entity = self._model.addEntity(i, j)
                hash_, info = self._proxy.cmd_service_get_entity_info(i, j, self._target)
                self.progress_next()
                entity.hash = hash_
                entity.info = info
                value = self._proxy.cmd_service_get_entity_state(entity.service, entity.hash, self._target)
                self.progress_next()
                entity.state = value

    def startReadEntitiesState(self, model):
        # type: (EntitiesTableModel) -> None
        self._operation = ComunicationWorker.READ_ENTITIES_STATE
        self._model = model
        self._thread.start()

    def readEntitiesWorker(self):
        self._model.beginUpdateStates()
        self.progress_init(2)
        for i in range(self._model.rowCount()):
            entity = self._model.getEntity(self._model.index(i, 0))
            value = self._proxy.cmd_service_get_entity_state(entity.service, entity.hash, self._target)
            entity.state = value / 10.0
        self._model.endUpdateStates()

    def startNodeInfo(self, model, target):
        self._operation = ComunicationWorker.NODE_INFO
        self._model = model
        self._target = target
        self._thread.start()

    def readNodeInfoWorker(self):
        row, device = self._model.get_device_by_node_id(self._target)
        try:
            device.tag = self._proxy.cmd_node_tag(self._target)
            device.firmware = self._proxy.cmd_firmware_version(self._target)
            self._model.device_updated(row)
        except requests.exceptions.ConnectionError as ex:
            self._lastError = str(ex)
        except Exception as ex:
            self._lastError = str(ex)

    def find_next_node_to_discover(self, model: DevicesTableModel):
        _found_id = None
        _found_node = None
        _found_cost = 1e6

        # print('find_next_node_to_discover model size {}'.format(model.rowCount()))
        for _row in range(model.rowCount()):
            _node = model.get_device_by_row(_row)
            # print('check id={} seen={} not_disc={}'.format(_node.text_id, _node.t_already_seen, not _node.t_is_discovered))
            if _node.t_already_seen and not _node.t_is_discovered:
                _path = self._proxy.shortest_path(_node.id)
                if len(_path) > 1:
                    _links = _node.links()
                    _targt_row, _target = model.get_device_by_node_id(_path[-2])
                    _link = _links.get_link_by_target(_target)
                    _cost = max(_link.rssi_remote, _link.rssi_local)
                    if _cost < _found_cost:
                        _found_node = _node
                        _found_cost = _cost
                else:
                    _found_node = _node
                    _found_cost = 0
        return _found_node

    def discovery_neighboors(self, repeats: int, target: DeviceItem, model: DevicesTableModel) -> None:
        tnt = {}  # temporary neighbour table

        print('---------------------------------------------------')
        print("discovery_nodes current {}".format(target.text_id))
        print('---------------------------------------------------')
        print('')
        print('|----------|-----|-----|')
        print('|  ID      | Rem | Loc |')
        print('|----------|-----|-----|')
        links = target.links()
        for row in range(links.rowCount()):
            _link = links.get_link_by_row(row)
            print('| {} | {} | {} |'.format(_link.target_text_id, _link.rssi_remote, _link.rssi_local))
            tnt[_link.target_text_id] = {'target': _link.target(), 'last': None, 'next': (_link.rssi_remote, _link.rssi_local), 'curr': None,
                                         'orig': True}
        print('|----------|-----|-----|')

        for _i in range(0, repeats):
            self._proxy.cmd_discovery_reset(target.real_id())
            print('\n\nStart discovery repetition {}'.format(_i))
            self._proxy.cmd_discovery_start(0, 0, 100, target.real_id())
            time.sleep(3)
            size = self._proxy.cmd_discovery_count(target.real_id())

            for k in tnt:
                tnt[k]['last'] = tnt[k]['next']
                tnt[k]['curr'] = None
                tnt[k]['next'] = None

            # print("Discovery table size is %d" % size)
            for j in range(0, size):
                disc_ser, disc_rssi, disc_rssi2 = self._proxy.cmd_discovery_get(j, target.real_id())
                disc_ser_hex = f"0x{disc_ser:06X}"

                # print('i:{} id:{}'.format(j, disc_ser))
                _, disc_node = model.get_device_by_node_id(disc_ser)
                if disc_node is None:
                    model.add_device(disc_ser)
                    _, disc_node = model.get_device_by_node_id(disc_ser)
                disc_node.t_already_seen = True

                if disc_ser_hex not in tnt:
                    tnt[disc_ser_hex] = {'target':disc_node, 'last': None, 'next': None, 'curr': None, 'orig': False}

                tnt[disc_ser_hex]['curr'] = discovery_rssi_to_weight(disc_rssi), discovery_rssi_to_weight(disc_rssi2)
                tnt[disc_ser_hex]['next'] = tnt[disc_ser_hex]['curr'] \
                    if tnt[disc_ser_hex]['last'] is None \
                    else ((tnt[disc_ser_hex]['last'][0] + tnt[disc_ser_hex]['curr'][0]) / 2, (tnt[disc_ser_hex]['last'][1] +
                                                                                              tnt[disc_ser_hex]['curr'][1]) / 2)

            print('\n|----------|---|------------|------------|------------|--------------|')
            print('| ID       | O | Last w.    | Curr w.    | Next w.    | Delta w.     |')
            print('|----------|---|------------|------------|------------|--------------|')

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
                    print(
                        f'| {k} | {kor} | {kw1[0]:1.2f}, {kw1[1]:1.2f} | ----, ---- | {kw3[0]:1.2f}, {kw3[1]:1.2f} | {kw3[0]:+1.2f}, {kw3[1]:+1.2f} |')
                else:
                    print(f'| {k} | {kor} | {kw1[0]:1.2f}, {kw1[1]:1.2f} | {kw2[0]:1.2f}, {kw2[1]:1.2f} | {kw3[0]:1.2f}, {kw3[1]:1.2f} | '
                          f'{kw3[0] - kw1[0]:+1.2f}, {kw3[1] - kw1[1]:+1.2f} |')

            print(f'|----------|---|------------|------------|------------|--------------|')

        for k in tnt:
            _target_node = tnt[k]['target']
            if not tnt[k]['orig']:
                links.add_link(_target_node)
            if tnt[k]['next'][0] > 1 or tnt[k]['next'][1] > 1:
                links.remove_link(_target_node)
            else:
                _link = links.get_link_by_target(_target_node)
                _link.rssi_local = tnt[k]['next'][0]
                _link.rssi_remote = tnt[k]['next'][1]

    def start_discovery(self, model, target):
        self._operation = ComunicationWorker.DISCOVERY_NODES
        self._model = model
        self._target = target
        self._thread.start()

    def discovery_worker(self):
        discovery = []
        print('---------------------------------------------------')
        print("discovery_nodes target")
        print('---------------------------------------------------')
        assert isinstance(self._model, DevicesTableModel)

        local_node_id = self._proxy.cmd_node_id(0)
        print('Local node id is 0x{:06X}'.format(local_node_id))
        local_node_row, local_node = self._model.get_device_by_node_id(local_node_id)

        if local_node is None:
            self._lastError = "Coordinator not found in graph"
            self.discovery_failed.emit(self._lastError)
            return

        for _r in range(0, self._model.rowCount()):
            _d = self._model.get_device_by_row(_r)
            _d.t_is_discovered = False
            _d.t_already_seen = False
            '''
        for n in graph.nodes:
            graph.nodes[n][DISCOVERY_BUGGY] = False
            for f, t in graph.edges(n):
                if DISCOVERY_COST2 not in graph[f][t]:
                    graph[f][t][DISCOVERY_COST2] = graph[f][t][DISCOVERY_COST1]
            '''

        local_node.t_already_seen = True

        _run_cnt = 0
        _run = True
        while _run:
            curr_node = self.find_next_node_to_discover(self._model)
            if not curr_node:
                print('No more nodes to discover...')
                _run = False
            else:
                try:
                    curr_node.tag = self._proxy.cmd_node_tag(curr_node.real_id())
                    curr_node.firmware = self._proxy.cmd_firmware_version(curr_node.real_id())
                    curr_node.t_is_discovered = True
                    print(f"about to discover from ID={curr_node.text_id} FIRM:{curr_node.firmware} TAG=\"{curr_node.tag}\"")
                except xmlrpc.client.Fault as ex:
                    print(f'{curr_node.text_id} communication error {str(ex)}')
                    curr_node.t_is_discovered = True
                    curr_node.t_is_buggy = True
                    _run_cnt += 1
                    continue

                self.discovery_neighboors(1, curr_node, self._model)
                self._model.upload('{}/upload_xml'.format(self._base_uri))

            _run_cnt += 1
        return

    def sendCommandWithTimoeut(address, size, id):
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

    def startUploadFirmware(self, target, firmware):
        self._operation = ComunicationWorker.UPLOAD_FIRMWARE
        self._model = None
        self._target = target
        self._firmware = firmware
        self._thread.start()

    def uploadFirmware(self):
        if not os.path.exists(self._firmware) or not os.path.isfile(self._firmware):
            self.firmwareFailed.emit(f"{self._firmware} not exists or is not readable")
            return

        try:
            node_firmware = self._proxy.cmd_firmware_version(self._target)
        except Exception as ex:
            self.firmwareFailed.emit(str(ex))
            return

        node_firmware_time = datetime.datetime.strptime(node_firmware, "%b %d %Y, %H:%M:%S")

        if node_firmware_time.date() < datetime.date(2020, 7, 12):
            self.firmwareFailed.emit('Node is too old!!!')
            return

        with open(self._firmware, 'rb') as file_handle:
            baseanme = os.path.basename(self._firmware)
            statinfo = os.stat(self._firmware)
            file_md5 = hashlib.md5(file_handle.read()).hexdigest()
            print(f'Uploading {statinfo.st_size} bytes from {baseanme} to {self._target:08X}')
            self.firmwareLoaded.emit(statinfo.st_size)
            file_handle.seek(0)

            start_address = 0x80000
            address = start_address
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

                # FIXME erased, md5 = get_md5_timeout(address, len(sector), id)
                x = lambda address, sector, id: self._proxy.cmd_spiflash_getmd5(address, len(sector), id)
                erased, md5 = self._proxy.cmd_spiflash_getmd5(address, len(sector), id)
                if md5 == binascii.hexlify(m.digest()).decode():
                    address += len(sector)
                    self.firmwareProgress.emit(address - 0x80000)
                    continue

                if erased == 0:
                    # FIXME res = spiflash_erase_timeout(address, 4096, id)
                    _res = self._proxy.cmd_spiflash_erase(address, 4096, id)
                else:
                    if md5 != '6ae59e64850377ee5470c854761551ea':
                        print('memory erased but md5 is ', md5)

                if md5 != binascii.hexlify(m.digest()):
                    sector_steps = int((len(sector) - 1) / 1024) + 1
                    for i in range(0, sector_steps):
                        chunk = sector[1024 * i:1024 * (i + 1)]
                        # FIXME error = spiflash_write_timeout(address, chunk, id)
                        error = self._proxy.cmd_spiflash_write(address, chunk, id)
                        address += len(chunk)
                        self.firmwareProgress.emit(address - 0x80000)
                        if error:
                            no_error = False
                            break

                # FIXME erased, md5 = get_md5_timeout(address - len(sector), len(sector), id)
                erased, md5 = self._proxy.cmd_spiflash_getmd5(address - len(sector), len(sector), id)
                if md5 != binascii.hexlify(m.digest()).decode():
                    print('Errrrrrrrrr')
                    address -= len(sector)
                    self.firmwareProgress.emit(address - 0x80000)
                    new_sector = False

            if no_error:
                # FIXME erased, md5 = get_md5_timeout(START_ADDRESS, statinfo.st_size, id)
                erased, md5 = self._proxy.cmd_spiflash_getmd5(start_address, statinfo.st_size, id)
                if md5 == file_md5:
                    print('File sent try to finalize update')
                    error = self._proxy.cmd_spiflash_eboot(start_address, statinfo.st_size, id)
                    if error == 0:
                        print('Update finalized try to reboot device')
                        self._proxy.cmd_reboot(id)
                else:
                    print(md5, file_md5)

    def progress_init(self, value):
        self._progress_max = value
        self._progress_cur = 0
        self.progress.emit(self._progress_cur, self._progress_max)

    def progress_next(self):
        self._progress_cur += 1
        self.progress.emit(self._progress_cur, self._progress_max)

    def progress_set_max(self, new_max):
        self._progress_max = new_max
        self.progress.emit(self._progress_cur, self._progress_max)

    @Slot()
    def executeWork(self):
        self._lastError = None
        if self._operation == ComunicationWorker.READ_NODE_PROPERTIES:
            assert isinstance(self._model, DevicesTableModel)
            self.readNodePropertiesWorker()
        elif self._operation == ComunicationWorker.DISCOVER_ENTITIES:
            assert isinstance(self._model, EntitiesTableModel)
            self.discover_entities_worker()
        elif self._operation == ComunicationWorker.READ_ENTITIES_STATE:
            assert isinstance(self._model, EntitiesTableModel)
            self.readEntitiesWorker()
        if self._operation == ComunicationWorker.NODE_INFO:
            assert isinstance(self._model, DevicesTableModel)
            self.readNodeInfoWorker()
        if self._operation == ComunicationWorker.DISCOVERY_NODES:
            assert isinstance(self._model, DevicesTableModel)
            try:
                self.discovery_worker()
            except Exception as ex:
                print(traceback.format_exc())

        if self._operation == ComunicationWorker.UPLOAD_FIRMWARE:
            self.uploadFirmware()
        else:
            time.sleep(1)
            self._thread.terminate()
