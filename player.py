from PyQt6.QtCore import (
    QPoint, QRect, QSize, Qt,
    pyqtSignal, QAbstractListModel,
    QModelIndex, QTimer
)
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLayout, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget,
    QTreeView, QLineEdit,
    QListView, QStackedWidget, QSlider,
    QDateEdit, QListWidget, QListWidgetItem
)
from random import choice
from PyQt6 import QtGui, QtWidgets
import sys
from time import sleep
from PyQt6.QtGui import QIcon, QPixmap, QFileSystemModel
import os
import vlc


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
                    QSizePolicy.ControlTypes.PushButton, QSizePolicy.ControlTypes.PushButton, Qt.Orientations.Horizontal)
                space_y += wid.style().layoutSpacing(
                    QSizePolicy.ControlTypes.PushButton, QSizePolicy.ControlTypes.PushButton, Qt.Orientations.Vertical)

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


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, directory):
        super().__init__()
        self.setWindowTitle('Remote CAM Controller')
        self.setGeometry(0, 0, 900, 900)
        self.set_ui(directory)

    def set_ui(self, directory):
        self.widget = QtWidgets.QWidget(self)
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
        # instanciate video
        self.instance = vlc.Instance()
        self.media = None
        # create an empty vlc media player
        self.mediaplayer = self.instance.media_player_new()
        self.is_paused = False
        # set the spacing
        self.body.setSpacing(0)
        # define the self.fileview pane, the bottom frame split into 2
        self.fmodel = QFileSystemModel()
        self.fmodel.setRootPath(directory)
        self.fileview = QTreeView()
        self.fileview.setModel(self.fmodel)
        self.fileview.setRootIndex(self.fmodel.index(directory))
        self.fileview.setColumnWidth(0, 200)
        self.fileview.setAnimated(True)
        self.fileview.clicked.connect(self.print_path)
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
        mv = QWidget()
        self.backbutton = QPushButton()
        self.backbutton.clicked.connect(self.go_back)
        icon = QIcon("assets/icon.png")
        self.backbutton.setIcon(icon)
        self.switch_button = QPushButton("screen 2")
        #bl.setText("Break Bad!!")
        
        
        ll = QLabel()
        #ll.setPixmap(im)
        #lb.clicked.connect(self.print_path)
        self.switch_button.clicked.connect(self.print_path)
        

        # test data
        thumb_list = ["assets/grafik 5.png", "assets/grafik 6.png", "assets/grafik 8.png", "assets/grafik 7.png", "assets/grafik 9.png"]
        for i in thumb_list:
            im = QPixmap(i)
            sized_img = im.scaled(111, 111)
            btn = QLabel("Bloom")
            btn.setFixedSize(111, 111)
            btn.setPixmap(sized_img)
            self.mainframe.addWidget(btn)
        # space the thumbnails
        self.mainframe.setSpacing(10)
        self.mainframe.addWidget(self.switch_button)

        # screen 2 configs
        # create a frame that would be later splitted into two
        self.page_frame = QVBoxLayout()
        self.rightview2.setLayout(self.page_frame)

        # set layout for view
        self.rightview.setLayout(self.mainframe)
        # make right view scrollable
        scroller = QtWidgets.QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(self.rightview)
        scroller.setContentsMargins(0,0,0,0)
        scroller2 = QtWidgets.QScrollArea()
        scroller2.setWidgetResizable(True)
        scroller2.setWidget(self.rightview2)
        # add the widgets to screen
        self.stackedWidget = QStackedWidget()
        self.stackedWidget.addWidget(scroller)
        self.stackedWidget.addWidget(scroller2)
        self.mainview.addWidget(self.wrapperwig, 30)
        self.mainview.addWidget(self.stackedWidget, 70) # make it take 70% of screen
        #self.mainview.addWidget(self.rightview2, 70)
        self.mainview.setSpacing(0)
        
        # topview for screen2
        self.screen_frame = QWidget()
        # main player screen 
        self.player_frame = QFrame()
        self.player_frame.setStyleSheet("background-color: black;")
        # slider frame below screen
        self.slider_frame_layout = QVBoxLayout()
        self.slider_frame = QFrame()
        self.slider_frame.setLayout(self.slider_frame_layout)
        self.list_label = QListWidget()
        self.list_label.setFlow(QListView.Flow(0))
        for i in range(8):
            itm = QListWidgetItem(self.list_label)
            btn = QLabel()
            btn.setFixedSize(111, 111)
            btn.setPixmap(sized_img)
            #btn.setLayout(bxr)
            #bxr.addWidget(btn)
            itm.setSizeHint(btn.sizeHint())
        
            self.list_label.addItem(itm)
            self.list_label.setItemWidget(itm, btn)
        self.list_label.setContentsMargins(10,10,10,10)
        self.list_label.setFixedHeight(155)

        self.date_range_lay = QHBoxLayout()
        self.date_range = QDateEdit()
        self.date_range_lay.addStretch()
        self.date_range_lay.addWidget(self.date_range)
        self.slider_frame_layout.addLayout(self.date_range_lay)
        self.slider_frame_layout.addWidget(self.list_label)
        self.listSlider = QSlider(Qt.Orientations.Horizontal)
        self.listSlider.setRange(0, 10)
        self.slider_frame_layout.addWidget(self.listSlider)
        self.label_btn = QHBoxLayout()
        self.video_label = QLabel("<h1>CALABAR - Marian Road - ATM Gallery 2!</h1>")
        self.label_btn.addWidget(self.backbutton)
        self.label_btn.addStretch()
        self.label_btn.addWidget(self.video_label)
        self.label_btn.addStretch()
        self.positionSlider = QSlider(Qt.Orientations.Horizontal)
        self.positionSlider.setMaximum(1000)
        self.positionSlider.sliderMoved.connect(self.set_position)
        self.positionSlider.sliderPressed.connect(self.set_position)
        #self.positionSlider.setFocusPolicy(Qt.NoFocus)
        self.hbuttonbox = QHBoxLayout()
        self.speakerbutton = QPushButton()
        self.chatbutton = QPushButton()
        self.messagebutton = QPushButton()
        self.playbutton = QPushButton()
        self.fwdbutton = QPushButton()
        self.rwdbutton = QPushButton()
        self.enlargebutton = QPushButton()
        self.enlargebutton.clicked.connect(self.go_full_screen)
        self.menubutton = QPushButton()
        self.speakericon = QIcon("assets/speaker.png")
        self.chat_icon = QIcon("assets/chat.png")
        self.message_icon = QIcon("assets/message.png")
        self.play_icon = QIcon("assets/play.png")
        self.pause_icon = QIcon("assets/pus.png")
        self.fwd_icon = QIcon("assets/fwd.png")
        self.rwd_icon = QIcon("assets/rewind.png")
        self.enlarge_icon = QIcon("assets/enlarge.png")
        self.menu_icon = QIcon("assets/3dots.png")
        self.speakerbutton.setIcon(self.speakericon)
        self.speakerbutton.clicked.connect(self.set_mute_status)
        self.chatbutton.setIcon(self.chat_icon)
        self.messagebutton.setIcon(self.message_icon)
        self.playbutton.setIcon(self.play_icon)
        self.playbutton.clicked.connect(self.play_pause)
        self.fwdbutton.setIcon(self.fwd_icon)
        self.fwdbutton.clicked.connect(self.fast_forward)
        self.rwdbutton.setIcon(self.rwd_icon)
        self.rwdbutton.clicked.connect(self.rewind)
        self.enlargebutton.setIcon(self.enlarge_icon)
        self.menubutton.setIcon(self.menu_icon)
        self.hbuttonbox.addWidget(self.speakerbutton)
        self.hbuttonbox.addWidget(self.chatbutton)
        self.hbuttonbox.addWidget(self.messagebutton)
        
        self.hbuttonbox.addStretch()
        self.hbuttonbox.addWidget(self.rwdbutton)
        self.hbuttonbox.addWidget(self.playbutton)
        self.hbuttonbox.addWidget(self.fwdbutton)
        self.hbuttonbox.addStretch()
        self.hbuttonbox.addWidget(self.enlargebutton)
        self.hbuttonbox.addWidget(self.menubutton)

        self.screen_frame_layout = QVBoxLayout()
        self.screen_frame_layout.addLayout(self.label_btn)
        self.screen_frame_layout.addWidget(self.player_frame, Qt.Alignment.AlignCenter)
        self.screen_frame_layout.addWidget(self.positionSlider)
        self.screen_frame_layout.addLayout(self.hbuttonbox)
        self.screen_frame_layout.addStretch(5)
        self.screen_frame.setLayout(self.screen_frame_layout)
        self.page_frame.addWidget(self.screen_frame, 60)
        self.page_frame.addWidget(self.slider_frame, 40)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
    
        # adjust margin
        self.rightview.setContentsMargins(25,0,0,0)
        # set object name to make css targetting easier
        self.widget.setLayout(self.body)
        self.setCentralWidget(self.widget)
        self.fileview.setObjectName('fv')
        self.rightview.setObjectName('rightview')
        self.mainview.setObjectName('mainview')
        self.mainframe.setObjectName('mainframe')
        self.wrapperwig.setObjectName('wrapper')
        self.search_box.setObjectName('search_box')
        scroller.setObjectName('mini')
        scroller2.setObjectName('mini2')
        self.speakerbutton.setObjectName("playb")
        self.playbutton.setObjectName("playb")
        self.chatbutton.setObjectName("playb")
        self.messagebutton.setObjectName("playb")
        self.rwdbutton.setObjectName("playb")
        self.fwdbutton.setObjectName("playb")
        self.enlargebutton.setObjectName("playb")
        self.menubutton.setObjectName("playb")
        self.backbutton.setObjectName("nav")

        self.widget.setStyleSheet("""
        #all {
            background-color: #E5E5E5;
        }
        #wrapper {
            background-color: #E5E5E5;
        }
        #playb {
            border: None;
        }
        #nav {
            border: 2px solid #000000;
            height: 40px;
            width: 40px;
        }
        #mainframe {
           
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
        #mini2 {
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
        QPushButton {
            width: 30;
            height: 30;
        }
        QSlider::groove:horizontal {
        border: 1px solid #999999;
        height: 10px;

        border-radius: 9px;
        }

        QSlider::handle:horizontal {
        width: 18px;
        background-color: white;
        border: 1.5px solid #0078D4;
        border-radius: 9px;
        height: 78px;
        margin: -5px 0;
        }

        QSlider::add-page:qlineargradient {
        background: lightgrey;
        border-top-right-radius: 9px;
        border-bottom-right-radius: 9px;
        border-top-left-radius: 0px;
        border-bottom-left-radius: 0px;
        }

        QSlider::sub-page:qlineargradient {
        background: #0078D4;
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
        border-top-left-radius: 9px;
        border-bottom-left-radius: 9px;
        }
        """)
    
    def play_pause(self):
        """
        Toggle play/pause status
        """
        
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.playbutton.setIcon(self.play_icon)
            self.is_paused = True
            self.timer.stop()
            
        else:
            self.mediaplayer.play()
            sleep(0.5)
            self.playbutton.setIcon(self.pause_icon)
            self.timer.start()
    
    def set_mute_status(self):
        """
        Set the volume
        """
        if self.mediaplayer.audio_get_mute():
            self.mediaplayer.audio_set_mute(0)
        else:
            self.mediaplayer.audio_set_mute(1)

    def go_full_screen(self):
        if self.screen_frame.isFullScreen():
            self.screen_frame.setLayout(self.screen_frame_layout)
            self.page_frame.addWidget(self.screen_frame, 60)
            #self.df.setParent(self.deet2)
            self.screen_frame.showNormal()
        else:
            self.screen_frame.setParent(None)
            self.screen_frame.showFullScreen()
    
    def go_back(self):
        if self.stackedWidget.currentIndex() == 1:
            self.stackedWidget.setCurrentIndex(0)
            if self.mediaplayer.is_playing():
                self.mediaplayer.pause()
                self.playbutton.setIcon(self.play_icon)
                self.is_paused = True
                self.timer.stop()

    def print_path(self, index):
        path = self.fmodel.fileInfo(index).absoluteFilePath()
        if os.path.isdir(path):
            if self.stackedWidget.currentIndex() == 1:
                self.stackedWidget.setCurrentIndex(0)
                if self.mediaplayer.is_playing():
                    self.mediaplayer.pause()
                    self.playbutton.setIcon(self.play_icon)
                    self.is_paused = True
                    self.timer.stop()
            return
        if self.stackedWidget.currentIndex() == 0:
            self.stackedWidget.setCurrentIndex(1)
        self.media = self.instance.media_new(path)
        self.mediaplayer.set_media(self.media)
        self.mediaplayer.set_hwnd(int(self.player_frame.winId()))
        self.media.parse()
        self.video_label.setText(f"<h1>{self.media.get_meta(0)}</h1>")
        self.play_pause()
    
    def rewind(self):
        self.timer.stop()
        cur = self.mediaplayer.get_position()
        self.mediaplayer.set_position(cur - 0.013)
        self.timer.start()
    
    def fast_forward(self):
        self.timer.stop()
        cur = self.mediaplayer.get_position()
        self.mediaplayer.set_position(cur + 0.023)
        self.timer.start()
    
    def set_position(self):
        """Set the movie position according to the position slider.
        """

        # The vlc MediaPlayer needs a float value between 0 and 1, Qt uses
        # integer variables, so you need a factor; the higher the factor, the
        # more precise are the results (1000 should suffice).

        # Set the media position to where the slider was dragged
        self.timer.stop()
        pos = self.positionSlider.value()
        self.mediaplayer.set_position(pos / 1000.0)
        self.timer.start()
    
    def stop(self):
        """Stop player
        """
        self.mediaplayer.stop()
        self.playbutton.setIcon(self.play_icon)


    def update_ui(self):
        media_pos = int(self.mediaplayer.get_position() * 1000)
        self.positionSlider.setValue(media_pos)
        if not self.mediaplayer.is_playing():
            self.timer.stop()

            # After the video finished, the play button stills shows "Pause",
            # which is not the desired behavior of a media player.
            # This fixes that "bug".
            if not self.is_paused:
                self.stop()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow("D:\\white collar")
    window.show()
    sys.exit(app.exec())
