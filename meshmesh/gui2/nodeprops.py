import os
from xmlrpc.client import ServerProxy

from PySide2 import QtCore
from PySide2 import QtWidgets

from PySide2.QtCore import Slot

from .devicemodel import DevicesTableModel
from .ui_nodeprops import Ui_NodeProps
from .proxyworker import EntitiesTableModel, ComunicationWorker


class NodeProps(QtWidgets.QDialog, Ui_NodeProps):
    def __init__(self, target, proxy, model, parent=None):
        # type: (int, ServerProxy, DevicesTableModel, QtCore.QObject) -> None
        super(NodeProps, self).__init__(parent)
        self.setupUi(self)

        self._proxy = proxy
        self._target = target
        self._model = model
        self._device_id, self._device = self._model.get_device_by_node_id(self._target)
        self._entitiesModel = EntitiesTableModel()
        self.entitiesTable.setModel(self._entitiesModel)
        self.linksTable.setModel(self._device.links())
        self._entities = b'\x00\x00\x00\x00\x00'
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer_timeout)

        self._worker = ComunicationWorker(target, proxy)
        self._worker.firmwareLoaded.connect(self._on_worker_firmwareLoaded)
        self._worker.firmwareProgress.connect(self._on_worker_firmwareProgress)
        self._worker.firmwareFailed.connect(self._on_worker_firmwareFailed)
        self._worker.thread.finished.connect(self._on_worker_finished)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.startNodeInfo(self._model, self._target)

    @Slot()
    def on_rebootNodeButton_clicked(self):
        self._proxy.cmd_reboot(self._target)

    @Slot()
    def on_applyButton_clicked(self):
        self._proxy.cmd_node_tag_set(self.nodeTag.text(), self._target)
        self._proxy.cmd_log_destination_set(self.logDestination.value(), self._target)

    @Slot()
    def on_entitiesRefresh_clicked(self):
        self._worker.start_discover_entities(self._entitiesModel, self._target)

    @Slot()
    def on_firmwareFileSelect_clicked(self):
        settings = QtCore.QSettings()
        last_dir = str(settings.value("firmwarFolder", None))
        filename, s_filter = QtWidgets.QFileDialog.getOpenFileName(self, "Select firmware file", last_dir, "*.bin")
        if filename is not None and os.path.dirname(filename) != last_dir:
            settings.setValue("firmwarFolder", os.path.dirname(filename))
        if filename is not None:
            self.firmwareFile.setText(filename)

    @Slot()
    def on_firmwareUploadButton_clicked(self):
        if self._worker.isRunning:
            QtWidgets.QMessageBox.warning(self, "Process already running", "Another process is already running")
        else:
            self.workerStatus.setValue(100)
            self._worker.startUploadFirmware(self._target, self.firmwareFile.text())

    @Slot(int)
    def _on_worker_firmwareLoaded(self, max_size):
        self.firmwareUploadState.setMinimum(0)
        self.firmwareUploadState.setMaximum(max_size)
        self.firmwareUploadState.setValue(0)

    @Slot(int)
    def _on_worker_firmwareProgress(self, progress):
        self.firmwareUploadState.setValue(progress)

    @Slot(int)
    def _on_worker_firmwareFailed(self, error):
        QtWidgets.QMessageBox.critical(self, "Firmware upload error", error)

    @Slot()
    def _on_worker_finished(self):
        print('work finisched')
        self.workerStatus.setValue(0)
        if self._worker.lastError is not None:
            self.workerResult.setText('Error')
            self.workerResult.setToolTip(self._worker.lastError)
        else:
            self.workerResult.setText('Ready')
            self.workerResult.setToolTip('')
            if self._worker.operation == ComunicationWorker.NODE_INFO:
                self.nodeId.setValue(self._device.id)
                self.nodeTag.setText(self._device.tag)
                self.nodeFirmware.setText(self._device.firmware)
                self.logDestination.setValue(self._device.log_destination)
                self.tabs.setDisabled(False)

    @Slot(int, int)
    def _on_worker_progress(self, cur, maxval):
        self.workerStatus.setValue(cur)
        if self.workerStatus.maximum() != maxval:
            self.workerStatus.setMaximum(maxval)
        if self._worker.operation == ComunicationWorker.READ_NODE_PROPERTIES:
            if cur == 1:
                self.nodeId.setValue(self._device.id)

    @Slot()
    def _on_timer_timeout(self):
        if self._worker.isRunning:
            self._timer.start(3000)
        else:
            self.workerStatus.setValue(100)
            self._worker.startReadEntitiesState(self._entitiesModel)
