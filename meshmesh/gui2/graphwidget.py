import weakref
import math
from typing import Any, Optional

from PySide2.QtCore import Slot
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QGraphicsItem, QGraphicsView, QGraphicsScene, QStyleOptionGraphicsItem

from meshmesh.gui2.devicemodel import DevicesTableModel, DeviceItem


class Edge(QGraphicsItem):
    Pi = math.pi
    two_pi = 2.0 * Pi

    Type = QGraphicsItem.UserType + 2

    def __init__(self, source_node, dest_node):
        QGraphicsItem.__init__(self)

        self.arrow_size = 0.0
        self.sourcePoint = QtCore.QPointF()
        self.destPoint = QtCore.QPointF()
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)
        self.source = weakref.ref(source_node)
        self.dest = weakref.ref(dest_node)
        self.source().add_edge(self)
        self.dest().add_edge(self)
        self.adjust()

    def type(self):
        return Edge.Type

    def source_node(self):
        return self.source()

    def set_source_node(self, node):
        self.source = weakref.ref(node)
        self.adjust()

    def dest_node(self):
        return self.dest()

    def set_dest_node(self, node):
        self.dest = weakref.ref(node)
        self.adjust()

    def adjust(self):
        if not self.source() or not self.dest():
            return

        line = QtCore.QLineF(self.mapFromItem(self.source(), 0, 0), self.mapFromItem(self.dest(), 0, 0))
        length = line.length()

        if length == 0.0:
            return

        edge_offset = QtCore.QPointF((line.dx() * 10) / length, (line.dy() * 10) / length)

        self.prepareGeometryChange()
        self.sourcePoint = line.p1() + edge_offset
        self.destPoint = line.p2() - edge_offset

    def boundingRect(self):
        if not self.source() or not self.dest():
            return QtCore.QRectF()

        pen_width = 1
        extra = (pen_width + self.arrow_size) / 2.0

        return QtCore.QRectF(self.sourcePoint,
                             QtCore.QSizeF(self.destPoint.x() - self.sourcePoint.x(), self.destPoint.y() - self.sourcePoint.y())).\
            normalized().adjusted(-extra, -extra, extra, extra)

    def paint(self, painter, option, widget=None):
        if not self.source() or not self.dest():
            return

        # Draw the line itself.
        line = QtCore.QLineF(self.sourcePoint, self.destPoint)

        if line.length() == 0.0:
            return

        painter.setPen(QtGui.QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
        painter.drawLine(line)

        # Draw the arrows if there's enough room.
        angle = math.acos(line.dx() / line.length())
        if line.dy() >= 0:
            angle = Edge.two_pi - angle

        if self.arrow_size > 0:
            source_arrow_p1 = self.sourcePoint + QtCore.QPointF(math.sin(angle + Edge.Pi / 3) * self.arrow_size,
                                                                math.cos(angle + Edge.Pi / 3) * self.arrow_size)
            source_arrow_p2 = self.sourcePoint + QtCore.QPointF(math.sin(angle + Edge.Pi - Edge.Pi / 3) * self.arrow_size,
                                                                math.cos(angle + Edge.Pi - Edge.Pi / 3) * self.arrow_size)
            dest_arrow_p1 = self.destPoint + QtCore.QPointF(math.sin(angle - Edge.Pi / 3) * self.arrow_size,
                                                            math.cos(angle - Edge.Pi / 3) * self.arrow_size)
            dest_arrow_p2 = self.destPoint + QtCore.QPointF(math.sin(angle - Edge.Pi + Edge.Pi / 3) * self.arrow_size,
                                                            math.cos(angle - Edge.Pi + Edge.Pi / 3) * self.arrow_size)

            painter.setBrush(QtCore.Qt.black)
            painter.drawPolygon(QtGui.QPolygonF([line.p1(), source_arrow_p1, source_arrow_p2]))
            painter.drawPolygon(QtGui.QPolygonF([line.p2(), dest_arrow_p1, dest_arrow_p2]))


class Node(QGraphicsItem):
    Type = QGraphicsItem.UserType + 1

    def __init__(self, parent, item, fixed=False):
        #  type: (QGraphicsView, DeviceItem, Optional[bool]) -> None
        QGraphicsItem.__init__(self)
        self._item: DeviceItem = item
        self._fixed: bool = fixed

        if fixed:
            self._color = QtCore.Qt.red
            self._dark_color = QtCore.Qt.darkRed
        else:
            self._color = QtCore.Qt.yellow
            self._dark_color = QtCore.Qt.darkYellow

        self.graph = weakref.ref(parent)
        self.edge_list = []
        self.new_pos = QtCore.QPointF()

        if not fixed:
            self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setCacheMode(self.DeviceCoordinateCache)
        self.setZValue(-1)

    @property
    def node_id(self) -> str:
        return self._item.text_id

    def type(self):
        return Node.Type

    def add_edge(self, edge):
        self.edge_list.append(weakref.ref(edge))
        edge.adjust()

    def edges(self):
        return self.edge_list

    def calculate_forces(self):
        if self._fixed or True:
            self.new_pos = self.pos()
            return
        if not self.scene() or self.scene().mouseGrabberItem() is self:
            self.new_pos = self.pos()
            return

        # Sum up all forces pushing this item away.
        xvel = 0.0
        yvel = 0.0
        for item in self.scene().items():
            if not isinstance(item, Node):
                continue

            line = QtCore.QLineF(self.mapFromItem(item, 0, 0), QtCore.QPointF(0, 0))
            dx = line.dx()
            dy = line.dy()
            _l = 2.0 * (dx * dx + dy * dy)
            if _l > 0:
                xvel += (dx * 150.0) / _l
                yvel += (dy * 150.0) / _l

        # Now subtract all forces pulling items together.
        weight = (len(self.edge_list) + 1) * 10.0
        for edge in self.edge_list:
            if edge().source_node() is self:
                pos = self.mapFromItem(edge().dest_node(), 0, 0)
            else:
                pos = self.mapFromItem(edge().source_node(), 0, 0)
            xvel += pos.x() / weight
            yvel += pos.y() / weight

        if QtCore.qAbs(xvel) < 0.1 and QtCore.qAbs(yvel) < 0.1:
            xvel = yvel = 0.0

        scene_rect = self.scene().sceneRect()
        self.new_pos = self.pos() + QtCore.QPointF(xvel, yvel)
        self.new_pos.setX(min(max(self.new_pos.x(), scene_rect.left() + 10), scene_rect.right() - 10))
        self.new_pos.setY(min(max(self.new_pos.y(), scene_rect.top() + 10), scene_rect.bottom() - 10))

    def advance(self, phase):
        if self.new_pos == self.pos():
            return False

        self.setPos(self.new_pos)
        return True

    def boundingRect(self):
        adjust = 2.0
        return QtCore.QRectF(-10 - adjust, -10 - adjust, 23 + adjust, 23 + adjust)

    def shape(self):
        path = QtGui.QPainterPath()
        path.addEllipse(-10, -10, 20, 20)
        return path

    def paint(self, painter, option, widget=None):
        # type: (QtGui.QPainter, QStyleOptionGraphicsItem, Any) -> None
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtCore.Qt.darkGray)
        painter.drawEllipse(-7, -7, 20, 20)

        gradient = QtGui.QRadialGradient(-3, -3, 10)
        if self.isSelected():
            gradient.setCenter(3, 3)
            gradient.setFocalPoint(3, 3)
            gradient.setColorAt(1, QtGui.QColor(self._color).lighter(120))
            gradient.setColorAt(0, QtGui.QColor(self._dark_color).lighter(120))
        else:
            gradient.setColorAt(0, self._color)
            gradient.setColorAt(1, self._dark_color)

        painter.setBrush(QtGui.QBrush(gradient))
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 0))
        painter.drawEllipse(-10, -10, 20, 20)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            for edge in self.edge_list:
                edge().adjust()
            self.graph().item_moved()

        return QGraphicsItem.itemChange(self, change, value)

    def mousePressEvent(self, event):
        self.update()
        QGraphicsItem.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        self.update()
        QGraphicsItem.mouseReleaseEvent(self, event)


