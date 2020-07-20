#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" This is a simple audio recorder."""

__author__ = "Hannan Khan"
__copyright__ = "Copyright 2020, Audio Recorder"
__credits__ = ["Hannan Khan"]
__license__ = "MIT"
__version__ = "1.0"
__maintainer__ = "Hannan Khan"
__email__ = "hannankhan888@gmail.com"

import sys, os, threading, time, queue
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtWidgets import QMainWindow, QApplication, QGraphicsBlurEffect
from PyQt5.QtCore import Qt
from win10toast import ToastNotifier
import sounddevice, soundfile, numpy
from dynamicLabels import ColorChangingLabel, ImageChangingLabel, CustomButton
from framelessDialog import FramelessDialog


# function needed to use pyinstaller properly:
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)


class AudioRecorder(QMainWindow):
    def __init__(self, screen_width: int, screen_height: int):
        # Set up the window's attributes.
        super(AudioRecorder, self).__init__()
        self.WIDTH = 600
        self.HEIGHT = 338
        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.X = int((self.SCREEN_WIDTH / 2) - (self.WIDTH / 2))
        self.Y = int(self.SCREEN_HEIGHT / 10) + 625
        self.setGeometry(self.X, self.Y, self.WIDTH, self.HEIGHT)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        # Set this window to not have the OS window frame.
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Audio Recorder")
        self.setWindowIcon(QtGui.QIcon(resource_path("icon.png")))


        # Set up the variables.
        self.app_name = "Audio Recorder"
        self.filepath = ""
        self.filename = ""
        self.current_font = QtGui.QFont("Segoe", 10)
        self.main_frame_blur = False
        self.recording = False
        self.paused = False
        self.stopped = False
        self.always_on_top = False
        self.mousePressPos = None
        self.mouseMovePos = None
        self.threads: [threading.Thread] = []
        self.q = queue.Queue()
        self.audio_file = None
        self.input_stream = None
        self.total_time = 0.0
        self.toaster = ToastNotifier()
        self.timer_thread = None
        self.recording_thread = None

        self._init_colors()
        self._init_default_devices()

        # Set up the overall layout and frames.
        self.main_frame = QtWidgets.QFrame()
        self.main_frame.setStyleSheet("""
        QFrame{
        background-color: rgba(35,61,77,255);
        }""")
        self.main_frame_layout = QtWidgets.QVBoxLayout()
        self.main_frame_layout.setSpacing(0)
        self.main_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.main_frame_layout.setAlignment(Qt.AlignTop)

        self.main_frame_blur = QGraphicsBlurEffect()
        self.main_frame_blur.setBlurHints(QGraphicsBlurEffect.QualityHint)
        self.main_frame_blur.setBlurRadius(10.0)
        self.main_frame_blur.setEnabled(False)
        self.main_frame.setGraphicsEffect(self.main_frame_blur)

        self._init_window_frame()
        self._init_bottom_frame()

        self.main_frame.setLayout(self.main_frame_layout)

        self.setCentralWidget(self.main_frame)
        self.show()

    def mousePressEvent(self, a0: QtGui.QMouseEvent) -> None:
        self.mousePressPos = None
        self.mouseMovePos = None
        if (a0.button() == QtCore.Qt.LeftButton) and self.window_frame.underMouse():
            self.mousePressPos = a0.globalPos()
            self.mouseMovePos = a0.globalPos()
        super(AudioRecorder, self).mousePressEvent(a0)

    def mouseMoveEvent(self, a0: QtGui.QMouseEvent) -> None:
        if (a0.buttons() == QtCore.Qt.LeftButton) and (self.window_frame.underMouse()):
            curr_pos = self.pos()
            global_pos = a0.globalPos()
            diff = global_pos - self.mouseMovePos
            new_pos = curr_pos + diff
            self.move(new_pos)
            self.mouseMovePos = global_pos
        super(AudioRecorder, self).mouseMoveEvent(a0)

    def mouseReleaseEvent(self, a0: QtGui.QMouseEvent) -> None:
        super(AudioRecorder, self).mouseReleaseEvent(a0)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        if self.window_frame.underMouse():
            self.pop_up_menu = QtWidgets.QMenu()
            self.always_on_top_action = QtWidgets.QAction("&Always on top", self)
            self.always_on_top_action.setCheckable(True)
            self.always_on_top_action.setChecked(self.always_on_top)
            self.always_on_top_action.triggered.connect(self.update_always_on_top)
            self.pop_up_menu.addAction(self.always_on_top_action)
            self.pop_up_menu.exec_(self.mapToGlobal(event.pos()))

    def _init_colors(self):
        # Charcoal
        self.normal_bg = QtGui.QColor()
        self.normal_bg.setRgb(35, 61, 77)

        # Uranian Blue
        self.highlight_bg = QtGui.QColor()
        self.highlight_bg.setRgb(163, 217, 255)

        # Heliotrope Gray
        self.normal_color = QtGui.QColor()
        self.normal_color.setRgb(187, 172, 193)

        # Slate Gray
        self.highlight_color = QtGui.QColor()
        self.highlight_color.setRgb(111, 117, 135)

    def _init_default_devices(self):
        """Gets the dictionaries of the default input and output devices."""
        self.input_device_num = sounddevice.default.device[0]
        self.output_device_num = sounddevice.default.device[1]
        self.input_device_dict = sounddevice.query_devices(device=self.input_device_num)
        self.output_device_dict = sounddevice.query_devices(device=self.output_device_num)
        self.default_sample_rate = self.input_device_dict["default_samplerate"]
        self.input_channels = self.input_device_dict["max_input_channels"]

    def _init_window_frame(self):
        self.window_frame = QtWidgets.QFrame()
        self.window_frame.setFixedHeight(40)
        """ Window_frame will have two sub frames, one for the left half, includes the
        icon and name, and one for the right half, includes the close and minimize
        buttons."""
        self.window_frame_layout = QtWidgets.QHBoxLayout()
        self.window_frame_layout.setSpacing(0)
        self.window_frame_layout.setContentsMargins(0, 0, 0, 0)

        self.window_frame_left = QtWidgets.QFrame()
        self.window_frame_right = QtWidgets.QFrame()

        self.wf_left_layout = QtWidgets.QHBoxLayout()
        self.wf_left_layout.setSpacing(0)
        self.wf_left_layout.setContentsMargins(8, 0, 0, 0)
        self.wf_left_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.wf_right_layout = QtWidgets.QHBoxLayout()
        self.wf_right_layout.setSpacing(0)
        self.wf_right_layout.setContentsMargins(0, 0, 0, 0)
        self.wf_right_layout.setAlignment(Qt.AlignRight | Qt.AlignTop)

        self.app_name_label = CustomButton(func=self.about)
        self.app_name_label.set_all_colors(self.normal_bg, self.highlight_bg, self.normal_color, self.highlight_color)
        self.app_name_label.setFont(self.current_font)
        self.app_name_label.setText(self.app_name)
        self.wf_left_layout.addWidget(self.app_name_label)

        self.minimize_button_label = CustomButton(self.minimize_app)
        self.minimize_button_label.set_all_colors(self.normal_bg, self.highlight_bg, self.normal_color,
                                                  self.highlight_color)
        self.minimize_button_label.setFont(self.current_font)
        self.minimize_button_label.setText(" _ ")
        self.wf_right_layout.addWidget(self.minimize_button_label)

        self.close_button_label = CustomButton(self.exit_app)
        self.close_button_label.set_all_colors(self.normal_bg, self.highlight_bg, self.normal_color,
                                               self.highlight_color)
        self.close_button_label.setFont(self.current_font)
        self.close_button_label.setText(" / ")
        self.wf_right_layout.addWidget(self.close_button_label)

        self.window_frame_left.setLayout(self.wf_left_layout)
        self.window_frame_right.setLayout(self.wf_right_layout)

        self.window_frame_layout.addWidget(self.window_frame_left)
        self.window_frame_layout.addWidget(self.window_frame_right)

        self.window_frame.setLayout(self.window_frame_layout)

        self.main_frame_layout.addWidget(self.window_frame)

    def _init_bottom_frame(self):
        self.bottom_frame = QtWidgets.QFrame()
        self.bottom_frame_layout = QtWidgets.QVBoxLayout()
        self.bottom_frame_layout.setAlignment(Qt.AlignCenter | Qt.AlignTop)
        self.bottom_frame_layout.setSpacing(15)
        self.bottom_frame_layout.setContentsMargins(0, 15, 0, 0)

        # Add the frame containing the current Information.
        self.current_recording_label = ColorChangingLabel(self.normal_bg, self.highlight_bg, self.normal_color,
                                                          self.highlight_color, False)
        self.current_recording_label.setAlignment(Qt.AlignCenter)
        self.current_recording_label.setFont(self.current_font)
        self.current_recording_label.setText("Click the mic to start recording")

        self.current_time_label = ColorChangingLabel(self.normal_bg, self.highlight_bg, self.normal_color,
                                                     self.highlight_color, False)
        self.current_time_label.setAlignment(Qt.AlignCenter)
        self.current_time_label.setFont(self.current_font)
        self.current_time_label.setText("00:00:00")

        self.bottom_frame_layout.addWidget(self.current_recording_label)
        self.bottom_frame_layout.addWidget(self.current_time_label)

        # We add the frame containing the buttons.
        self.buttons_frame = QtWidgets.QFrame()
        self.buttons_frame_layout = QtWidgets.QHBoxLayout()
        self.buttons_frame_layout.setSpacing(100)
        self.buttons_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_frame_layout.setAlignment(Qt.AlignCenter)

        self.record_button_label = ImageChangingLabel(resource_path("mic_1.png"), resource_path("mic_2.png"), self.start_recording)
        self.pause_button_label = ImageChangingLabel(resource_path("pause_1.png"), resource_path("pause_2.png"), self.pause_recording)
        self.stop_button_label = ImageChangingLabel(resource_path("stop_1.png"), resource_path("stop_2.png"), self.stop_recording)
        self.buttons_frame_layout.addWidget(self.record_button_label)
        self.buttons_frame_layout.addWidget(self.pause_button_label)
        self.buttons_frame_layout.addWidget(self.stop_button_label)
        self.buttons_frame.setLayout(self.buttons_frame_layout)

        # add the label for the settings icon
        self.settings_frame = QtWidgets.QFrame()
        self.settings_frame_layout = QtWidgets.QHBoxLayout()
        self.settings_frame_layout.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.settings_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_label = ImageChangingLabel(resource_path("settings_1.png"), resource_path("settings_2.png"), self.settings, 35, 35)
        self.settings_frame_layout.addWidget(self.settings_label)
        self.settings_frame.setLayout(self.settings_frame_layout)

        self.bottom_frame_layout.addWidget(self.buttons_frame)
        self.bottom_frame_layout.addWidget(self.settings_frame)

        self.bottom_frame.setLayout(self.bottom_frame_layout)
        self.main_frame_layout.addWidget(self.bottom_frame)

    def set_current_recording_text(self, text: str = "", recording: bool = False, paused: bool = False,
                                   stopped: bool = False):
        if not text:
            text = self.filename
        if recording:
            self.current_recording_label.setText(f"Recording: {text}")
        elif paused:
            self.current_recording_label.setText(f"Paused: {text}")
        elif stopped:
            self.current_recording_label.setText(f"Stopped: {text}")
        else:
            self.current_recording_label.setText(f"Current Recording: {text}")

    def update_always_on_top(self):
        """ Updates the always on top value, as well as updating the current window
        flags to enable always on top behavior."""

        if self.always_on_top:
            self.always_on_top = False
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.show()
        elif not self.always_on_top:
            self.always_on_top = True
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.show()

    def _start_timer_thread(self):
        start_time = time.time()
        self.timer_thread = threading.Thread(target=self.start_timer, args=(start_time,))
        self.timer_thread.daemon = True
        self.timer_thread.start()
        self.threads.append(self.timer_thread)

    def start_timer(self, start_time):
        diff_time = 0.0
        self.total_time = 0.0
        while True:
            if self.recording and not self.paused:
                time.sleep(1)
                curr_time = time.time()
                diff_time = curr_time - start_time
                diff_time = diff_time + self.total_time
                self.set_current_time_text(diff_time)
            elif self.stopped:
                self.set_current_time_text(0)
                break
            else:
                start_time = time.time()
                self.total_time = diff_time

    def set_current_time_text(self, diff_time: float):
        self.current_time_label.setText(time.strftime("%H:%M:%S", time.gmtime(diff_time)))

    def callback(self, indata: numpy.ndarray, frames: int, time, status) -> None:
        if self.recording:
            self.q.put(indata.copy())

    def _start_recording_thread(self):
        self.recording_thread = threading.Thread(target=self.open_continue_recording)
        self.recording_thread.daemon = True
        self.threads.append(self.recording_thread)
        self.recording_thread.start()

    def open_continue_recording(self):
        with soundfile.SoundFile(self.filepath, mode='x', samplerate=int(self.default_sample_rate),
                                 channels=self.input_channels, subtype="PCM_24", format="WAV") as self.audio_file:
            with sounddevice.InputStream(samplerate=self.default_sample_rate, device=self.input_device_num,
                                         channels=self.input_channels, callback=self.callback):
                while True:
                    if self.recording:
                        self.audio_file.write(self.q.get())
                    elif self.paused:
                        pass
                    elif self.stopped:
                        break

    def start_recording(self):
        # TODO: add error message to remind to stop, if we are already recording something.
        # TODO: reset the filename and filepath vars each time we start recording.
        if not self.recording:
            self.filepath = QtWidgets.QFileDialog.getSaveFileName(self, "Save Audio As", os.getcwd(), "Audio Files (*.wav)")[0]
            if self.filepath:
                self.filename = os.path.basename(self.filepath)
                self.record_button_label.invert_active_state()
                self.recording = True
                self.paused = False
                self.stopped = False
                self.set_current_recording_text(recording=True)
                self._start_timer_thread()
                self._start_recording_thread()
                self.toaster.show_toast(self.app_name, f"Recording Started.\n{self.filename} Created.", None, 3, True)
        elif self.recording:
            warning_dialog = FramelessDialog(self, "A recording is already underway.", self.normal_bg, self.highlight_bg, self.normal_color, self.highlight_color, "Error", self.current_font)
            self.main_frame_blur.setEnabled(True)
            warning_dialog.exec_()
            self.main_frame_blur.setEnabled(False)

    def pause_recording(self):
        if self.paused:
            self.pause_button_label.invert_active_state()
            self.recording = True
            self.paused = False
            self.record_button_label.invert_active_state()
            self.set_current_recording_text(recording=True)
        elif self.recording:
            self.pause_button_label.invert_active_state()
            self.recording = False
            self.record_button_label.invert_active_state()
            self.paused = True
            self.set_current_recording_text(paused=True)
        else:
            warning_dialog = FramelessDialog(self, "You must first start a\nrecording to be able to pause.", self.normal_bg, self.highlight_bg, self.normal_color, self.highlight_color, "Error", self.current_font)
            self.main_frame_blur.setEnabled(True)
            warning_dialog.exec_()
            self.main_frame_blur.setEnabled(False)

    def stop_recording(self):
        self.stopped = True
        if self.recording:
            self.toaster.show_toast(self.app_name, f"Recording Stopped.\n{self.filename} Saved.", None, 3, True)
            self.record_button_label.invert_active_state()
            self.set_current_recording_text(stopped=True)
        elif self.paused:
            self.toaster.show_toast(self.app_name, f"Recording Stopped.\n{self.filename} Saved.", None, 3, True)
            self.pause_button_label.invert_active_state()
            self.set_current_recording_text(stopped=True)
        self.recording = False
        self.paused = False
        if self.audio_file:
            self.audio_file.close()
        self.audio_file = None
        self.total_time = 0.0
        self.filepath = ""
        self.filename = ""
        self.set_current_time_text(0)

    def settings(self):
        self.settings_label.invert_active_state()
        io_text = "Input:\n%s\nOutput:\n%s\n" % (self.input_device_dict["name"], self.output_device_dict["name"])
        settings_dialog = FramelessDialog(self, io_text, self.normal_bg, self.highlight_bg,
                                          self.normal_color, self.highlight_color, "Settings", self.current_font)
        self.main_frame_blur.setEnabled(True)
        result = settings_dialog.exec_()
        if result == 0:
            self.main_frame_blur.setEnabled(False)
            self.settings_label.invert_active_state()

    def about(self):
        about_dialog = FramelessDialog(self, "Created by Hannan Khan", self.normal_bg, self.highlight_bg,
                                       self.normal_color, self.highlight_color, "About", self.current_font)
        linked_in_label = QtWidgets.QLabel()
        linked_in_label.setFont(self.current_font)
        linked_in_label.setText('<a href="https://www.linkedin.com/in/hannankhan888/" style="color: rgba(187, 172, '
                                '193, 255)">LinkedIn</a>')
        linked_in_label.setOpenExternalLinks(True)
        github_label = QtWidgets.QLabel()
        github_label.setFont(self.current_font)
        github_label.setText('<a href="https://github.com/hannankhan888" style="color: rgba(187, 172, 193, '
                             '255)">Github</a>')
        github_label.setOpenExternalLinks(True)
        about_dialog.middle_frame_layout.addWidget(linked_in_label)
        about_dialog.middle_frame_layout.addWidget(github_label)
        self.main_frame_blur.setEnabled(True)
        result = about_dialog.exec_()
        if result == 0:
            self.main_frame_blur.setEnabled(False)

    def minimize_app(self):
        self.showMinimized()

    def exit_app(self):
        for thread in self.threads:
            thread.join()
        sys.exit(0)


def main():
    app = QApplication(sys.argv)
    screen_size = app.primaryScreen().size()
    GUI = AudioRecorder(screen_size.width(), screen_size.height())
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
