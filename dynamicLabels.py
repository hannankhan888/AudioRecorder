import sys, os
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import Qt


# function needed to use pyinstaller properly:
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)


class ColorChangingLabel(QtWidgets.QLabel):
    def __init__(self, normal_bg: QtGui.QColor = None, highlight_bg: QtGui.QColor = None,
                 normal_color: QtGui.QColor = None, highlight_color: QtGui.QColor = None, highlightable: bool = True):
        super(ColorChangingLabel, self).__init__()
        self.normal_bg = normal_bg
        self.highlight_bg = highlight_bg
        self.normal_color = normal_color
        self.highlight_color = highlight_color
        self.highlightable = highlightable
        self.setStyleSheet("""
        QLabel{
        color: rgba(187, 172, 193, 255);
        }""")

    def enterEvent(self, a0: QtCore.QEvent) -> None:
        if self.highlightable:
            self.setStyleSheet(self.get_style_sheet(True))
        super(ColorChangingLabel, self).enterEvent(a0)

    def leaveEvent(self, a0: QtCore.QEvent) -> None:
        if self.highlightable:
            self.setStyleSheet(self.get_style_sheet(False))
        super(ColorChangingLabel, self).leaveEvent(a0)

    def get_rgb_string(self, idx: int = 0) -> str:
        """Returns the RGB portion of the string to be used in the styleSheet.
        idx = 0 means normal bg
        1 == highlight bg
        2 == normal color
        3 == highlight color"""

        if idx == 0:
            color = QtGui.QColor(self.normal_bg)
        elif idx == 1:
            color = QtGui.QColor(self.highlight_bg)
        elif idx == 2:
            color = QtGui.QColor(self.normal_color)
        elif idx == 3:
            color = QtGui.QColor(self.highlight_color)
        else:
            return "Error. Wrong idx value in get_rgb_string"

        red = str(color.red())
        green = str(color.green())
        blue = str(color.blue())

        return "".join([red, ", ", green, ", ", blue])

    def get_style_sheet(self, highlighted: bool = False):
        """:returns the stylesheet for a label based on if it is highlighted or not."""

        normal_bg_rgb = self.get_rgb_string(0)
        highlight_bg_rgb = self.get_rgb_string(1)
        normal_color_rgb = self.get_rgb_string(2)
        highlight_color_rgb = self.get_rgb_string(3)

        if highlighted:
            styleSheet = """
            QLabel {
            color: rgba(%s, 255);
            background-color: rgba(%s, 255);
            }""" % (highlight_color_rgb, highlight_bg_rgb)
            return styleSheet
        elif not highlighted:
            styleSheet = """
            QLabel {
            color: rgba(%s, 255);
            background-color: rgba(%s, 255);
            }""" % (normal_color_rgb, normal_bg_rgb)
            return styleSheet

    def set_all_colors(self, normal_bg, highlight_bg, normal_color, highlight_color):
        self.normal_bg = normal_bg
        self.highlight_bg = highlight_bg
        self.normal_color = normal_color
        self.highlight_color = highlight_color


class ImageChangingLabel(QtWidgets.QLabel):
    def __init__(self, image_1: str = "", image_2: str = "", func: classmethod = None, resized_x: int = 128,
                 resized_y: int = 128):
        super(ImageChangingLabel, self).__init__()
        self.leftButtonClicked = False
        self.active = False

        self.func = func
        self.img_1_pixmap = QtGui.QPixmap(resource_path(image_1)).scaled(resized_x, resized_y, Qt.KeepAspectRatio)
        self.img_2_pixmap = QtGui.QPixmap(resource_path(image_2)).scaled(resized_x, resized_y, Qt.KeepAspectRatio)
        self.setPixmap(self.img_1_pixmap)

    def enterEvent(self, a0: QtCore.QEvent) -> None:
        if not self.active:
            self.setPixmap(self.img_2_pixmap)
        super(ImageChangingLabel, self).enterEvent(a0)

    def leaveEvent(self, a0: QtCore.QEvent) -> None:
        if not self.active:
            self.setPixmap(self.img_1_pixmap)
        super(ImageChangingLabel, self).leaveEvent(a0)

    def mousePressEvent(self, ev: QtGui.QMouseEvent) -> None:
        self.leftButtonClicked = False
        if ev.button() == Qt.LeftButton:
            self.leftButtonClicked = True
        super(ImageChangingLabel, self).mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        if self.func:
            if self.leftButtonClicked and (ev.button() == Qt.LeftButton):
                self.func()
        super(ImageChangingLabel, self).mouseReleaseEvent(ev)

    def update(self) -> None:
        if self.active:
            self.setPixmap(self.img_2_pixmap)
        else:
            self.setPixmap(self.img_1_pixmap)
        super(ImageChangingLabel, self).update()

    def invert_active_state(self):
        self.active = (not self.active)
        self.update()


class CustomButton(ColorChangingLabel):
    def __init__(self, func: classmethod = None):
        super(CustomButton, self).__init__()
        self.leftButtonClicked = False
        self.func = func

    def mousePressEvent(self, ev: QtGui.QMouseEvent) -> None:
        self.leftButtonClicked = False
        if ev.button() == Qt.LeftButton:
            self.leftButtonClicked = True
        super(CustomButton, self).mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QtGui.QMouseEvent) -> None:
        if self.func:
            if (ev.button() == Qt.LeftButton) and (self.leftButtonClicked is True):
                self.func()
        super(CustomButton, self).mouseReleaseEvent(ev)
