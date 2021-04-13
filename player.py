from PyQt5.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLayout, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget,
    QFileSystemModel, QTreeView, QLineEdit
)
from random import choice
from PyQt5 import QtGui, QtWidgets
import sys
from PyQt5.QtGui import QPixmap


class FlowLayout(QLayout):
    """A ``QLayout`` that aranges its child widgets horizontally and
    vertically.

    If enough horizontal space is available, it looks like an ``HBoxLayout``,
    but if enough space is lacking, it automatically wraps its children into
    multiple rows.

    Thanks largely to stackoverflow.

    """
    heightChanged = pyqtSignal(int)

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

        self._item_list = []

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):  # pylint: disable=invalid-name
        self._item_list.append(item)

    def addSpacing(self, size):  # pylint: disable=invalid-name
        self.addItem(QSpacerItem(size, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):  # pylint: disable=invalid-name
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):  # pylint: disable=invalid-name
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):  # pylint: disable=invalid-name,no-self-use
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):  # pylint: disable=invalid-name,no-self-use
        return True

    def heightForWidth(self, width):  # pylint: disable=invalid-name
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):  # pylint: disable=invalid-name
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):  # pylint: disable=invalid-name
        return self.minimumSize()

    def minimumSize(self):  # pylint: disable=invalid-name
        size = QSize()

        for item in self._item_list:
            minsize = item.minimumSize()
            extent = item.geometry().bottomRight()
            size = size.expandedTo(QSize(minsize.width(), extent.y()))

        margin = self.contentsMargins().left()
        size += QSize(2 * margin, 2 * margin)
        return size

    def _do_layout(self, rect, test_only=False):
        m = self.contentsMargins()
        effective_rect = rect.adjusted(+m.left(), +m.top(), -m.right(), -m.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._item_list:
            wid = item.widget()

            space_x = self.spacing()
            space_y = self.spacing()
            if wid is not None:
                space_x += wid.style().layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
                space_y += wid.style().layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        new_height = y + line_height - rect.y()
        self.heightChanged.emit(new_height)
        return new_height


class MainScreen(QtWidgets.QWidget):
    def __init__(self, directory):
        super().__init__()
        # self.body of the screen
        self.body = QVBoxLayout()
        # main area
        self.bottomframe = QFrame()
        # top area(little space)
        self.topframe = QFrame()
        self.bottomframe.setObjectName('mvue')
        self.topframe.setObjectName('topframe')
        # assign those areas to the screen(self.body)
        self.body.addWidget(self.topframe, 5)
        self.body.addWidget(self.bottomframe, 95)
        # set the spacing
        self.body.setSpacing(0)
        # define the self.fileview pane, the bottom frame split into 2
        fmodel = QFileSystemModel()
        fmodel.setRootPath(directory)
        self.fileview = QTreeView()
        self.fileview.setModel(fmodel)
        self.fileview.setRootIndex(fmodel.index(directory))
        self.fileview.setColumnWidth(0, 200)
        self.fileview.setAnimated(True)
        # file search bar
        self.wrapperwig = QFrame()
        self.twobx = QVBoxLayout(self.wrapperwig)
        self.twobx.setSpacing(0)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search Branches")
        self.twobx.addWidget(self.search_box)
        self.twobx.addWidget(self.fileview)

        # define the video thumbnail view
        self.rightview = QWidget()
        self.mainview = QHBoxLayout(self.bottomframe)
        self.rightview2 = QWidget()
        self.rightview2.hide()
        self.mainview.setContentsMargins(0,0,0,0)
        # use the flowlayout to accomodate and self balance
        self.mainframe = FlowLayout(self.rightview)

        # test thumbnail placeholder
        image = QPixmap("fm.png")
        sized_img = image.scaled(111, 111, Qt.KeepAspectRatio)

        # test data
        for i in range(25):
            btn = QLabel("Bloom")
            btn.setFixedSize(111, 111)
            btn.setPixmap(sized_img)
            self.mainframe.addWidget(btn)
        # space the thumbnails
        self.mainframe.setSpacing(10)

        # set layout for view
        self.rightview.setLayout(self.mainframe)
        # make right view scrollable
        scroller = QtWidgets.QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(self.rightview)
        scroller.setContentsMargins(0,0,0,0)
        # add the widgets to screen
        self.mainview.addWidget(self.wrapperwig, 30)
        self.mainview.addWidget(scroller, 70) # make it take 70% of screen
        self.mainview.addWidget(self.rightview2, 70)
        self.mainview.setSpacing(0)
        # adjust margin
        self.rightview.setContentsMargins(25,0,0,0)
        # set object name to make css targetting easier
        self.fileview.setObjectName('fv')
        self.rightview.setObjectName('rightview')
        self.mainview.setObjectName('mainview')
        self.mainframe.setObjectName('mainframe')
        self.wrapperwig.setObjectName('wrapper')
        self.search_box.setObjectName('search_box')
        scroller.setObjectName('mini')


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dirr):
        super().__init__()
        self.setWindowTitle('Remote CAM Controller')
        self.setMinimumSize(600, 800)
        self.widget = QtWidgets.QWidget(self)
        self.widget.setLayout(MainScreen(dirr).body)
        self.setCentralWidget(self.widget)
        self.widget.setStyleSheet("""
        #all {
            background-color: #E5E5E5;
        }
        #wrapper {
            background-color: #E5E5E5;
        }
        #mainframe {
            background-color: #E5E5E5;
            border: None;
        }
        #rightview {
            border: None;
        }
        #search_box {
            background-color: #E5E5E5;
        }
        #mini {
            margin: 0px;
            padding: 10px;
            border-top: None;
            border-left: 1px solid black;
        }
        #rightview {
            border: None;
        }
        #fv {
            border: none;
            margin-top: 0px;
            padding: 0px;
            }
        
        #topframe {
            border-bottom: 1px solid black;
            border-radius: 1px;
            padding: 0px;
            margin-bottom: 0px;
            background-color: #E6E6E6;
            }
        """)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow("D:\\tutorials\\prometheus")
    window.show()
    sys.exit(app.exec_())