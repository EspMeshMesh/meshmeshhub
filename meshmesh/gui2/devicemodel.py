import datetime
import locale
import math
import os
import tempfile

from typing import List, Any, Optional, Tuple, Dict

import networkx as nx
import requests

from PySide2.QtCore import QAbstractTableModel, QModelIndex, Qt, QObject
from PySide2.QtWidgets import QWidget


class DeviceLink:
    def __init__(self, source: str, target: str, graph_edge: Dict, graph: nx.Graph) -> None:
        self._source: int = int(source[2:], 16)
        self._target: int = int(target[2:], 16)
        self._graph_edge: Dict = graph_edge  # type:
        self._graph: nx.Graph = graph

    def target(self):
        _t = self.target_text_id
        return DeviceItem(_t, self._graph.nodes[_t], self._graph)

    @property
    def target_text_id(self) -> str:
        return "0x%06X" % self._target

    @property
    def rssi_remote(self):
        # type: () -> float
        return self._graph_edge['weight']

    @rssi_remote.setter
    def rssi_remote(self, value: float) -> None:
        self._graph_edge['weight'] = value

    @property
    def rssi_local(self):
        # type: () -> float
        return self._graph_edge['weight2']

    @rssi_local.setter
    def rssi_local(self, value: float) -> None:
        self._graph_edge['weight2'] = value


class DeviceItem:
    def __init__(self, node_id, graph_node, graph):
        #  type: (str, dict, nx.Graph) -> None
        self._id = int(node_id[2:], 16)  # type: int
        self._log_destination = 0  # type: int
        self._position = [0, 0]  # type: List[int]
        self._entities = []  # type: List[int]
        self._graph_node = graph_node  # type: Optional[Dict]
        self._graph = graph  # type: Optional[nx.Graph]

    @property
    def id(self):
        # type: () -> int
        return self._id

    def real_id(self):
        return self.id if not self.is_coordinator else 0

    @property
    def text_id(self):
        return "0x%06X" % self._id

    @property
    def tag(self):
        # type: () -> str
        return self._graph_node['tag'] if 'tag' in self._graph_node else ''

    @tag.setter
    def tag(self, value):
        # type: (str) -> None
        self._graph_node['tag'] = value

    @property
    def firmware(self):
        # type: () -> str
        return self._graph_node['firmware'] if 'firmware' in self._graph_node else ''

    @firmware.setter
    def firmware(self, value):
        # type: (str) -> None
        self._graph_node['firmware'] = value

    @property
    def firmware_time(self):
        locale.setlocale(locale.LC_ALL, 'C')
        firmware_time = None if not self.firmware or self.firmware == '' else datetime.datetime.strptime(self.firmware, "%b %d %Y, %H:%M:%S")
        return firmware_time

    @property
    def is_coordinator(self):
        return self._graph_node['coordinator'] if 'coordinator' in self._graph_node else False

    @is_coordinator.setter
    def is_coordinator(self, value):
        self._graph_node['coordinator'] = value

    @property
    def log_destination(self):
        # type: () -> int
        return self._log_destination

    @log_destination.setter
    def log_destination(self, value):
        # type: (int) -> None
        self._log_destination = value

    @property
    def position(self):
        return self._graph_node['position_x'], self._graph_node['position_y'] if 'position_x' in self._graph_node else [0, 0]

    @position.setter
    def position(self, value):
        if value is not None:
            self._graph_node['position_x'] = value[0]
            self._graph_node['position_y'] = value[1]
        else:
            self._graph_node['position_x'] = 0
            self._graph_node['position_y'] = 0

    @property
    def t_is_discovered(self) -> bool:
        return self._graph_node['t_is_discovered'] if 't_is_discovered' in self._graph_node else False

    @t_is_discovered.setter
    def t_is_discovered(self, value: bool):
        self._graph_node['t_is_discovered'] = value

    @property
    def t_already_seen(self) -> bool:
        return self._graph_node['t_already_seen'] if 't_already_seen' in self._graph_node else False

    @t_already_seen.setter
    def t_already_seen(self, value: bool):
        self._graph_node['t_already_seen'] = value

    @property
    def entities(self):
        # type: () -> List[int]
        return self._entities

    @entities.setter
    def entities(self, value):
        # type: (List[int]) -> None
        self._entities = value

    def links(self) -> "LinksTableModel":
        return LinksTableModel(self._graph, self)


