import argparse
import sys

from PySide2 import QtCore
from PySide2 import QtWidgets

from PySide2.QtCore import Slot, QItemSelectionModel
from PySide2.QtWidgets import QHeaderView, QFileDialog, QInputDialog, QMessageBox

from .ui_mainwindow import Ui_MainWindow
from .transport import RequestsTransport
from .nodeprops import NodeProps
from .proxyworker import DevicesTableModel, ComunicationWorker
from .graphwidget import GraphWidget

from xmlrpc.client import ServerProxy


GRAPH_FILENAME = 'meshmesh.graphml'


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, hub=None, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        settings = QtCore.QSettings()
        self._base_url = f"http://{hub}:8801" if hub else settings.value("server/url", "http://127.0.0.1:8801")
        self._proxy = ServerProxy(self._base_url, transport=RequestsTransport())
        self._worker = ComunicationWorker(0, self._proxy, self._base_url)
        self._worker.thread.finished.connect(self._on_worker_finished)
        self._model = DevicesTableModel(self)
        self._model.download_graph(self._base_url)
        # self._model.load_graph(GRAPH_FILENAME)

        self._model.populate_model()
        self.devicesTable.setModel(self._model)
        self.devicesTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.devicesTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.devicesTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.devicesTable.doubleClicked.connect(self.onDeviceDoubleClicked)

        self.tabNetworkGraph.layout().addWidget(GraphWidget(self._model))

    @Slot()
    def on_actionSaveGraph_triggered(self):
        self._model.save_graph('out_'+GRAPH_FILENAME)

    @Slot()
    def on_actionSaveGraphAs_triggered(self):
        filename, _filter = QFileDialog.getSaveFileName(self, "Save grpah", None, "*.graphml")
        if filename is not None and len(filename) > 0:
            self._model.save_graph(filename)

    @Slot()
    def on_actionDiscovery_triggered(self):
        self._worker.start_discovery(self._model, 0)

    @Slot()
    def on_actionDiscovery_triggered(self):
        self._worker.start_discovery(self._model, 0)

    @Slot()
    def on_actionAddNode_triggered(self):
        value, result = QInputDialog.getInt(self, 'Enter node address', 'Address', 0, 0, 2^24-1)
        if result:
            self._model.add_device("0x%06X" % value)

    @Slot()
    def on_actionDeleteNode_triggered(self):
        selmod = self.devicesTable.selectionModel()  # type: QItemSelectionModel
        if selmod.hasSelection():
            rows = selmod.selectedRows()
            for row in rows:
                if QMessageBox.warning(self, 'Delete Node', f'You are about to delete'):
                    self._model.delete_device(row)

    @Slot(QtCore.QModelIndex)
    def onDeviceDoubleClicked(self, index):
        device = self._model.get_device_by_index(index)
        dialog = NodeProps(device.id, self._proxy, self._model, self)
        dialog.exec_()

    @Slot()
    def _on_worker_finished(self):
        pass


def auto_int(x):
    return int(x, 0)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setOrganizationName("Stefano Pagnottelli")
    app.setOrganizationDomain("leguru.com")
    app.setApplicationName("MeshMeshGui2")

    parser = argparse.ArgumentParser(description='Meshmesh Gui2')
    parser.add_argument('--hub', dest='hub', default=None, type=str, help='IP address of the hub2 server')
    parser.add_argument('--node-id', dest='node_id', default=0, type=auto_int, help='additional node id')
    args = parser.parse_args()

    frame = MainWindow(hub=args.hub)
    if args.node_id > 0:
        frame.add_node(args.node_id)
    frame.show()
    app.exec_()
