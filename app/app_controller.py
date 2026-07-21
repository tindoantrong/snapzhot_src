"""Điều phối trung tâm: kết nối Capture, Library, Editor và khay hệ thống.

Luồng chính:
- Chụp vùng / toàn màn hình  -> lưu vào thư viện -> mở Editor.
- Editor "Lưu vào thư viện"   -> cập nhật ảnh (nếu sửa ảnh cũ) hoặc thêm mới.
- Thư viện "Mở trong Editor"  -> nạp ảnh vào Editor.
"""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QObject, QRect, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication, QImage
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
)

from . import APP_NAME, __version__, updater
from .capture import capture_manager
from .capture.countdown_overlay import CountdownOverlay
from .capture.region_selector import RegionSelector
from .capture.window_selector import WindowSelector, window_capture_available
from .common import autostart
from .common.assets import app_icon
from .common.config import load_config, save_config
from .common.paths import videos_dir
from .editor.editor_window import EditorWindow
from .library.library_manager import LibraryManager
from .library.library_window import LibraryWindow
from .recording.audio_recorder import AudioRecorder, audio_available, mux_audio_video
from .recording.record_bar import RecordBar
from .recording.recorder import VideoRecorder

import logging

_log = logging.getLogger(__name__)
# Watchdog tick mỗi 5 giây — phát hiện processing_thread chết và ghi log chẩn đoán.
_HOTKEY_WATCHDOG_INTERVAL_MS = 5_000


_UPDATE_QSS = """
QDialog { background:#2B2D31; }
QLabel { color:#C8C8C8; font-size:13px; }
QLabel#title { color:#FFFFFF; font-size:15px; font-weight:bold; }
QTextEdit {
    background:#1E1F22; color:#C8C8C8;
    border:1px solid #3A3D42; border-radius:6px;
}
QPushButton {
    background:#3A3D42; color:#FFFFFF; border:none;
    border-radius:6px; padding:7px 16px;
}
QPushButton:hover { background:#44474D; }
QPushButton#primary { background:#1E90FF; }
QPushButton#primary:hover { background:#3AA0FF; }
QPushButton:disabled { background:#2F3136; color:#7A7D82; }
/* Nút primary khi DISABLE: ID-selector #primary thắng :disabled về specificity nên
   phải có rule riêng (ID+pseudo) để hóa xám đúng, tránh hiểu nhầm còn bấm được. */
QPushButton#primary:disabled { background:#2F3136; color:#7A7D82; }
"""


class _UpdateCheckWorker(QObject):
    """Chạy `updater.check_for_updates` (chặn tới 8s) trên luồng nền.

    Phát `finished(UpdateInfo)` về luồng GUI; không bao giờ raise (updater đã nuốt
    mọi lỗi → luôn trả UpdateInfo), nên tray không bị đơ khi đang kiểm tra mạng.
    """

    finished = Signal(object)  # UpdateInfo

    def __init__(self, current_version: str, manifest_url: str) -> None:
        super().__init__()
        self._current = current_version
        self._url = manifest_url

    @Slot()
    def run(self) -> None:
        info = updater.check_for_updates(self._current, self._url)
        self.finished.emit(info)


class _UpdateDialog(QDialog):
    """Hộp thoại cập nhật theme tối, đổi nội dung theo 5 trạng thái.

    Trạng thái: idle / checking / available (Tải về) / latest / error (Thử lại).
    Việc kiểm tra thực hiện ở luồng nền — dialog chỉ phát `check_requested` và
    nhận kết quả qua `show_result`.
    """

    check_requested = Signal()

    def __init__(self, current_version: str) -> None:
        super().__init__()
        self._current = current_version
        self._download_url = ""
        self._mode = "idle"

        self.setWindowTitle(f"Cập nhật {APP_NAME}")
        self.setMinimumWidth(380)
        self.setStyleSheet(_UPDATE_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(12)

        self.title = QLabel(APP_NAME)
        self.title.setObjectName("title")
        layout.addWidget(self.title)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.notes = QTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setFixedHeight(110)
        self.notes.hide()
        layout.addWidget(self.notes)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.close_btn = QPushButton("Đóng")
        self.close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.close_btn)
        self.action_btn = QPushButton("Kiểm tra cập nhật")
        self.action_btn.setObjectName("primary")
        self.action_btn.clicked.connect(self._on_action)
        btn_row.addWidget(self.action_btn)
        layout.addLayout(btn_row)

        self.show_idle()

    def _on_action(self) -> None:
        # Khi có bản mới: nút là "Tải về" → mở URL. Ngược lại: chạy kiểm tra mới.
        if self._mode == "available" and self._download_url:
            if not updater.is_safe_update_url(self._download_url):
                QMessageBox.warning(
                    self,
                    "URL cập nhật không hợp lệ",
                    "URL tải về không hợp lệ hoặc không an toàn và đã bị chặn.\n"
                    "Chỉ chấp nhận liên kết https://github.com/…",
                )
                return
            QDesktopServices.openUrl(QUrl(self._download_url))
            return
        self.show_checking()
        self.check_requested.emit()

    def show_idle(self) -> None:
        self._mode = "idle"
        self.status.setText(f"Phiên bản hiện tại: {self._current}")
        self.notes.hide()
        self.action_btn.setText("Kiểm tra cập nhật")
        self.action_btn.setEnabled(True)
        self.action_btn.setToolTip("")
        self.close_btn.setText("Đóng")

    def show_checking(self) -> None:
        self._mode = "checking"
        self.status.setText("Đang kiểm tra…")
        self.notes.hide()
        self.action_btn.setEnabled(False)

    def show_result(self, info) -> None:
        if info.error:
            self._mode = "error"
            self.status.setText(info.error)
            self.notes.hide()
            self.action_btn.setText("Thử lại")
            self.action_btn.setEnabled(True)
            self.action_btn.setToolTip("")
            return
        if info.available:
            self._mode = "available"
            self._download_url = info.url
            self.status.setText(
                f"Đã có phiên bản mới: {info.latest}\n"
                f"(bạn đang dùng {info.current})"
            )
            if info.notes:
                self.notes.setPlainText(info.notes)
                self.notes.show()
            else:
                self.notes.hide()
            self.action_btn.setText("Tải về")
            if updater.is_safe_update_url(info.url):
                self.action_btn.setEnabled(True)
                self.action_btn.setToolTip("")
            elif info.url:
                self.action_btn.setEnabled(False)
                self.action_btn.setToolTip("URL cập nhật không hợp lệ/không an toàn, đã chặn.")
            else:
                self.action_btn.setEnabled(False)
                self.action_btn.setToolTip("Manifest không có liên kết tải về.")
            self.close_btn.setText("Để sau")
        else:
            self._mode = "latest"
            self.status.setText("Bạn đang dùng phiên bản mới nhất.")
            self.notes.hide()
            self.action_btn.setText("Kiểm tra lại")
            self.action_btn.setEnabled(True)
            self.action_btn.setToolTip("")