class LinksTableModel(QAbstractTableModel):
    def __init__(self, graph, source: DeviceItem, parent: Optional[QObject] = None) -> None:
        QAbstractTableModel.__init__(self, parent)
        self._graph = graph  # type: Optional[nx.Graph]
        self._source: DeviceItem = source
        self._links = []  # type: List[DeviceLink]

    def add_link(self, target: DeviceItem) -> DeviceLink:
        _s = self._source.text_id
        _t = target.text_id
        self._graph.add_edge(_s, _t)
        return DeviceLink(_s, _t, self._graph[_s][_t], self._graph)

    def get_link_by_index(self, index: QModelIndex) -> DeviceLink:
        _s, _t = list(nx.edges(self._graph, self._source.text_id))[index.row()]
        return DeviceLink(_s, _t, self._graph[_s][_t], self._graph)

    def get_link_by_row(self, row: int) -> DeviceLink:
        _s, _t = list(nx.edges(self._graph, self._source.text_id))[row]
        return DeviceLink(_s, _t, self._graph[_s][_t], self._graph)

    def get_link_by_target(self, target: DeviceItem) -> DeviceLink:
        _s = self._source.text_id
        _t = target.text_id
        return DeviceLink(_s, _t, self._graph[_s][_t], self._graph)

    def rowCount(self, parent=QModelIndex()):
        return len(nx.edges(self._graph, self._source.text_id))

    def columnCount(self, parent=QModelIndex()):
        return 3

    def data(self, index, role=Qt.DisplayRole):
        # type: (QModelIndex, int) -> Any
        if role == Qt.DisplayRole:
            link = self.get_link_by_index(index)

            if index.column() == 0:
                return link.target_text_id
            elif index.column() == 1:
                return f"{link.rssi_remote:1.2f}"
            elif index.column() == 2:
                return f"{link.rssi_local:1.2f}"
            else:
                return ''
        elif role == Qt.TextAlignmentRole:
            if index.column() == 1 or index.column() == 2:
                return Qt.AlignRight
            else:
                return Qt.AlignLeft

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        #  type: (int, Qt.Orientation, int) -> Any
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section == 0:
                    return "Target"
                elif section == 1:
                    return "Rssi rem."
                elif section == 2:
                    return "Rssi loc."


class DevicesTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        #  type: (QWidget) -> None
        QAbstractTableModel.__init__(self, parent)
        self._graph = None  # type: Optional[nx.Graph]

    @property
    def graph(self):
        #  type: () -> nx.Graph
        return self._graph

    def get_device_by_row(self, row: int) -> DeviceItem:
        _n = list(self._graph.nodes)[row]
        return DeviceItem(_n, self._graph.nodes[_n], self._graph)

    def get_device_by_index(self, index: QModelIndex) -> DeviceItem:
        return self.get_device_by_row(index.row())

    def get_device_by_node_id(self, serial: int) -> Tuple[int, Optional[DeviceItem]]:
        node_id = "0x%06X" % serial
        try:
            row = list(self._graph.nodes).index(node_id)
            return row, DeviceItem(node_id, self._graph.nodes[node_id], self._graph)
        except ValueError:
            # print('ID not found {}'.format(node_id))
            return -1, None

    def delete_device(self, index):
        #  type: (QModelIndex) -> None
        self.beginRemoveRows(QModelIndex(), index.row(), index.row())
        self._graph.remove_node(list(self._graph.nodes)[index.row()])
        self.endRemoveRows()

    def add_device(self, node_id: int):
        new_index = self._graph.number_of_nodes()
        self.beginInsertRows(QModelIndex(), new_index, new_index)
        self._graph.add_node('0x{:06X}'.format(node_id), tag='', discover=False, position_x=0, position_y=0)
        self.endInsertRows()

    def device_updated(self, row):
        self.dataChanged.emit(self.index(row, 1), self.index(row, 2))

    def rowCount(self, parent=QModelIndex()):
        return self._graph.number_of_nodes() if self._graph else 0

    def columnCount(self, parent=QModelIndex()):
        return 3

    def data(self, index, role=Qt.DisplayRole):
        #  type: (QModelIndex, int) -> Any
        if role == Qt.DisplayRole:
            node_id = list(self._graph.nodes)[index.row()]
            device = DeviceItem(node_id, self._graph.nodes[node_id], self._graph)

            if index.column() == 0:
                return device.text_id
            elif index.column() == 1:
                return device.tag
            elif index.column() == 2:
                return device.firmware
            else:
                return ''

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        #  type: (int, Qt.Orientation, int) -> Any
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section == 0:
                    return "Address"
                elif section == 1:
                    return "Note tag"
                elif section == 2:
                    return "Firmware date"

        return super().headerData(section, orientation, role)

    @staticmethod
    def exp_weight(data):
        return math.pow(max(data['weight'], data['weight2']), 1.1)

    def load_graph(self, filename):
        # type: (str) -> None
        if os.path.exists(filename):
            self._graph = nx.readwrite.read_graphml(filename)  # type: nx.Graph
            self._post_load_graph()

    def download_graph(self, base_url):
        resp = requests.get(f'{base_url}/download_xml')
        _, resptemp = tempfile.mkstemp()
        with open(resptemp, 'wb') as fp:
            fp.write(resp.content)
        self._graph = nx.readwrite.read_graphml(resptemp)
        os.unlink(resptemp)
        self._post_load_graph()

    def _post_load_graph(self):
        for n in self._graph.nodes:
            for _f, _t in self._graph.edges(n):
                if 'w' not in self._graph[_f][_t]:
                    self._graph[_f][_t]['w'] = 100.0 - DevicesTableModel.exp_weight(self._graph[_f][_t]) * 100.0
        pos = nx.spring_layout(self._graph, weight='w')
        for n in pos:
            self._graph.nodes[n]['position_x'], self._graph.nodes[n]['position_y'] = pos[n]

    def save_graph(self, filename):
        # type: (str) -> None
        nx.spring_layout(self._graph)
        nx.readwrite.write_graphml(self._graph, filename)

    def populate_model(self):
        # type: () -> None
        if self._graph:
            for n in nx.nodes(self._graph):
                list(self._graph.nodes).append(n)

    def shortest_path(self, _from: DeviceItem, _to: DeviceItem):
        pass

    def upload(self, uri):
        nx.spring_layout(self._graph)
        _, resptemp = tempfile.mkstemp()
        nx.readwrite.write_graphml(self._graph, resptemp)
        with open(resptemp, 'rb') as f:
            requests.post(uri, files={'graph': f.read()})
        os.unlink(resptemp)
