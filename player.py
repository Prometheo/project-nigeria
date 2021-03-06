from PyQt6.QtCore import (
    QPoint, QRect, QSize, Qt,
    pyqtSignal, QAbstractListModel,
    QModelIndex, QTimer, QThread, QDir, QRect
)
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLayout, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget,
    QTreeView, QLineEdit,
    QListView, QStackedWidget, QSlider,
    QDateEdit, QListWidget, QListWidgetItem,
    QToolBar
)
from random import choice, randint
from PyQt6 import QtGui, QtWidgets
import sys
from time import sleep
from functools import partial
from PyQt6.QtGui import (
    QIcon, QPixmap, QFileSystemModel,
    QAction
)
import os
import vlc
import tempfile
import ffmpeg

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


class Slider(QtWidgets.QSlider):
    # seek = pyqtSignal()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButtons.LeftButton:
            e.accept()
            x = e.position().x()
            value = (self.maximum() - self.minimum()) * x / self.width() + self.minimum()
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
            #self.seek.emit()
        else:
            return super().mousePressEvent(self, e)


class ThumbFrame(QLabel):
    clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, a0):
        self.clicked.emit()


def generate_thumbnail(in_filename, out_filename):
    try:
        probe = ffmpeg.probe(in_filename.path)
        time = float(probe['streams'][0]['duration']) // 2
        width = probe['streams'][0]['width']
        (
            ffmpeg
            .input(in_filename, ss=time)
            .filter('scale', width, -1)
            .output(out_filename, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return out_filename
    except Exception as e:
        pass


def clearLayout(layout):
    for i in reversed(range(layout.count())):
        layout.itemAt(i).widget().deleteLater()

def generate_media_list(directory: str, cur_media=None, include=False):
    media_list = sorted([file.path for file in os.scandir(directory)], key=os.path.getctime, reverse=True)
    if cur_media:
        try:
            media_index = media_list.index(cur_media)
            if include:
                media_list = media_list[media_index:]
            else:
                media_list = media_list[media_index+1:]
        except ValueError:
            pass
    for file in media_list:
        yield file


class ThumbnailThread(QThread):
    update_widget = pyqtSignal(tuple, str, int)
    update_list_label = pyqtSignal(tuple, str)
    def __init__(self, video_dir, thumb_dir):
        QThread.__init__(self)
        self.video_dir = video_dir
        self.thumb_dir = thumb_dir
        #self.update_widget = pyqtSignal(str)
    
    def __del__(self):
        self.wait()
    
    def _generate_video_thumbnail(self, video_file):
        identifier = randint(1, 100000000)
        name = f'{identifier}.png'
        thumb_file = os.path.join(self.thumb_dir.name, name)
        thumb_nail = generate_thumbnail(video_file, thumb_file)
        return thumb_nail

    def run(self):
        folderz = len(list(os.scandir(self.video_dir)))
        vids = [vid for vid in os.scandir(self.video_dir) if os.path.isfile(vid) ]
        if vids:
            try:
                thub_nail = self._generate_video_thumbnail(vids[0])
                self.update_widget.emit((thub_nail, os.path.normcase(self.video_dir)), self.video_dir, folderz)
            except IndexError:
                pass
        for file in os.scandir(self.video_dir):
            if os.path.isdir(file):
                sorted_videos = sorted(os.scandir(file), key=os.path.getctime, reverse=True)
                try:
                    thub_nail = self._generate_video_thumbnail(sorted_videos[0])
                    self.update_widget.emit((thub_nail, os.path.normpath(file.path)), self.video_dir, folderz)
                except IndexError:
                    self.update_widget.emit((None, os.path.normpath(file.path)), self.video_dir, folderz)



class ListThumbnailThread(QThread):
    update_list_label = pyqtSignal(tuple, str, int)
    def __init__(self, video_dir, thumb_dir):
        QThread.__init__(self)
        self.video_dir = video_dir
        self.thumb_dir = thumb_dir
        #self.update_widget = pyqtSignal(str)
    
    def __del__(self):
        self.wait()
    
    def _generate_video_thumbnail(self, video_file):
        identifier = randint(1, 100000000)
        name = f'{identifier}.png'
        thumb_file = os.path.join(self.thumb_dir.name, name)
        thumb_nail = generate_thumbnail(video_file, thumb_file)
        return thumb_nail

    def run(self):
        videoz = [vid for vid in os.scandir(self.video_dir) if os.path.isfile(vid) ]
        for file in sorted(os.scandir(self.video_dir), key=os.path.getctime, reverse=True):
            if os.path.isfile(file):
                thub_nail = self._generate_video_thumbnail(file)
                self.update_list_label.emit((thub_nail, file.path), self.video_dir, len(videoz))


class FileSystemModel(QFileSystemModel):
    def hasChildren(self, parent):
        file_info = self.fileInfo(parent)
        _dir = QDir(file_info.absoluteFilePath())
        return bool(_dir.entryList(self.filter()))


file_model = FileSystemModel()


class MyTreeView(QTreeView):
    #expanded = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setExpandsOnDoubleClick(False)
        #self.expanded.connect(self.rexpand)

    def mousePressEvent(self, e):
        pos = e.position()
        clickedIndex = self.indexAt(pos.toPoint())
        if clickedIndex.isValid():
            vrect = self.visualRect(clickedIndex)
            itemIdentation = vrect.x() - self.visualRect(self.rootIndex()).x()
            if e.position().x() < itemIdentation:
                path = file_model.fileInfo(clickedIndex).absoluteFilePath()
                if not list(os.walk(path))[0][2]:
                    if not self.isExpanded(clickedIndex):
                        self.expand(clickedIndex)
                        s
                    else:
                        self.collapse(clickedIndex)
                return
            return super().mousePressEvent(e)



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Remote CAM Controller')
        self.setGeometry(0, 0, 900, 900)
        self.set_ui()

    def set_ui(self):
        self.widget = QtWidgets.QWidget(self)
        # self.body of the screen
        self.body = QVBoxLayout()
        # main area
        self.bottomframe = QFrame()
        toolbar = QToolBar("&Folder Selector")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        select_folder_action = QAction(QIcon("assets\\folder.png"), "Select Folder", self)
        select_folder_action.setStatusTip("This is your button")
        select_folder_action.triggered.connect(self.onMyToolBarButtonClick)
        # about_action = QAction(QIcon("assets\\help.png"), "About", self)
        # info_action = QAction(QIcon("assets\\info.png"), "How To", self)
        toolbar.addAction(select_folder_action)
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        # help_menu = menu.addMenu("&Help")
        file_menu.addAction(select_folder_action)
        # help_menu.addActions([about_action, info_action])
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
        #self.media_list = vlc.MediaList()
        # self.media_list = []
        self.is_paused = False
        # set a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        # keep track od directories
        self.cur_dir = None
        # set the spacing
        self.body.setSpacing(0)
        # define the self.fileview pane, the bottom frame split into 2
        #file_model = QFileSystemModel()
        #file_model.setFilter(QDir.Dirs|QDir.NoDotAndDotDot)
        #file_model.setRootPath('')
        self.fileview = QTreeView()
        
        self.fileview.setModel(file_model)
        self.fileview.setColumnWidth(0, 200)
        self.fileview.setAnimated(True)
        self.fileview.setHeaderHidden(True)
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
        #self.rightview2.hide()
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
        
        # space the thumbnails
        self.mainframe.setSpacing(10)

        image = QPixmap("assets/grafik 5.png")
        sized_img = image.scaled(111, 111)

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
        # for i in range(8):
        #     itm = QListWidgetItem(self.list_label)
        #     btn = QLabel()
        #     btn.setFixedSize(111, 111)
        #     btn.setPixmap(sized_img)
        #     #btn.setLayout(bxr)
        #     #bxr.addWidget(btn)
        #     itm.setSizeHint(btn.sizeHint())
        
        #     self.list_label.addItem(itm)
        #     self.list_label.setItemWidget(itm, btn)
        self.list_label.setContentsMargins(10,10,10,10)
        

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
        self.positionSlider = Slider(Qt.Orientations.Horizontal)
        self.positionSlider.setMaximum(1000)
        self.positionSlider.sliderMoved.connect(self.set_position)
        # self.positionSlider.sliderPressed.connect(self.set_position)
        #self.positionSlider.seek.connect(self.set_position)
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
        # self.hbuttonbox.addWidget(self.chatbutton)
        # self.hbuttonbox.addWidget(self.messagebutton)
        
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
           border: 5px solid #000000;
        }
        #plate::hover {
            border: 3px solid #000000;
            
        }
        #rightview {
            border: None;
        }
        #search_box {
            background-color: white;
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
        
            height: 1px;
            border-radius: 0px;
        }

        QSlider::handle:horizontal {
            width: 11px;
            background-color: white;
            border: 0.5px solid #0078D4;
            border-radius: 5px;
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
            self.is_paused = False
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
            self.page_frame.addWidget(self.slider_frame, 40)
            #self.df.setParent(self.deet2)
            self.screen_frame.showNormal()
        else:
            self.screen_frame.setParent(None)
            self.screen_frame.setStyleSheet(
                '''
                #playb {
                    border: None;
                }
                QSlider::groove:horizontal {
        
                height: 1px;
                border-radius: 0px;
                }

                QSlider::handle:horizontal {
                    width: 11px;
                    background-color: white;
                    border: 0.5px solid #0078D4;
                    border-radius: 5px;
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
                }'''
            )
            self.screen_frame.showFullScreen()
    def onMyToolBarButtonClick(self):
        dialog = QtWidgets.QFileDialog()
        folder_path = dialog.getExistingDirectory(None, 'select the content Folder')
        file_model.setRootPath(folder_path)
        file_model.setFilter(QDir.Filters.AllDirs|QDir.Filters.NoDotAndDotDot)

        self.fileview.setRootIndex(file_model.index(folder_path))
        # for col in range(1, file_model.columnCount()):
        #     self.fileview.hideColumn(col)
        

    def go_back(self):
        if self.screen_frame.isFullScreen():
            self.screen_frame.setLayout(self.screen_frame_layout)
            self.page_frame.addWidget(self.screen_frame, 60)
            self.screen_frame.showNormal()
            return
        if self.stackedWidget.currentIndex() == 1:
            self.stackedWidget.setCurrentIndex(0)
            if self.mediaplayer.is_playing():
                self.mediaplayer.stop()
                self.playbutton.setIcon(self.play_icon)
                #self.is_paused = True
                self.positionSlider.setValue(0)
                self.timer.stop()
    
    def play_thumbnail(self, dd):
        if self.stackedWidget.currentIndex() == 0:
            self.stackedWidget.setCurrentIndex(1)
        
        path = dd[1]
        cam_label = dd[1].split('\\')
        #path_folder = os.path.dirname(path)
        
        self.media_list = generate_media_list(path)
        # for video in os.scandir(path):
        #     print(video)
        #     self.media_list.add_media(self.instance.media_new(video))
        
        #self.mediaplayer.set_media_list(self.media_list)
        #m_inst = self.mediaplayer.get_media_player()
        print(dd[1])
        try:
            self.media = self.instance.media_new(self.media_list.__next__())
        except StopIteration:
            return
        self.mediaplayer.set_media(self.media)
        self.mediaplayer.set_hwnd(int(self.player_frame.winId()))
        self.media.parse()
        self.video_label.setText(f"<h1>{cam_label[-1]}</h1>")
        try:
            if self.generate_thread.isRunning():
                self.generate_thread.terminate()
        except:
            pass
        thumb_dir = self.temp_dir
        path_folder = os.path.dirname(path)
        self.generate_thread = ListThumbnailThread(path,thumb_dir)
        self.generate_thread.update_list_label.connect(self.update_list_label)
        self.generate_thread.start()

    def play_list_thumbnail(self, dd):
        if self.stackedWidget.currentIndex() == 0:
            self.stackedWidget.setCurrentIndex(1)
        
        path = dd[1]
        cam_label = dd[1].split('\\')
        path_folder = os.path.dirname(path)
        
        self.media_list = generate_media_list(path_folder, path, include=True)
        # for video in os.scandir(path):
        #     print(video)
        #     self.media_list.add_media(self.instance.media_new(video))
        
        #self.mediaplayer.set_media_list(self.media_list)
        #m_inst = self.mediaplayer.get_media_player()
        self.media = self.instance.media_new(path)
        self.mediaplayer.set_media(self.media)
        self.mediaplayer.set_hwnd(int(self.player_frame.winId()))
        self.media.parse()
        # self.video_label.setText(f"<h1>{cam_label[-1]}</h1>")
        # try:
        #     if self.generate_thread.isRunning():
        #         self.generate_thread.terminate()
        # except:
        #     pass
        # thumb_dir = self.temp_dir
        # path_folder = os.path.dirname(path)
        # self.generate_thread = ListThumbnailThread(path,thumb_dir)
        # self.generate_thread.update_list_label.connect(self.update_list_label)
        # self.generate_thread.start()

    def update_list_label(self, obj, dir, length):
        if self.cur_dir != dir:
            self.list_label.clear()
        elif self.cur_dir == dir:
            if self.list_label.count() == length:
                return
        self.cur_dir = dir
        im = QPixmap(obj[0])
        sized_img = im.scaled(111, 111, Qt.AspectRatioMode.IgnoreAspectRatio)
        itm = QListWidgetItem(self.list_label)
        btn = ThumbFrame("Bloom")
        btn.setAccessibleDescription(obj[1])
        btn.clicked.connect(partial(self.play_list_thumbnail, obj))
        btn.setFixedSize(111, 111)
        btn.setPixmap(sized_img)
        itm.setSizeHint(btn.sizeHint())
        wrapper_layout = QVBoxLayout()
        wrapper_widget = QWidget()
        wrapper_layout.addWidget(btn)
        wrapper_widget.setLayout(wrapper_layout)
        wrapper_widget.setObjectName('plate')
        self.list_label.addItem(itm)
        self.list_label.setItemWidget(itm, btn)
        self.list_label.setFixedHeight(btn.height())
        # for i in range(8):
        #     itm = QListWidgetItem(self.list_label)
        #     btn = QLabel()
        #     btn.setFixedSize(111, 111)
        #     btn.setPixmap(sized_img)
        #     #btn.setLayout(bxr)
        #     #bxr.addWidget(btn)
        #     itm.setSizeHint(btn.sizeHint())
        
        #     self.list_label.addItem(itm)
        #     self.list_label.setItemWidget(itm, btn)

    def update_widget(self, obj, dir, length):
        if self.cur_dir != dir:
            clearLayout(self.mainframe)
        elif self.cur_dir == dir:
            if self.mainframe.count() == length:
                return
        self.cur_dir = dir
        if obj[0]:
            im = QPixmap(obj[0])
            sized_img = im.scaled(111, 111, Qt.AspectRatioMode.IgnoreAspectRatio)
            btn = ThumbFrame("Bloom")
            btn.setAccessibleDescription(obj[1])
            btn.clicked.connect(partial(self.play_thumbnail, obj))
            btn.setFixedSize(111, 111)
            btn.setPixmap(sized_img)
        else:
            btn = ThumbFrame("No data")
            btn.setAlignment(Qt.Alignment.AlignCenter)
            btn.setAccessibleDescription(obj[1])
            btn.clicked.connect(partial(self.play_thumbnail, obj))
            btn.setFixedSize(111, 111)
        # btn.setStyleSheet("::hover"
        #                     "{"
        #                     "border : 5px solid green;"
        #                     "}")
        cam_label = obj[1].split('\\')
        #print(cam_label)
        label = QLabel(cam_label[-1])
        wrapper_layout = QVBoxLayout()
        wrapper_widget = QWidget()
        wrapper_layout.addWidget(btn, 70, Qt.Alignment.AlignCenter)
        wrapper_layout.addWidget(label, 30, Qt.Alignment.AlignCenter)
        wrapper_widget.setLayout(wrapper_layout)
        wrapper_widget.setObjectName('plate')
        self.mainframe.addWidget(wrapper_widget)
    
    def block_thread_signal(self):
        self.fileview.blockSignals(True)
    
    def release_thread_signal(self):
        self.fileview.blockSignals(False)

    def print_path(self, index):
        path = file_model.fileInfo(index).absoluteFilePath()
        if os.path.isdir(path):
            if self.stackedWidget.currentIndex() == 1:
                self.stackedWidget.setCurrentIndex(0)
                if self.mediaplayer.is_playing():
                    self.mediaplayer.pause()
                    self.playbutton.setIcon(self.play_icon)
                    self.is_paused = True
                    self.timer.stop()
            try:
                if self.generate_thread.isRunning():
                    self.generate_thread.terminate()
            except:
                pass
            thumb_dir = self.temp_dir
            self.generate_thread = ThumbnailThread(path,thumb_dir)
            self.generate_thread.update_widget.connect(self.update_widget)
            self.generate_thread.started.connect(self.block_thread_signal)
            self.generate_thread.finished.connect(self.release_thread_signal)
            self.generate_thread.start()
                
            return
        if self.stackedWidget.currentIndex() == 0:
            self.stackedWidget.setCurrentIndex(1)
        
        # path_folder = os.path.dirname(path)
        # self.media_list = generate_media_list(path_folder, path)
        # self.media = self.instance.media_new(path)
        # self.mediaplayer.set_media(self.media)
        # self.mediaplayer.set_hwnd(int(self.player_frame.winId()))
        # self.media.parse()
        # self.video_label.setText(f"<h1>{self.media.get_meta(0)}</h1>")
        # self.play_pause()
        # try:
        #     if self.generate_thread.isRunning():
        #         self.generate_thread.terminate()
        # except:
        #     pass
        # thumb_dir = self.temp_dir
        
        # self.generate_thread = ListThumbnailThread(path_folder,thumb_dir)
        # self.generate_thread.update_list_label.connect(self.update_list_label)
        # self.generate_thread.start()
    
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
        self.mediaplayer.pause()
        pos = self.positionSlider.value()
        self.mediaplayer.set_position(pos / 1000.0)
        sleep(0.5)
        self.mediaplayer.play()
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
            #self.timer.stop()

            # After the video finished, the play button stills shows "Pause",
            # which is not the desired behavior of a media player.
            # This fixes that "bug".
            if not self.is_paused:
                try:
                    self.media = self.instance.media_new(self.media_list.__next__())
                    self.mediaplayer.set_media(self.media)
                    self.mediaplayer.set_hwnd(int(self.player_frame.winId()))
                    self.media.parse()
                    #self.video_label.setText(f"<h1>{self.media.get_meta(0)}</h1>")
                    self.play_pause()
                except StopIteration:
                    self.stop()


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