class AppController(QObject):
    # Tín hiệu nội bộ để gọi chụp/quay từ luồng hotkey về luồng GUI an toàn.
    request_region = Signal()
    request_video_toggle = Signal()
    request_escape = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.library = LibraryManager()

        self.editor = EditorWindow()
        self.editor.save_to_library.connect(self._on_editor_save)
        # Nút chụp/quay trong Editor dùng chung luồng với thư viện.
        self.editor.request_capture_region.connect(self.capture_region)
        self.editor.request_capture_fullscreen.connect(self.capture_fullscreen)
        self.editor.request_video.connect(self.toggle_video_recording)
        # Nhấp thumbnail "Ảnh gần đây" trong Editor → mở lại đúng ảnh đó.
        self.editor.open_capture_requested.connect(self._open_capture_in_editor)
        # Yêu cầu xoá ảnh từ dải "Ảnh gần đây".
        self.editor.delete_capture_requested.connect(self._on_delete_capture)
        # Nút "Về thư viện" trong Editor → hiện màn hình thư viện.
        self.editor.request_library.connect(self.show_library)

        self.library_window = LibraryWindow(self.library)
        self.library_window.open_in_editor.connect(self._open_capture_in_editor)
        self.library_window.request_capture_region.connect(self.capture_region)
        self.library_window.request_capture_fullscreen.connect(self.capture_fullscreen)
        self.library_window.request_video.connect(self.toggle_video_recording)

        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self._on_region_selected)

        # Chụp theo cửa sổ (Windows + pywin32). Dùng chung luồng với chụp vùng.
        self.window_selector = WindowSelector()
        self.window_selector.window_selected.connect(self._on_region_selected)

        # Chụp hẹn giờ: overlay đếm ngược + bộ đếm 1 giây.
        self.countdown_overlay = CountdownOverlay()
        self._delay_remaining = 0
        self._delay_timer = QTimer(self)
        self._delay_timer.setInterval(1000)
        self._delay_timer.timeout.connect(self._on_delay_tick)

        # Quay video: luôn quay toàn màn hình (không chọn vùng) + thanh điều khiển.
        self.record_bar = RecordBar()
        self.record_bar.pause_toggled.connect(self._on_pause_toggled)
        self.record_bar.stopped.connect(self.stop_recording)
        self._recorder: VideoRecorder | None = None
        self._recording = False
        self._recording_region: dict | None = None
        self._esc_handle = None
        self._remove_region_hook = None  # cleanup handle cho hook_key PrtScn (tránh accumulate)
        # Watchdog phát hiện thread chết + periodic hard-restart phòng silent hook removal.
        self._hotkey_watchdog: QTimer | None = None
        self._hotkey_watchdog_tick: int = 0

        # Âm thanh micro (cộng thêm; suy giảm nhẹ nhàng nếu thiếu thiết bị).
        self._audio_recorder: AudioRecorder | None = None
        self._record_audio_enabled = (
            bool(self.config.get("record_audio", True)) and audio_available()
        )
        self._final_path: str | None = None      # đường dẫn file cuối
        self._video_tmp_path: str | None = None   # video tạm khi quay kèm tiếng
        self._audio_tmp_path: str | None = None   # wav tạm

        # Kiểm tra cập nhật: dialog + luồng nền (giữ ref tránh GC).
        self._update_dialog: _UpdateDialog | None = None
        self._update_thread: QThread | None = None
        self._update_worker: _UpdateCheckWorker | None = None

        self._build_tray()

        # Kết nối hàng đợi để chụp/quay được kích hoạt từ luồng khác (hotkey).
        self.request_region.connect(self.capture_region, Qt.QueuedConnection)
        self.request_video_toggle.connect(self.toggle_video_recording, Qt.QueuedConnection)
        self.request_escape.connect(self._on_escape, Qt.QueuedConnection)

    # ---------- khay hệ thống ----------
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(app_icon())
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()

        for text, slot in (
            ("Chụp vùng chọn", self.capture_region),
            ("Chụp toàn màn hình", self.capture_fullscreen),
            ("Chụp cửa sổ", self.capture_window),
        ):
            act = QAction(text, self)
            act.triggered.connect(slot)
            menu.addAction(act)

        # Chụp hẹn giờ: submenu với vài mốc thời gian.
        delay_menu = menu.addMenu("Chụp hẹn giờ")
        default_delay = int(self.config.get("capture_delay_seconds", 3))
        for sec in sorted({default_delay, 3, 5}):
            act = QAction(f"Chụp toàn màn hình sau {sec} giây", self)
            act.triggered.connect(lambda _=False, s=sec: self.capture_fullscreen_delayed(s))
            delay_menu.addAction(act)
        menu.addSeparator()

        self._record_action = QAction("Quay video toàn màn hình", self)
        self._record_action.triggered.connect(self.toggle_video_recording)
        menu.addAction(self._record_action)

        # Bật/tắt thu âm micro khi quay (disable nếu không có thiết bị).
        self._audio_action = QAction("Quay kèm âm thanh micro", self)
        self._audio_action.setCheckable(True)
        self._audio_action.setChecked(self._record_audio_enabled)
        self._audio_action.setEnabled(audio_available())
        if not audio_available():
            self._audio_action.setToolTip("Không tìm thấy thiết bị thu âm.")
        self._audio_action.toggled.connect(self._on_audio_toggled)
        menu.addAction(self._audio_action)

        self._startup_action = QAction("Khởi động cùng Windows", self)
        self._startup_action.setCheckable(True)
        self._startup_action.setEnabled(autostart.is_supported())
        self._startup_action.setChecked(autostart.is_enabled())
        self._startup_action.toggled.connect(self._on_startup_toggled)
        menu.addAction(self._startup_action)

        self._hotkey_action = QAction("Cài đặt phím tắt chụp vùng…", self)
        self._hotkey_action.triggered.connect(self._open_hotkey_settings)
        menu.addAction(self._hotkey_action)

        self._reregister_act = QAction("Đăng ký lại phím tắt chụp", self)
        self._reregister_act.triggered.connect(self._manual_reregister_hotkeys)
        menu.addAction(self._reregister_act)
        menu.addSeparator()

        lib_act = QAction("Mở thư viện", self)
        lib_act.triggered.connect(self.show_library)
        menu.addAction(lib_act)

        ed_act = QAction("Mở Editor", self)
        ed_act.triggered.connect(self.editor.show)
        menu.addAction(ed_act)
        menu.addSeparator()

        # Nhãn phiên bản (disabled) + kiểm tra cập nhật.
        about_act = QAction(f"Về {APP_NAME} (phiên bản {__version__})", self)
        about_act.setEnabled(False)
        menu.addAction(about_act)

        update_act = QAction("Kiểm tra cập nhật…", self)
        update_act.triggered.connect(self._open_update_dialog)
        menu.addAction(update_act)
        menu.addSeparator()

        quit_act = QAction("Thoát", self)
        quit_act.triggered.connect(QGuiApplication.quit)
        menu.addAction(quit_act)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:  # click trái
            self.show_library()

    # ---------- cập nhật phiên bản ----------
    def _open_update_dialog(self) -> None:
        """Mở (hoặc đưa lên trước) hộp thoại kiểm tra cập nhật."""
        if self._update_dialog is not None:
            self._update_dialog.raise_()
            self._update_dialog.activateWindow()
            return
        dlg = _UpdateDialog(__version__)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.check_requested.connect(self._start_update_check)
        dlg.finished.connect(self._on_update_dialog_finished)
        self._update_dialog = dlg
        dlg.show()

    def _start_update_check(self) -> None:
        """Chạy check_for_updates ở luồng nền (chặn tới 8s → không trên GUI)."""
        if self._update_thread is not None:
            return  # đã có một lần kiểm tra đang chạy
        url = self.config.get("update_manifest_url", updater.UPDATE_MANIFEST_URL)
        thread = QThread(self)
        worker = _UpdateCheckWorker(__version__, url)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_update_checked)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_update_thread)
        self._update_thread = thread
        self._update_worker = worker
        thread.start()

    @Slot(object)
    def _on_update_checked(self, info) -> None:
        # Dialog có thể đã đóng khi kết quả về → bỏ qua an toàn.
        if self._update_dialog is not None:
            self._update_dialog.show_result(info)

    def _clear_update_thread(self) -> None:
        self._update_thread = None
        self._update_worker = None

    def _on_update_dialog_finished(self, _result: int) -> None:
        self._update_dialog = None

    # ---------- chụp ----------
    def _hide_app_windows(self) -> None:
        """Ẩn cửa sổ app trước khi chụp để không lọt vào ảnh."""
        for w in (self.library_window, self.editor):
            if w.isVisible():
                w.hide()

    @Slot()
    def capture_region(self) -> None:
        # Ẩn cửa sổ rồi mới hiện overlay (chờ một nhịp cho cửa sổ biến mất).
        self._hide_app_windows()
        QTimer.singleShot(180, self.region_selector.start)

    @Slot()
    def capture_fullscreen(self) -> None:
        self._hide_app_windows()
        QTimer.singleShot(180, self._do_fullscreen_capture)

    def _do_fullscreen_capture(self) -> None:
        image = capture_manager.capture_fullscreen()
        self._handle_new_capture(image)

    @Slot()
    def capture_window(self) -> None:
        """Chụp một cửa sổ: hiện overlay highlight cửa sổ dưới con trỏ.

        Thiếu pywin32 (hoặc không phải Windows) -> báo nhẹ nhàng, không crash.
        """
        if not window_capture_available():
            self.tray.showMessage(
                APP_NAME, "Chụp cửa sổ cần pywin32 trên Windows."
            )
            return
        self._hide_app_windows()
        QTimer.singleShot(180, self.window_selector.start)

    @Slot(int)
    def capture_fullscreen_delayed(self, seconds: int | None = None) -> None:
        """Chụp toàn màn hình sau N giây, kèm overlay đếm ngược."""
        if self._delay_timer.isActive():
            return  # đang đếm ngược -> bỏ qua yêu cầu chồng
        if seconds is None:
            seconds = int(self.config.get("capture_delay_seconds", 3))
        seconds = max(1, int(seconds))
        self._hide_app_windows()
        self._delay_remaining = seconds
        self.countdown_overlay.show_count(seconds)
        self._delay_timer.start()
        self._register_escape()

    def _on_delay_tick(self) -> None:
        self._delay_remaining -= 1
        if self._delay_remaining <= 0:
            self._delay_timer.stop()
            self._unregister_escape()
            self.countdown_overlay.hide()
            self._do_fullscreen_capture()
        else:
            self.countdown_overlay.show_count(self._delay_remaining)

    def _cancel_countdown(self) -> None:
        """Hủy chụp hẹn giờ đang đếm ngược (do người dùng nhấn Esc)."""
        self._delay_timer.stop()
        self.countdown_overlay.hide()
        self._unregister_escape()

    # ---------- Esc toàn cục (hủy countdown / dừng quay) ----------
    def _register_escape(self) -> None:
        """Đăng ký Esc toàn cục (hủy countdown / dừng quay) khi tiến trình đang chạy."""
        if self._esc_handle is not None:
            return
        try:
            import keyboard
            self._esc_handle = keyboard.add_hotkey(
                "esc", lambda: self._emit_safe(self.request_escape)
            )
        except Exception:
            self._esc_handle = None

    def _unregister_escape(self) -> None:
        if self._esc_handle is None:
            return
        try:
            import keyboard
            keyboard.remove_hotkey(self._esc_handle)
        except Exception:
            pass
        self._esc_handle = None

    @Slot()
    def _on_escape(self) -> None:
        if self._delay_timer.isActive():
            self._cancel_countdown()
        elif self._recording:
            self.stop_recording()

    @Slot(QRect)
    def _on_region_selected(self, rect: QRect) -> None:
        try:
            image = capture_manager.capture_region(
                rect.x(), rect.y(), rect.width(), rect.height()
            )
        except ValueError:
            return
        self._handle_new_capture(image)

    def _handle_new_capture(self, image: QImage) -> None:
        cap = self.library.add_capture(image)
        if self.config.get("open_editor_after_capture", True):
            self.editor.load_image(image, capture_id=cap.id)
            self._raise_editor()
        else:
            self.tray.showMessage(APP_NAME, "Đã lưu ảnh vào thư viện.")
        self.library_window.refresh()
        self._refresh_editor_recents()

    def _raise_editor(self) -> None:
        """Đưa Editor lên foreground bền vững: bỏ minimize + active + raise."""
        self.editor.setWindowState(
            (self.editor.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive
        )
        self.editor.show()
        self.editor.raise_()
        self.editor.activateWindow()

    def _refresh_editor_recents(self) -> None:
        """Bơm 12 ảnh mới nhất (bỏ video) vào dải 'Ảnh gần đây' của Editor."""
        caps = [c for c in self.library.list_captures() if not c.is_video][:12]
        items = [
            {"id": c.id, "thumb": str(c.thumbnail_path), "label": c.filename}
            for c in caps
        ]
        self.editor.set_recent_captures(items)

    # ---------- quay video ----------
    @Slot()
    def toggle_video_recording(self) -> None:
        """Bật/tắt quay toàn màn hình: đang quay thì dừng, chưa thì bắt đầu."""
        if self._recording:
            self.stop_recording()
            return
        self._hide_app_windows()
        QTimer.singleShot(180, lambda: self._begin_recording(
            capture_manager.virtual_screen_geometry()))

    @Slot(bool)
    def _on_audio_toggled(self, checked: bool) -> None:
        self._record_audio_enabled = checked and audio_available()

    def _open_hotkey_settings(self) -> None:
        """Mở hộp thoại đổi phím chụp vùng, lưu config và đăng ký lại hotkey."""
        from .common.settings_dialog import HotkeyDialog

        current = self.config.get("hotkey_region", "print screen")
        dlg = HotkeyDialog(current)
        if dlg.exec() != QDialog.Accepted:
            return
        new = dlg.value()
        if not new or new == current:
            return
        self.config["hotkey_region"] = new
        save_config(self.config)
        self.reload_global_hotkeys()
        self.tray.showMessage(APP_NAME, f"Đã đặt phím chụp vùng: {new}")

    def _on_startup_toggled(self, checked: bool) -> None:
        if not autostart.set_enabled(checked):
            self._startup_action.blockSignals(True)
            self._startup_action.setChecked(autostart.is_enabled())
            self._startup_action.blockSignals(False)
            self.tray.showMessage(APP_NAME, "Không đặt được khởi động cùng Windows.")
            return
        self.config["start_on_boot"] = checked
        save_config(self.config)

    def _begin_recording(self, region: dict) -> None:
        if self._recording:
            return
        ts = datetime.now()
        base = videos_dir() / f"video_{ts:%Y%m%d_%H%M%S}"
        final_path = str(base) + ".mp4"
        self._recording_region = region
        self._final_path = final_path
        self._audio_recorder = None
        self._video_tmp_path = None
        self._audio_tmp_path = None

        use_audio = self._record_audio_enabled and audio_available()
        video_out = final_path
        if use_audio:
            # Quay video ra file tạm để còn ghép tiếng; audio ra WAV tạm.
            video_out = str(base) + "_video.mp4"
            audio_tmp = str(base) + "_audio.wav"
            try:
                self._audio_recorder = AudioRecorder(audio_tmp)
                self._video_tmp_path = video_out
                self._audio_tmp_path = audio_tmp
            except Exception as exc:
                # Không khởi tạo được audio -> quay video-only như cũ.
                self._audio_recorder = None
                self._video_tmp_path = None
                self._audio_tmp_path = None
                video_out = final_path
                self.tray.showMessage(APP_NAME, "Không thu được âm thanh: " + str(exc))

        self._recorder = VideoRecorder(
            region, video_out, fps=int(self.config.get("video_fps", 15))
        )
        self._recorder.finished_recording.connect(self._on_recording_finished)
        self._recorder.error.connect(self._on_recording_error)
        self._recording = True
        self._record_action.setText("Dừng quay video")
        self.record_bar.start()
        self._register_escape()

        # Bắt đầu audio rồi video sát nhau nhất có thể để giảm lệch.
        if self._audio_recorder is not None:
            try:
                self._audio_recorder.start()
            except Exception as exc:
                # Mic lỗi lúc chạy -> bỏ audio, quay video-only (ghi thẳng file cuối).
                self._audio_recorder = None
                self._video_tmp_path = None
                self._audio_tmp_path = None
                self._recorder._output_path = final_path
                self.tray.showMessage(APP_NAME, "Mic lỗi, quay không tiếng: " + str(exc))
        self._recorder.start()

    def _on_pause_toggled(self, paused: bool) -> None:
        if self._recorder is not None:
            self._recorder.set_paused(paused)
        if self._audio_recorder is not None:
            self._audio_recorder.set_paused(paused)

    @Slot()
    def stop_recording(self) -> None:
        if not self._recording or self._recorder is None:
            return
        self._unregister_escape()
        self.record_bar.finish()
        # Dừng audio (đồng bộ: đóng stream + file) trước, video kết thúc sau.
        if self._audio_recorder is not None:
            try:
                self._audio_recorder.stop()
            except Exception:
                pass
        self._recorder.stop()  # luồng sẽ kết thúc và phát finished_recording

    @Slot(str, float, int)
    def _on_recording_finished(self, path: str, duration: float, frames: int) -> None:
        self._recording = False
        self._record_action.setText("Quay video toàn màn hình")
        self._unregister_escape()

        # Nếu có thu âm: ghép audio+video; lỗi/không tiếng -> giữ video-only.
        audio_rec = self._audio_recorder
        self._audio_recorder = None
        if audio_rec is not None and self._video_tmp_path and self._audio_tmp_path:
            final_path = self._finalize_with_audio(
                self._video_tmp_path, self._audio_tmp_path,
                self._final_path or path, audio_rec,
            )
        else:
            final_path = path  # video-only: đã ghi thẳng file cuối

        region = self._recording_region or {"width": 0, "height": 0}
        w, h = region["width"], region["height"]
        thumb = self._video_thumbnail(final_path)
        if not thumb.isNull():
            w, h = thumb.width(), thumb.height()
        self.library.add_video(final_path, duration, thumb, w, h)
        self.library_window.refresh()
        self.tray.showMessage(
            APP_NAME, f"Đã lưu video ({duration:.0f}s, {frames} frame) vào thư viện."
        )

    def _finalize_with_audio(self, video_tmp: str, audio_tmp: str,
                             final_path: str, audio_rec: AudioRecorder) -> str:
        """Ghép audio+video thành final_path. Lỗi/không tiếng -> giữ video-only.

        Trả về đường dẫn file cuối thực tế (luôn tồn tại, không mất bản ghi).
        """
        has_audio = False
        try:
            has_audio = (audio_rec.has_audio
                         and os.path.exists(audio_tmp)
                         and os.path.getsize(audio_tmp) > 0)
        except Exception:
            has_audio = False

        if has_audio and mux_audio_video(video_tmp, audio_tmp, final_path):
            for p in (video_tmp, audio_tmp):
                try:
                    os.remove(p)
                except OSError:
                    pass
            return final_path

        # Fallback video-only: đưa file video tạm thành file cuối.
        try:
            if os.path.exists(final_path):
                os.remove(final_path)
            os.replace(video_tmp, final_path)
        except OSError:
            final_path = video_tmp  # không đổi tên được thì giữ nguyên tạm
        try:
            if os.path.exists(audio_tmp):
                os.remove(audio_tmp)
        except OSError:
            pass

        msg = ("Không có tín hiệu mic - đã lưu video không tiếng."
               if not has_audio else
               "Ghép âm thanh thất bại - đã lưu video không tiếng.")
        self.tray.showMessage(APP_NAME, msg)
        return final_path

    @staticmethod
    def _video_thumbnail(path: str) -> QImage:
        """Lấy frame đầu của video làm thumbnail."""
        try:
            import imageio
            import numpy as np

            reader = imageio.get_reader(path)
            frame = np.ascontiguousarray(reader.get_data(0))  # RGB (h, w, 3)
            reader.close()
            h, w = frame.shape[0], frame.shape[1]
            qimg = QImage(frame.tobytes(), w, h, 3 * w, QImage.Format_RGB888)
            return qimg.copy()
        except Exception:
            return QImage()

    def _on_recording_error(self, message: str) -> None:
        self._recording = False
        self._record_action.setText("Quay video toàn màn hình")
        self._unregister_escape()
        self.record_bar.finish()
        if self._audio_recorder is not None:
            try:
                self._audio_recorder.stop()
            except Exception:
                pass
            self._audio_recorder = None
        self.tray.showMessage(APP_NAME, "Lỗi quay video: " + message)

    # ---------- editor <-> library ----------
    @Slot(QImage)
    def _on_editor_save(self, image: QImage) -> None:
        cid = self.editor.current_capture_id
        if cid is not None and self.library.get(cid) is not None:
            self.library.update_image(cid, image)
        else:
            cap = self.library.add_capture(image)
            self.editor.load_image(image, capture_id=cap.id)
        self.library_window.refresh()
        self._refresh_editor_recents()
        self.tray.showMessage(APP_NAME, "Đã lưu vào thư viện.")

    @Slot(int)
    def _open_capture_in_editor(self, capture_id: int) -> None:
        cap = self.library.get(capture_id)
        if cap is None:
            return
        image = QImage(cap.path)
        if image.isNull():
            return
        self.editor.load_image(image, capture_id=capture_id)
        self._raise_editor()
        self._refresh_editor_recents()

    @Slot(int)
    def _on_delete_capture(self, capture_id: int) -> None:
        """Xoá ảnh từ dải 'Ảnh gần đây'; nếu xoá ảnh đang mở thì nhảy ảnh mới nhất."""
        was_current = capture_id == self.editor.current_capture_id
        self.library.delete(capture_id)
        self.library_window.refresh()
        self._refresh_editor_recents()
        if was_current:
            remaining = [c for c in self.library.list_captures() if not c.is_video]
            if remaining:
                # list_captures sắp xếp mới→cũ → phần tử đầu là ảnh mới nhất.
                self._open_capture_in_editor(remaining[0].id)

    def show_library(self) -> None:
        self.library_window.show()
        self.library_window.raise_()
        self.library_window.activateWindow()

    # ---------- phím tắt toàn cục ----------
    def _emit_safe(self, signal) -> None:
        """Phát signal an toàn từ keyboard thread — KHÔNG BAO GIỜ để exception thoát ra.

        Mục đích: ``_generic.process()`` gọi ``pre_process_event()`` KHÔNG có try/except
        → nếu callback ném exception → ``processing_thread`` chết vĩnh viễn → hotkey chết
        đến khi restart app. Bọc tất cả callback keyboard bằng hàm này để ngăn điều đó.

        Dùng cho signal với ``Qt.QueuedConnection``: ``emit()`` chỉ post event vào Qt
        event queue của main thread, không chạy slot ngay trong keyboard thread → an toàn.
        """
        try:
            signal.emit()
        except Exception:
            _log.exception("[hotkey] signal.emit() ném exception trong keyboard thread"
                           " — đã chặn để bảo vệ processing_thread.")

    def install_global_hotkeys(self) -> None:
        """Đăng ký phím tắt toàn cục bằng thư viện `keyboard` (nếu có).

        Chạy trong luồng riêng của keyboard; phát signal về luồng GUI.
        """
        try:
            import keyboard
        except Exception:
            return  # không có keyboard -> bỏ qua, vẫn dùng được qua tray menu

        # Phím chụp vùng: phân biệt phím đơn vs tổ hợp.
        # - Phím đơn (vd "print screen"): dùng hook_key(suppress=True) — chặn phím
        #   xuống OS và tránh Right Ctrl kẹt (CTRL-STUCK-FIX).
        # - Tổ hợp phím (vd "windows+shift+a"): dùng add_hotkey — hook_key chỉ
        #   nhận tên 1 phím đơn, không hỗ trợ tổ hợp "mod+key".
        #   KHÔNG dùng suppress=True để tránh modifier state machine kẹt Ctrl.
        # Lưu remove-handle để reload_global_hotkeys có thể gỡ đúng cách.
        region_key = self.config.get("hotkey_region", "print screen")
        if self._remove_region_hook is not None:
            try:
                self._remove_region_hook()
            except Exception:
                pass
            self._remove_region_hook = None

        is_combo = "+" in region_key
        if is_combo:
            try:
                handler = keyboard.add_hotkey(
                    region_key,
                    lambda: self._emit_safe(self.request_region),
                )
                self._remove_region_hook = lambda: keyboard.remove_hotkey(handler)
            except Exception:
                self._remove_region_hook = None
        else:
            try:
                def _region_hook(event):
                    if event.event_type == keyboard.KEY_DOWN:
                        self._emit_safe(self.request_region)
                    return False  # suppress: luôn chặn phím đơn xuống OS
                self._remove_region_hook = keyboard.hook_key(region_key, _region_hook, suppress=True)
            except Exception:
                try:
                    def _region_hook_fallback(event):
                        if event.event_type == keyboard.KEY_DOWN:
                            self._emit_safe(self.request_region)
                    self._remove_region_hook = keyboard.hook_key(region_key, _region_hook_fallback)
                except Exception:
                    self._remove_region_hook = None

        try:
            keyboard.add_hotkey(
                self.config.get("hotkey_video", "ctrl+shift+r"),
                lambda: self._emit_safe(self.request_video_toggle),
            )
        except Exception:
            # Một số máy cần quyền admin để hook bàn phím toàn cục.
            pass
        self._start_hotkey_watchdog()

    def reload_global_hotkeys(self) -> None:
        """Gỡ và đăng ký lại hotkey theo config hiện tại (Python-level callback tables).

        Lưu ý: ``remove_all_hotkeys()`` + ``add_hotkey()`` KHÔNG tái cài WH_KEYBOARD_LL
        OS hook — chỉ thao tác ``_listener.blocking_hotkeys``/``nonblocking_hotkeys``.
        remove_all_hotkeys() KHÔNG xoá blocking_keys (dùng bởi hook_key) → phải gỡ
        _remove_region_hook riêng trước. Nếu region là tổ hợp (add_hotkey),
        _remove_region_hook gỡ nó trước khi remove_all_hotkeys dọn phần còn lại.
        """
        try:
            import keyboard
            # Gỡ region hook trước (hook_key hoặc add_hotkey handler).
            if self._remove_region_hook is not None:
                try:
                    self._remove_region_hook()
                except Exception:
                    pass
                self._remove_region_hook = None
            keyboard.remove_all_hotkeys()
        except Exception:
            pass
        # remove_all_hotkeys() xoá CẢ Esc đăng ký riêng → handle thành stale.
        self._esc_handle = None
        self.install_global_hotkeys()
        # Đăng ký lại Esc nếu đang đếm ngược / đang quay (nếu không, hủy/dừng chết câm).
        if self._delay_timer.isActive() or self._recording:
            self._register_escape()

    def _start_hotkey_watchdog(self) -> None:
        """Khởi watchdog phát hiện listener thread chết — chỉ tạo 1 lần, chạy liên tục."""
        if self._hotkey_watchdog is None:
            self._hotkey_watchdog = QTimer(self)
            self._hotkey_watchdog.setInterval(_HOTKEY_WATCHDOG_INTERVAL_MS)
            self._hotkey_watchdog.timeout.connect(self._watchdog_reregister_hotkeys)
        if not self._hotkey_watchdog.isActive():
            self._hotkey_watchdog.start()

    def _watchdog_reregister_hotkeys(self) -> None:
        """Watchdog giám sát processing_thread + ghi log chẩn đoán định kỳ.

        Kịch bản được xử lý:
        1. ``processing_thread`` chết (exception từ callback → propagate qua
           ``pre_process_event()`` vì không có try/except) → hotkey chết hoàn toàn:
           events vào queue nhưng không ai xử lý. Restart processing_thread ngay.
        2. ``listening_thread`` chết → ghi log cảnh báo (không còn cơ chế tự restart).

        KHÔNG re-add hotkey (handlers persist). Guard chống double-thread trong
        _restart_processing_thread.
        """
        self._hotkey_watchdog_tick += 1

        try:
            import keyboard
            lst = keyboard._listener
        except Exception:
            return

        listen_thread = getattr(lst, "listening_thread", None)
        proc_thread   = getattr(lst, "processing_thread", None)
        listen_alive  = listen_thread is not None and listen_thread.is_alive()
        proc_alive    = proc_thread   is not None and proc_thread.is_alive()

        # Log chẩn đoán mỗi 30 s (6 tick × 5 s) để pin nguyên nhân nếu user báo lỗi.
        if self._hotkey_watchdog_tick % 6 == 0:
            _log.debug(
                "[hotkey-watchdog] tick=%d | listening_thread=%s | processing_thread=%s"
                " | queue_size=%d",
                self._hotkey_watchdog_tick,
                "alive" if listen_alive else "DEAD",
                "alive" if proc_alive   else "DEAD",
                lst.queue.qsize(),
            )

        if not proc_alive:
            # NGUY HIỂM NHẤT: processing_thread chết → không ai drain queue → hotkey im.
            _log.warning(
                "[hotkey-watchdog] processing_thread %s — khôi phục.",
                "chưa khởi động" if proc_thread is None else "đã chết",
            )
            self._restart_processing_thread(lst)
            if not listen_alive:
                _log.warning("[hotkey-watchdog] listening_thread cũng chết — không thể tự khôi phục.")
        elif not listen_alive:
            _log.warning(
                "[hotkey-watchdog] listening_thread %s — không có cơ chế tự khôi phục.",
                "chưa khởi động" if listen_thread is None else "đã chết",
            )


    def _restart_processing_thread(self, lst) -> bool:
        """Khởi động lại processing_thread đã chết — LEAK-FREE.

        Leak-free vì: chỉ gọi khi old thread đã CHẾT (is_alive=False) → không có thread
        nào blocked trên queue.get() → tạo thread mới không tạo thêm thread zombie.

        Drain queue trước khi start thread mới để tránh bơm loạt event cũ (ví dụ: key
        events tồn đọng trong lúc thread chết) gây chụp/escape/video toggle không mong muốn.

        KHÔNG set ``listening=False``, KHÔNG re-add hotkey (handlers persist).
        Guard: nếu old thread vẫn còn sống khi gọi → ABORT (không tạo 2 processing_thread).
        """
        import threading
        import queue as _queue_mod
        try:
            old = getattr(lst, "processing_thread", None)
            if old is not None and old.is_alive():
                _log.error(
                    "[hotkey] _restart_processing_thread: old thread vẫn sống — ABORT "
                    "(chỉ gọi hàm này khi thread đã chết)."
                )
                return False

            # Drain stale events tồn đọng trong queue.
            drained = 0
            try:
                while True:
                    lst.queue.get_nowait()
                    lst.queue.task_done()
                    drained += 1
            except _queue_mod.Empty:
                pass
            except Exception:
                pass
            if drained:
                _log.debug(
                    "[hotkey] Đã drain %d stale event khỏi queue trước khi restart "
                    "processing_thread.", drained,
                )

            t = threading.Thread(target=lst.process, daemon=True)
            lst.processing_thread = t
            t.start()
            _log.info("[hotkey] processing_thread mới đã khởi động.")
            return True
        except Exception:
            _log.warning("[hotkey] _restart_processing_thread thất bại.", exc_info=True)
            return False

    def _manual_reregister_hotkeys(self) -> None:
        """Khôi phục processing_thread thủ công qua tray menu — lối thoát khi hotkey chết.

        Chỉ khôi phục processing_thread; listening_thread không còn cơ chế tự hồi.
        Handlers persist — không re-add hotkey.
        """
        _log.info("[hotkey] Tái đăng ký thủ công qua tray menu.")
        try:
            import keyboard as _kb
            lst = _kb._listener
        except Exception:
            self.tray.showMessage(APP_NAME, "Không load được keyboard library.", msecs=2000)
            return

        proc_thread = getattr(lst, "processing_thread", None)
        proc_dead   = proc_thread is None or not proc_thread.is_alive()
        if proc_dead:
            _log.warning("[hotkey] manual: processing_thread đã chết — khôi phục.")
            proc_ok = self._restart_processing_thread(lst)
            msg = ("Đã khôi phục processing_thread hotkey." if proc_ok
                   else "Khôi phục processing_thread thất bại — xem log.")
        else:
            msg = "Hotkey processing_thread đang hoạt động bình thường."
        _log.info("[hotkey] %s", msg)
        self.tray.showMessage(APP_NAME, msg, msecs=3000)

    def shutdown(self) -> None:
        if self._hotkey_watchdog is not None:
            self._hotkey_watchdog.stop()
        if self._update_thread is not None:
            self._update_thread.quit()
            self._update_thread.wait(2000)
        if self._audio_recorder is not None:
            try:
                self._audio_recorder.stop()
            except Exception:
                pass
        if self._recording and self._recorder is not None:
            self._recorder.stop()
            self._recorder.wait(3000)
        self.library.close()
