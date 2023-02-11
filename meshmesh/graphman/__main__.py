import argparse
import sys

import meshmesh.graphman.uic
from meshmesh.graphman.handler import MeshMeshHandler

from meshmesh.graphman.mainwindow_ui import Ui_MainWindow

from PySide6 import QtCore
from PySide6 import QtWidgets

from PySide6.QtCore import Slot

import networkx as nx

class MainWindow(QtWidgets.QDialog, Ui_MainWindow):
    def __init__(self, parent: QtWidgets.QWidget = None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        self._handler = MeshMeshHandler(self)
        self._handler.got_graph.connect(self._on_got_graph)
        self._handler.get_graph()

    @Slot(str)
    def _on_got_graph(self, data: str):
        G: nx.Graph = nx.parse_graphml(data)
        print(G.name, len(G.nodes))

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName("LeGuru")
    app.setOrganizationDomain("leguru.net")
    app.setApplicationName("Meshmesh Grpah Manager")

    parser = argparse.ArgumentParser(description='meshmesh.graphman')
    args = parser.parse_args()

    frame = MainWindow()
    frame.show()
    app.exec()
