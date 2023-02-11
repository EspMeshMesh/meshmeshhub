from PySide6 import QtCore
from PySide6 import QtNetwork

from PySide6.QtCore import Signal, Slot

class MeshMeshHandler(QtCore.QObject):
    user_agent = 'MeshMesh XMLRPC'
    got_graph = Signal(str)

    def __init__(self, parent: QtCore.QObject = None):
        super(MeshMeshHandler, self).__init__(parent)
        self._manager = QtNetwork.QNetworkAccessManager(self)

    def get_graph(self):
        _req = QtNetwork.QNetworkRequest()
        _req.setUrl("http://127.0.0.1:8801/download_xml")
        _req.setHeader(QtNetwork.QNetworkRequest.UserAgentHeader, MeshMeshHandler.user_agent)
        _rep = self._manager.get(_req)
        _rep.finished.connect(self._on_get_graph_finished)

    def call(self):
        _req = QtNetwork.QNetworkRequest()
        _req.setUrl("http://127.0.0.1:8801/RPC2")
        _req.setHeader(QtNetwork.QNetworkRequest.UserAgentHeader, MeshMeshHandler.user_agent)
        _req.setHeader(QtNetwork.QNetworkRequest.ContentTypeHeader, "text/xml")

        _data = QtCore.QByteArray()
        _w = QtCore.QXmlStreamWriter(_data)
        _w.setAutoFormatting(True)
        _w.writeStartDocument()
        _w.writeStartElement("methodCall")
        _w.writeTextElement("methodName", "cmd_node_id")
        _w.writeStartElement("params")
        _w.writeStartElement("param")
        _w.writeStartElement("value")
        _w.writeTextElement("int", str(0))
        _w.writeEndElement()  # param
        _w.writeEndElement()  # params
        _w.writeEndElement()  # methodName
        _w.writeEndElement()  # methodCall
        _w.writeEndDocument()

        _rep = self._manager.post(_req, _data)
        _rep.finished.connect(self._on_request_finished)

    @Slot()
    def _on_get_graph_finished(self):
        reply: QtNetwork.QNetworkReply = self.sender()
        _s = reply.readAll().toStdString()
        self.got_graph.emit(_s)
        reply.deleteLater()

    @Slot()
    def _on_request_finished(self):
        reply: QtNetwork.QNetworkReply = self.sender()
        if reply.error() != QtNetwork.QNetworkReply.NoError:
            print("Error", reply.errorString())
        else:
            _wait_param = False
            _param_type = None
            _params = []
            _r = QtCore.QXmlStreamReader(reply)
            while not _r.atEnd() and not _r.hasError():
                _t = _r.readNext()
                if _t == QtCore.QXmlStreamReader.StartDocument:
                    continue
                if _t == QtCore.QXmlStreamReader.StartElement:
                    if _wait_param:
                        _param_type = _r.name()
                        _wait_param = False
                    if _r.name() == "param":
                        _wait_param = True
                    continue
                if _t == QtCore.QXmlStreamReader.Characters:
                    if _param_type is not None:
                        _params.append(int(_r.text()))
                        _param_type = None
                if _t == QtCore.QXmlStreamReader.EndElement:
                    continue
                print("A", _t)
            if _r.hasError():
                print("Error", _r.errorString())

            print(_params)