class GraphWidget(QGraphicsView):
    def __init__(self, model):
        # type: (Optional[DevicesTableModel]) -> None
        QGraphicsView.__init__(self)

        self.timer_id = 0

        scene = QGraphicsScene(self)
        scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        scene.setSceneRect(-500, -300, 1000, 600)

        self.setScene(scene)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        scene.selectionChanged.connect(self._on_scene_selection_changed)

        def find_item(_is, _id):
            for _i in _is:
                if _i.node_id == _id:
                    return _i
            return None

        nodes = []
        for i in range(0, model.rowCount()):
            item = model.get_device_by_index(model.index(i, 0))
            _node = Node(self, item, True if item.is_coordinator else False)
            _node.setPos(item.position[0]*150, item.position[1]*150)
            scene.addItem(_node)
            nodes.append(_node)

        if model.graph:
            for u, v in model.graph.edges:
                _iu = find_item(nodes, u)
                _iv = find_item(nodes, v)
                edge_x = Edge(_iu, _iv)
                scene.addItem(edge_x)
                # graph.edges[u][v]['scene'] = edge_x

        self.scale(0.8, 0.8)
        self.setMinimumSize(400, 400)

    def item_moved(self):
        if not self.timer_id:
            self.timer_id = self.startTimer(int(1000 / 25))

    def keyPressEvent(self, event):
        QGraphicsView.keyPressEvent(self, event)

    def timerEvent(self, event):
        nodes = [item for item in self.scene().items() if isinstance(item, Node)]

        for node in nodes:
            node.calculate_forces()

        items_moved = False
        for node in nodes:
            if node.advance(0):
                items_moved = True

        if not items_moved:
            self.killTimer(self.timer_id)
            self.timer_id = 0

    def wheelEvent(self, event):
        self.scale_view(math.pow(2.0, -event.delta() / 240.0))

    def drawBackground(self, painter, rect):
        # Shadow.
        scene_rect = self.sceneRect()
        right_shadow = QtCore.QRectF(scene_rect.right(), scene_rect.top() + 5, 5, scene_rect.height())
        bottom_shadow = QtCore.QRectF(scene_rect.left() + 5, scene_rect.bottom(), scene_rect.width(), 5)
        if right_shadow.intersects(rect) or right_shadow.contains(rect):
            painter.fillRect(right_shadow, QtCore.Qt.darkGray)
        if bottom_shadow.intersects(rect) or bottom_shadow.contains(rect):
            painter.fillRect(bottom_shadow, QtCore.Qt.darkGray)

        # Fill.
        gradient = QtGui.QLinearGradient(scene_rect.topLeft(), scene_rect.bottomRight())
        gradient.setColorAt(0, QtCore.Qt.white)
        gradient.setColorAt(1, QtCore.Qt.lightGray)
        painter.fillRect(rect.intersected(scene_rect), QtGui.QBrush(gradient))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(scene_rect)

    def scale_view(self, scale_factor):
        factor = self.matrix().scale(scale_factor, scale_factor).mapRect(QtCore.QRectF(0, 0, 1, 1)).width()

        if factor < 0.07 or factor > 100:
            return

        self.scale(scale_factor, scale_factor)

    @Slot()
    def _on_scene_selection_changed(self):
        print('_on_scene_selection_changed')
        for _i in self.scene().selectedItems():
            print(_i.node_id)
