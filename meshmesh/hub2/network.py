import math
import os
import logging
import shutil

from typing import Optional

import networkx as nx

GL_NETWORK_GRAPH = None  # type: Optional[GraphNetwork]


class GraphNetworkError(Exception):
    pass


class GraphNetwork(object):
    def __init__(self):
        self._network: Optional[nx.Graph] = None
        self._last_filename: Optional[str] = None
        self._local_node_id: int = 0

    def _debug_path(self, s_path):
        p_ = None
        d = None
        for p in s_path:
            if p_ is None:
                d = p
                p_ = p
            else:
                d += " -> "
                d += "(%1.2f)" % self._network[p_][p]['weight']
                d += " -> "
                d += p
                p_ = p
        logging.debug("shortest_path " + d)

    @property
    def local_node_id(self) -> int:
        return self._local_node_id

    @local_node_id.setter
    def local_node_id(self, value: int):
        self._local_node_id = value
        if self._network is None:
            self._local_node_id = None
            logging.error(f'GraphNetwork.local_node_id network is not loaded')
            return

        if self.local_node_text_id not in self._network:
            self.add_node(self.local_node_id)
            logging.error(f'GraphNetwork.local_node_id {self.local_node_text_id} is not present in graph')

        self._network.nodes[self.local_node_text_id]['coordinator'] = True

    @property
    def local_node_text_id(self):
        return "0x%06X" % self.local_node_id

    @staticmethod
    def node_text_id(value):
        return "0x%06X" % value

    @staticmethod
    def instance():
        global GL_NETWORK_GRAPH
        if GL_NETWORK_GRAPH is None:
            GL_NETWORK_GRAPH = GraphNetwork()
        return GL_NETWORK_GRAPH

    @staticmethod
    def id2hex(id_: int) -> str:
        return "0x%06X" % id_

    @staticmethod
    def exp_weight(_e1, _e2, data):
        return math.pow(max(data['weight'], data['weight2']), 1.1)

    def add_node(self, _id: int, _tag=''):
        self._network.add_node(GraphNetwork.id2hex(_id), tag=_tag, inuse=False, discover=False, buggy=False)

    def shortest_path(self, target, full_path=False):
        try:
            s_path = nx.astar_path(self._network, self.local_node_text_id, self.node_text_id(target), weight=GraphNetwork.exp_weight)
        except nx.exception.NodeNotFound as ex:
            logging.error(f'Node not found {self.local_node_text_id} -> {self.node_text_id(target)}')
            raise ex
        self._debug_path(s_path)
        if not full_path:
            s_path = s_path[1:]
        path = [int(i[2:], 16) for i in s_path]
        return path

    def init_empty(self):
        self._network = nx.Graph()

    def load_network(self, filename, is_temporary=False):
        if not is_temporary:
            self._last_filename = filename
        if os.path.exists(filename):
            self._network = nx.readwrite.read_graphml(filename)
            print(nx.info(self._network))

    def save_network(self, filename, temporary=False, backup=False):
        if not temporary:
            if self._last_filename and backup:
                shutil.move(self._last_filename, "%s.backup" % self._last_filename)
            if len(filename) < 1 or filename[0] == '*':
                filename = self._last_filename
        if self._network is None:
            self._network = nx.Graph()
            # self._network.add_node(_id, tag=_tag, inuse=False, discover=False, buggy=False)
        print(filename, self._network.nodes(data=True))
        nx.readwrite.write_graphml(self._network, filename)

    def is_network_loaded(self):
        return self._network is not None
