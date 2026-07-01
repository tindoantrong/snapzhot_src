"""Trình phát video nhúng dùng QtMultimedia (Play/Pause, tua, âm lượng).

Tách riêng để library_window có thể import có fallback: nếu môi trường thiếu
backend QtMultimedia, library_window vẫn mở video bằng trình phát ngoài.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from .video_editor import export_clip


def _fmt_time(ms: int) -> str:
    s = max(0, ms) // 1000
    m, s = divmod(s, 60)
    return f"{m:02d}:{s:02d}"


class VideoPlayerWindow(QWidget):
    """Cửa sổ phát video nhúng tối giản kiểu Snagit."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Trình phát video")
        self.resize(800, 560)

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._video = QVideoWidget(self)
        self._player.setVideoOutput(self._video)
        # Tránh người dùng kéo slider lại gây seek vòng lặp khi tự cập nhật.
        self._seeking = False

        # Chỉnh sửa nhẹ: nguồn hiện tại + điểm cắt (end_ms == 0 nghĩa là tới hết).
        self._source_path: str | None = None
        self._trim_start_ms = 0
        self._trim_end_ms = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._video, 1)

        controls = QHBoxLayout()
        controls.setContentsMargins(8, 6, 8, 8)

        self._play_btn = QPushButton("⏸ Tạm dừng")
        self._play_btn.clicked.connect(self._toggle_play)
        controls.addWidget(self._play_btn)

        self._position_slider = QSlider(Qt.Horizontal)
        self._position_slider.setRange(0, 0)
        self._position_slider.sliderPressed.connect(self._on_seek_start)
        self._position_slider.sliderReleased.connect(self._on_seek_end)
        controls.addWidget(self._position_slider, 1)

        self._time_label = QLabel("00:00 / 00:00")
        controls.addWidget(self._time_label)

        controls.addWidget(QLabel("🔊"))
        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setFixedWidth(90)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        controls.addWidget(self._volume_slider)
        self._audio.setVolume(0.8)

        root.addLayout(controls)

        # Hàng chỉnh sửa nhẹ: đặt điểm đầu/cuối + bỏ tiếng + lưu đoạn.
        edit = QHBoxLayout()
        edit.setContentsMargins(8, 0, 8, 8)

        set_start = QPushButton("⏮ Đặt đầu")
        set_start.setToolTip("Đặt điểm bắt đầu cắt tại vị trí đang phát")
        set_start.clicked.connect(self._set_trim_start)
        edit.addWidget(set_start)

        set_end = QPushButton("Đặt cuối ⏭")
        set_end.setToolTip("Đặt điểm kết thúc cắt tại vị trí đang phát")
        set_end.clicked.connect(self._set_trim_end)
        edit.addWidget(set_end)

        self._trim_label = QLabel("Đoạn: 00:00 – 00:00")
        edit.addWidget(self._trim_label)

        edit.addStretch(1)

        self._mute_check = QCheckBox("Bỏ tiếng")
        edit.addWidget(self._mute_check)

        self._save_btn = QPushButton("💾 Lưu đoạn...")
        self._save_btn.setToolTip("Cắt đoạn đã chọn và lưu ra file mới")
        self._save_btn.clicked.connect(self._save_clip)
        edit.addWidget(self._save_btn)

        root.addLayout(edit)

        # Đồng bộ 2 chiều với player.
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)

    # ---------- API ----------
    def open(self, path: str) -> None:
        """Nạp file video, hiện cửa sổ và tự phát."""
        self._source_path = path
        self._trim_start_ms = 0
        self._trim_end_ms = 0
        self._mute_check.setChecked(False)
        self._update_trim_label()
        self._player.setSource(QUrl.fromLocalFile(path))
        self.show()
        self.raise_()
        self.activateWindow()
        self._player.play()

    # ---------- điều khiển ----------
    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlayingState
        self._play_btn.setText("⏸ Tạm dừng" if playing else "▶ Phát")

    def _on_seek_start(self) -> None:
        self._seeking = True

    def _on_seek_end(self) -> None:
        self._player.setPosition(self._position_slider.value())
        self._seeking = False

    def _on_position_changed(self, pos: int) -> None:
        if not self._seeking:
            self._position_slider.setValue(pos)
        self._update_time_label(pos, self._player.duration())

    def _on_duration_changed(self, duration: int) -> None:
        self._position_slider.setRange(0, duration)
        self._update_time_label(self._player.position(), duration)
        self._update_trim_label()

    def _update_time_label(self, pos: int, duration: int) -> None:
        self._time_label.setText(f"{_fmt_time(pos)} / {_fmt_time(duration)}")

    def _on_volume_changed(self, value: int) -> None:
        self._audio.setVolume(value / 100.0)

    # ---------- chỉnh sửa nhẹ (trim + mute + lưu) ----------
    def _effective_end_ms(self) -> int:
        """Điểm cuối thực tế: nếu chưa đặt (==0) thì lấy hết video."""
        return self._trim_end_ms if self._trim_end_ms > 0 else self._player.duration()

    def _set_trim_start(self) -> None:
        self._trim_start_ms = self._player.position()
        # Giữ điểm đầu không vượt điểm cuối đã đặt.
        if self._trim_end_ms > 0 and self._trim_start_ms > self._trim_end_ms:
            self._trim_end_ms = 0
        self._update_trim_label()

    def _set_trim_end(self) -> None:
        self._trim_end_ms = self._player.position()
        self._update_trim_label()

    def _update_trim_label(self) -> None:
        self._trim_label.setText(
            f"Đoạn: {_fmt_time(self._trim_start_ms)} – "
            f"{_fmt_time(self._effective_end_ms())}"
        )

    def _save_clip(self) -> None:
        if not self._source_path:
            return
        start, end = self._trim_start_ms, self._effective_end_ms()
        if end <= start:
            QMessageBox.warning(
                self, APP_NAME, "Đoạn cắt không hợp lệ: điểm cuối phải sau điểm đầu."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu đoạn video", "", "Video MP4 (*.mp4)"
        )
        if not path:
            return
        if not path.lower().endswith(".mp4"):
            path += ".mp4"

        mute = self._mute_check.isChecked()
        src = self._source_path
        # Chặn ghi đè đúng file nguồn: ffmpeg đọc & ghi cùng file -> hỏng video.
        if os.path.normcase(os.path.abspath(path)) == \
                os.path.normcase(os.path.abspath(src)):
            QMessageBox.warning(
                self, APP_NAME,
                "Không thể lưu đè lên chính file nguồn. Hãy chọn tên file khác."
            )
            return

        # Nhả lock file nguồn (QMediaPlayer đang giữ) trước khi ffmpeg đọc/ghi.
        was_playing = self._player.playbackState() == QMediaPlayer.PlayingState
        pos = self._player.position()
        self._player.stop()
        self._player.setSource(QUrl())
        QApplication.processEvents()

        # Re-encode có thể mất vài giây -> báo bận + khoá nút để tránh bấm chồng.
        self._save_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok = export_clip(src, path, start, end, mute=mute)
        finally:
            QApplication.restoreOverrideCursor()
            self._save_btn.setEnabled(True)

        # Mở lại nguồn để tiếp tục xem ở đúng vị trí.
        self._player.setSource(QUrl.fromLocalFile(src))
        self._player.setPosition(pos)
        if was_playing:
            self._player.play()

        if ok:
            QMessageBox.information(self, APP_NAME, "Đã lưu đoạn video.")
        else:
            QMessageBox.warning(
                self, APP_NAME, "Xuất video thất bại (cần ffmpeg của imageio-ffmpeg)."
            )

    # ---------- dọn dẹp ----------
    def closeEvent(self, event) -> None:
        # Dừng và bỏ source để không giữ lock file video.
        self._player.stop()
        self._player.setSource(QUrl())
        super().closeEvent(event)
