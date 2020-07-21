#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This is a simple audio recorder that uses PyAudio and wave to record .wav files."""

__author__ = "Hannan Khan"
__copyright__ = "Copyright 2020, Audio Recorder"
__credits__ = ["Hannan Khan"]
__license__ = "MIT"
__version__ = "1.0"
__maintainer__ = "Hannan Khan"
__email__ = "hannankhan888@gmail.com"

import os
import sys
import threading
import time
import wave

import pyaudio
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QApplication, QGraphicsBlurEffect
from win10toast import ToastNotifier

from dynamicLabels import ColorChangingLabel, ImageChangingLabel, CustomButton
from framelessDialog import FramelessDialog

CHUNK = 1024
SAMPLE_FORMAT = pyaudio.paInt16
CHANNELS = 0
FPS = 44100


# function needed to use PyInstaller properly:
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)


class AudioRecorder(QMainWindow):
    """This class implements a minimalist AudioRecorder.
    Functions of the recorder include starting recording, pausing, and stopping (same
    as saving).
    Each time a recording is started, a separate timer thread and recording thread are
    created for that particular recording. When stop is pressed, these threads terminate."""

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
        self.setWindowIcon(QtGui.QIcon(resource_path("images/icon.ico")))

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
        self.total_time = 0.0
        self.toaster = ToastNotifier()
        self.timer_thread = None
        self.recording_thread = None
        self.stream = None
        self.frames = []

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
        """Gets the dictionaries of the default input and output devices, and set the
        default values for them."""

        self.p = pyaudio.PyAudio()
        self.input_device_dict = pyaudio.PyAudio.get_default_input_device_info(self.p)
        self.input_device_idx = self.input_device_dict['index']
        self.input_device_name = self.input_device_dict["name"]
        self.input_channels = self.input_device_dict['maxInputChannels']
        self.default_sample_rate = self.input_device_dict['defaultSampleRate']

        self.output_device_dict = pyaudio.PyAudio.get_default_output_device_info(self.p)
        self.output_device_num = self.output_device_dict['index']
        self.output_device_name = self.output_device_dict["name"]

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

        self.record_button_label = ImageChangingLabel(resource_path("images/mic_1.png"), resource_path(
            "images/mic_2.png"),
                                                      self.start_recording)
        self.pause_button_label = ImageChangingLabel(resource_path("images/pause_1.png"), resource_path(
            "images/pause_2.png"),
                                                     self.pause_recording)
        self.stop_button_label = ImageChangingLabel(resource_path("images/stop_1.png"), resource_path(
            "images/stop_2.png"),
                                                    self.stop_recording)
        self.buttons_frame_layout.addWidget(self.record_button_label)
        self.buttons_frame_layout.addWidget(self.pause_button_label)
        self.buttons_frame_layout.addWidget(self.stop_button_label)
        self.buttons_frame.setLayout(self.buttons_frame_layout)

        # add the label for the settings icon
        self.settings_frame = QtWidgets.QFrame()
        self.settings_frame_layout = QtWidgets.QHBoxLayout()
        self.settings_frame_layout.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.settings_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_label = ImageChangingLabel(resource_path("images/settings_1.png"), resource_path(
            "images/settings_2.png"),
                                                 self.settings, 35, 35)
        self.settings_frame_layout.addWidget(self.settings_label)
        self.settings_frame.setLayout(self.settings_frame_layout)

        self.bottom_frame_layout.addWidget(self.buttons_frame)
        self.bottom_frame_layout.addWidget(self.settings_frame)

        self.bottom_frame.setLayout(self.bottom_frame_layout)
        self.main_frame_layout.addWidget(self.bottom_frame)

    def set_current_recording_text(self, text: str = "", recording: bool = False, paused: bool = False,
                                   stopped: bool = False):
        """Sets the current recording text based on which variable is activated."""

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
        """This function starts a timer thread each time a recording starts. Each recording
        has a timer thread and a recording thread. When paused the timer thread will
        emulate sleep by sleeping for .2 seconds, and updating the current and total
        recording time."""

        start_time = time.time()
        self.timer_thread = threading.Thread(target=self.start_timer, args=(start_time,))
        self.timer_thread.setDaemon(True)
        self.timer_thread.setName("Timer Thread")
        self.timer_thread.start()
        self.threads.append(self.timer_thread)

    def start_timer(self, start_time):
        """Timer thread runs this function. When self.stopped is True, this thread will
        return and terminate."""

        diff_time = 0.0
        self.total_time = 0.0
        while True:
            if self.paused:
                start_time = time.time()
                self.total_time = diff_time
                time.sleep(.2)
            if self.recording:
                time.sleep(1)
                diff_time = time.time() - start_time + self.total_time
                self.set_current_time_text(diff_time)
            if self.stopped:
                self.set_current_time_text(0)
                return

    def set_current_time_text(self, diff_time: float):
        """Sets the current time text with correct time conversion."""

        self.current_time_label.setText(time.strftime("%H:%M:%S", time.gmtime(diff_time)))

    def _start_recording_thread(self):
        """This function will create and start the recording thread. One recording thread
        is created for each file that is recorded."""

        self.recording_thread = threading.Thread(target=self.open_continue_recording)
        self.recording_thread.setDaemon(True)
        self.recording_thread.setName("Recording Thread")
        self.threads.append(self.recording_thread)
        self.recording_thread.start()

    def open_continue_recording(self):
        """This function actually does the recording. It will open a stream and enter a
        while True loop. If paused, it will stop the stream and sleep for .2 seconds. If
        recording, it will check to see if the stream is started, and then record. When
        stopping, the loop will stop the stream, close it, and return, causing the associated
        recording thread to terminate."""

        self.stream = self.p.open(format=SAMPLE_FORMAT, channels=self.input_channels,
                                  rate=FPS, frames_per_buffer=CHUNK, input=True)
        while True:
            if self.recording:
                if self.stream.is_stopped():
                    self.stream.start_stream()
                data = self.stream.read(1024)
                self.frames.append(data)
            elif self.paused:
                if not self.stream.is_stopped():
                    self.stream.stop_stream()
                else:
                    time.sleep(.2)
            elif self.stopped:
                self.stream.stop_stream()
                self.stream.close()
                return

    def start_recording(self):
        """This function is called when you press the record button. It will check for user
        errors, and provides error messages, as well as a file selection dialog for getting
        a new file's name. When the recording is started, it will notify via the win10Toast
        module."""

        if self.recording:
            warning_dialog = FramelessDialog(self, "A recording is already underway.", self.normal_bg,
                                             self.highlight_bg, self.normal_color, self.highlight_color, "Error",
                                             self.current_font)
            self.main_frame_blur.setEnabled(True)
            warning_dialog.exec_()
            self.main_frame_blur.setEnabled(False)
        elif not self.recording:
            self.filename = ""
            self.filepath = ""
            self.filepath = QtWidgets.QFileDialog.getSaveFileName(self, "Save Audio As",
                                                                  os.getcwd(), "Audio Files (*.wav)")[0]
            if self.filepath:
                self.filename = os.path.basename(self.filepath)
                self.record_button_label.invert_active_state()
                self.recording = True
                self.paused = False
                self.stopped = False
                self.set_current_recording_text(recording=True)
                self._start_timer_thread()
                self._start_recording_thread()
                self.toaster.show_toast(self.app_name, f"Recording Started:\n{self.filename} created.",
                                        resource_path("images/icon.ico"), 3, True)

    def pause_recording(self):
        """This function is called when User clicks the pause button. If paused, it will set
        variables so that the currently running threads may resume again. Otherwise, it
        pause the threads (again, by only setting the vars and letting the threads take
        care of the rest).."""

        if self.paused:
            self.pause_button_label.invert_active_state()
            self.recording = True
            self.paused = False
            self.record_button_label.invert_active_state()
            self.set_current_recording_text(recording=True)
        elif self.recording:
            self.recording = False
            self.paused = True
            self.pause_button_label.invert_active_state()
            self.record_button_label.invert_active_state()
            self.set_current_recording_text(paused=True)
        else:
            warning_dialog = FramelessDialog(self, "You must first start a\nrecording to be able to pause.",
                                             self.normal_bg, self.highlight_bg, self.normal_color, self.highlight_color,
                                             "Error", self.current_font)
            self.main_frame_blur.setEnabled(True)
            warning_dialog.exec_()
            self.main_frame_blur.setEnabled(False)

    def stop_recording(self):
        """This function is called when you stop recording. It will check that you have a
        recording that you have at least started already. Otherwise, it will save the recording
        via wave, an in-built python module for wav files. This function will also take care of
        resetting the variables for a new recording to take place."""

        self.stopped = True
        if not self.recording and not self.paused:
            warning_dialog = FramelessDialog(self, "Please start recording first.", self.normal_bg, self.highlight_bg,
                                             self.normal_color, self.highlight_color, "Error", self.current_font)
            self.main_frame_blur.setEnabled(True)
            warning_dialog.exec_()
            self.main_frame_blur.setEnabled(False)
        else:
            if self.recording:
                self.record_button_label.invert_active_state()
            elif self.paused:
                self.pause_button_label.invert_active_state()
            self.recording = False
            self.paused = False
            with wave.open(self.filename, "wb") as wf:
                wf.setnchannels(self.input_channels)
                wf.setsampwidth(self.p.get_sample_size(SAMPLE_FORMAT))
                wf.setframerate(FPS)
                wf.writeframes(b''.join(self.frames))
                self.frames.clear()
            self.toaster.show_toast(self.app_name, f"Recording Stopped:\n{self.filename} saved.",
                                    resource_path("images/icon.ico"), 3, True)
            self.set_current_recording_text(stopped=True)
            self.total_time = 0.0
            self.filepath = ""
            self.filename = ""
            self.set_current_time_text(0)
        for thread in self.threads:
            if thread.is_alive():
                thread.join(.5)
        self.threads.clear()

    def settings(self):
        """This function takes care of the settings dialog."""

        self.settings_label.invert_active_state()
        io_text = "Input:\n%s\nOutput:\n%s\n" % (self.input_device_name, self.output_device_name)
        settings_dialog = FramelessDialog(self, io_text, self.normal_bg, self.highlight_bg,
                                          self.normal_color, self.highlight_color, "Settings", self.current_font)
        self.main_frame_blur.setEnabled(True)
        result = settings_dialog.exec_()
        if result == 0:
            self.main_frame_blur.setEnabled(False)
            self.settings_label.invert_active_state()

    def about(self):
        """This function takes care of the about dialog."""

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
        """This function will take care of possible User error while exiting, as one can only
        save a file by pressing stop. It will also close the PyAudio object, join all remaining
        possible threads, and finally exit."""

        if self.recording or self.paused:
            warning_dialog = FramelessDialog(self, "You must press stop in\norder to save your recording.",
                                             self.normal_bg, self.highlight_bg, self.normal_color,self.highlight_color,
                                             "Error", self.current_font)
            if self.recording:
                warning_dialog.message_label.setText("Recording in progress.\nPlease press Stop.")
            self.main_frame_blur.setEnabled(True)
            warning_dialog.exec_()
            self.main_frame_blur.setEnabled(False)
            return
        self.p.terminate()
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
