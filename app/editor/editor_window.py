"""Cửa sổ Editor: thanh công cụ vẽ + canvas + panel Tool Properties (màu, độ dày).

Bố cục mô phỏng Snagit:
- Toolbar trên: các công cụ chú thích.
- Canvas giữa.
- Panel phải: thuộc tính công cụ + Quick colors.
- Toolbar dưới: Lưu vào thư viện / Xuất ra file / Copy.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDockWidget,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from .canvas import (
    STAMP_NAMES,
    Canvas,
    Tool,
    _paint_stamp_glyph,
    item_style_props,
)
from .tool_icons import tool_icon

QUICK_COLORS = [
    "#FF3B30", "#FF9500", "#FFCC00", "#34C759",
    "#1E90FF", "#5856D6", "#000000", "#FFFFFF",
]

# (tool, tên, icon, phím tắt) — icon là TÊN icon line-art trong tool_icons.
TOOLS = [
    (Tool.SELECT, "Chọn", "select", "V"),
    (Tool.ARROW, "Mũi tên", "arrow", "A"),
    (Tool.RECT, "Chữ nhật", "rect", "R"),
    (Tool.ELLIPSE, "Elip", "ellipse", "E"),
    (Tool.PEN, "Bút vẽ", "pen", "P"),
    (Tool.TEXT, "Chữ", "text", "T"),
    (Tool.CALLOUT, "Callout", "callout", "O"),
    (Tool.HIGHLIGHT, "Đánh dấu", "highlight", "H"),
    (Tool.BLUR, "Làm mờ", "blur", "B"),
    (Tool.STEP, "Số bước", "step", "S"),
    (Tool.CROP, "Cắt", "crop", "C"),
    (Tool.STAMP, "Stamp", "stamp", "M"),
    (Tool.SPOTLIGHT, "Tiêu điểm", "spotlight", "F"),
]

# Gợi ý hiển thị ở status bar tuỳ theo công cụ đang chọn.
TOOL_HINTS = {
    Tool.SELECT: "Chọn: nhấp để chọn đối tượng, kéo để di chuyển, Delete để xoá.",
    Tool.ARROW: "Mũi tên: kéo từ điểm đầu đến điểm cuối.",
    Tool.RECT: "Chữ nhật: kéo để vẽ khung viền.",
    Tool.ELLIPSE: "Elip: kéo để vẽ hình tròn/elip.",
    Tool.PEN: "Bút vẽ: giữ chuột trái và vẽ tự do.",
    Tool.TEXT: "Chữ: nhấp vào ảnh rồi gõ nội dung.",
    Tool.CALLOUT: "Callout: kéo để vẽ bong bóng theo cỡ mong muốn; double-click để sửa chữ; kéo handle để resize.",
    Tool.HIGHLIGHT: "Đánh dấu: kéo để tô vùng nổi bật (mờ trong suốt).",
    Tool.BLUR: "Làm mờ: kéo chọn vùng cần che mờ.",
    Tool.STEP: "Số bước: nhấp để đặt badge số, tự tăng dần.",
    Tool.CROP: "Cắt: kéo chọn vùng giữ lại, phần ngoài bị cắt bỏ.",
    Tool.STAMP: "Stamp: nhấp để chèn biểu tượng.",
    Tool.SPOTLIGHT: "Tiêu điểm: kéo chọn vùng cần làm nổi bật (ngoài vùng bị làm tối).",
}

# Nhóm thuộc tính liên quan tới từng công cụ (panel chỉ hiện nhóm phù hợp).
# Khoá nhóm: "color", "width", "font", "step".
TOOL_PROPS = {
    Tool.SELECT: [],
    Tool.ARROW: ["color", "width"],
    Tool.RECT: ["color", "width"],
    Tool.ELLIPSE: ["color", "width"],
    Tool.PEN: ["color", "width"],
    Tool.TEXT: ["color", "font"],
    Tool.CALLOUT: ["color", "width", "font"],
    Tool.HIGHLIGHT: ["color"],
    Tool.BLUR: [],
    Tool.STEP: ["color", "width", "step"],
    Tool.CROP: [],
    Tool.STAMP: ["stamp", "color"],
    Tool.SPOTLIGHT: [],
}

# Express Styles: preset áp combo style nhanh cho object đang chọn + state vẽ-mới.
# Mỗi dict chỉ chứa khoá hợp lệ với apply_style_to_selection
# (color/width/fill/fill_enabled/shadow). fill chỉ áp được cho rect/ellipse.
QUICK_STYLES = [
    {"name": "Đỏ đậm", "color": "#FF3B30", "width": 5},
    {"name": "Xanh dương", "color": "#1E90FF", "width": 3},
    {"name": "Hộp vàng", "color": "#E6A700", "width": 2,
     "fill": "#FFE680", "fill_enabled": True},
    {"name": "Đen mảnh", "color": "#000000", "width": 2},
    {"name": "Trắng đổ bóng", "color": "#FFFFFF", "width": 3, "shadow": True},
    {"name": "Xanh lá", "color": "#34C759", "width": 4},
]

# Theme tối tập trung cho toàn bộ cửa sổ Editor.
EDITOR_QSS = """
QMainWindow, QMainWindow > QWidget { background: #2B2D31; }
QToolBar {
    background: #33363B;
    border: none;
    padding: 4px;
    spacing: 4px;
}
#captureBar, #toolBar, #zoomBar, #bottomBar { background: #33363B; }
QToolBar::separator {
    background: #4A4D52;
    width: 1px;
    margin: 4px 6px;
}
QToolButton {
    color: #E8E8E8;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
}
QToolButton:hover {
    background: #3E4248;
    border: 1px solid #55585E;
}
QToolButton:checked {
    background: #1E90FF;
    color: #FFFFFF;
    border: 1px solid #1E90FF;
}
QToolButton:pressed { background: #187BDD; }
QDockWidget {
    color: #E8E8E8;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background: #33363B;
    padding: 7px 10px;
    color: #E8E8E8;
    font-weight: bold;
}
#propsPanel { background: #2B2D31; }
#propsPanel QLabel { color: #DDDDDD; }
QSlider::groove:horizontal {
    height: 4px;
    background: #4A4D52;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #1E90FF;
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #4AA8FF; }
QSpinBox {
    background: #3E4248;
    color: #E8E8E8;
    border: 1px solid #55585E;
    border-radius: 4px;
    padding: 2px 4px;
}
#propsPanel QPushButton {
    background: #3E4248;
    color: #E8E8E8;
    border: 1px solid #55585E;
    border-radius: 5px;
    padding: 5px 8px;
}
#propsPanel QPushButton:hover { background: #484C53; }
#propsPanel QPushButton:pressed { background: #2F3338; }
QStatusBar { background: #222428; }
QStatusBar, QStatusBar QLabel { color: #C8C8C8; }
QStatusBar::item { border: none; }
#emptyState { background: #3A3D42; }
#emptyTitle { color: #E8E8E8; font-size: 19px; font-weight: bold; }
#emptySub { color: #9AA0A6; font-size: 13px; }
#emptyState QPushButton {
    background: #1E90FF;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
    font-size: 13px;
}
#emptyState QPushButton:hover { background: #3AA0FF; }
#emptyState QPushButton:pressed { background: #187BDD; }
#emptyState QPushButton#secondary {
    background: #3E4248;
    border: 1px solid #55585E;
}
#emptyState QPushButton#secondary:hover { background: #484C53; }
#recentStrip {
    background: #2B2D31;
    border: none;
    outline: none;
}
#recentStrip::item {
    background: #33363B;
    border: 1px solid transparent;
    border-radius: 6px;
    margin: 2px;
    padding: 2px;
}
#recentStrip::item:hover {
    background: #3E4248;
    border: 1px solid #55585E;
}
#recentStrip::item:selected {
    background: #1E3A5F;
    border: 2px solid #1E90FF;
}
QMenu {
    background: #33363B;
    color: #E8E8E8;
    border: 1px solid #55585E;
}
QMenu::item { padding: 6px 18px; }
QMenu::item:selected { background: #1E90FF; color: #FFFFFF; }
#toast {
    background: rgba(20, 20, 22, 235);
    color: #FFFFFF;
    border: 1px solid #55585E;
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
}
"""


class EditorWindow(QMainWindow):
    # Phát QImage khi người dùng muốn lưu vào thư viện.
    save_to_library = Signal(QImage)
    # Các yêu cầu chụp/quay phát lên controller xử lý (giống LibraryWindow).
    request_capture_region = Signal()
    request_capture_fullscreen = Signal()
    request_video = Signal()
    # Phát capture_id khi người dùng nhấp một thumbnail trong dải "Ảnh gần đây".
    open_capture_requested = Signal(int)
    # Phát capture_id khi người dùng yêu cầu xoá ảnh từ dải "Ảnh gần đây".
    delete_capture_requested = Signal(int)
    # Phát khi người dùng muốn quay về thư viện.
    request_library = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - Editor")
        self.resize(1100, 720)
        self._current_capture_id: int | None = None

        self.canvas = Canvas()
        # Nền canvas tối để ảnh nổi bật (API Qt công khai, không đụng canvas.py).
        self.canvas.setBackgroundBrush(QColor("#3A3D42"))
        self.setCentralWidget(self.canvas)

        self._build_capture_toolbar()
        self._build_tool_toolbar()
        self._build_zoom_toolbar()
        self._build_properties_panel()
        self._build_bottom_toolbar()
        self._build_recent_dock()
        self._build_status_bar()
        self._build_overlays()

        # Áp theme tập trung sau khi đã dựng widget.
        self.setStyleSheet(EDITOR_QSS)

        self.canvas.step_number_changed.connect(self._sync_step_number)
        self.canvas.zoom_changed.connect(self._sync_zoom_label)
        self.canvas.resize_preview.connect(self._on_resize_preview)
        self.canvas.resize_finished.connect(self._on_resize_finished)
        self.canvas.selection_changed.connect(self._refresh_props)
        self._select_tool(Tool.ARROW)
        self._refresh_empty_state()

    # ---------- thanh chụp & quay ----------
    def _build_capture_toolbar(self) -> None:
        """Nút chụp/quay ngay trong Editor để chụp tiếp mà không cần về thư viện."""
        tb = QToolBar("Chụp & Quay")
        tb.setObjectName("captureBar")
        tb.setMovable(False)
        tb.setStyleSheet("QToolBar { padding:4px; spacing:6px; }")
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, tb)

        # Nút về thư viện — đặt ở đầu toolbar, tách bằng separator với nhóm chụp.
        act_library = QAction("Về thư viện", self)
        act_library.setIcon(tool_icon("open"))
        act_library.setToolTip("Quay lại màn hình thư viện")
        act_library.triggered.connect(self.request_library.emit)
        tb.addAction(act_library)
        tb.addSeparator()

        for text, icon, signal, tip in (
            ("Chụp vùng", "capture_region", self.request_capture_region, "Chụp một vùng màn hình"),
            ("Chụp toàn màn hình", "capture_full", self.request_capture_fullscreen, "Chụp toàn bộ màn hình"),
            ("Quay video", "video", self.request_video, "Quay video màn hình"),
        ):
            act = QAction(text, self)
            act.setIcon(tool_icon(icon))
            act.setToolTip(tip)
            act.triggered.connect(signal.emit)
            tb.addAction(act)
        # Tách riêng một hàng để các thanh công cụ vẽ xuống dòng dưới.
        self.addToolBarBreak(Qt.TopToolBarArea)

    # ---------- thanh công cụ vẽ ----------
    def _build_tool_toolbar(self) -> None:
        tb = QToolBar("Công cụ")
        tb.setObjectName("toolBar")
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)

        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb.setIconSize(QSize(26, 26))

        # Hoàn tác / Làm lại nối với QUndoStack của canvas.
        self.undo_action = self.canvas.undo_stack.createUndoAction(self, "Hoàn tác")
        self.undo_action.setShortcut(QKeySequence.Undo)            # Ctrl+Z
        self.undo_action.setToolTip("Hoàn tác (Ctrl+Z)")
        self.undo_action.setIcon(tool_icon("undo"))
        self.redo_action = self.canvas.undo_stack.createRedoAction(self, "Làm lại")
        self.redo_action.setShortcut(QKeySequence.Redo)            # Ctrl+Y / Ctrl+Shift+Z
        self.redo_action.setToolTip("Làm lại (Ctrl+Y)")
        self.redo_action.setIcon(tool_icon("redo"))
        tb.addAction(self.undo_action)
        tb.addAction(self.redo_action)
        # createUndoAction đổi text động ("Hoàn tác Thêm callout"…) → với
        # TextUnderIcon nút giãn rộng, nhảy bề ngang và ngốn chỗ của tool toolbar.
        # Icon-only giữ bề ngang ổn định; nhãn động vẫn còn ở tooltip + menu ">>".
        for _act in (self.undo_action, self.redo_action):
            _btn = tb.widgetForAction(_act)
            if _btn is not None:
                _btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        tb.addSeparator()

        group = QActionGroup(self)
        group.setExclusive(True)
        self._tool_actions: dict[Tool, QAction] = {}
        for tool, name, icon, shortcut in TOOLS:
            act = QAction(name, self)
            act.setIcon(tool_icon(icon))
            act.setCheckable(True)
            act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(f"{name} ({shortcut})")
            act.triggered.connect(lambda _=False, t=tool: self._select_tool(t))
            group.addAction(act)
            tb.addAction(act)
            self._tool_actions[tool] = act

    # ---------- thanh zoom ----------
    def _build_zoom_toolbar(self) -> None:
        tb = QToolBar("Zoom")
        tb.setObjectName("zoomBar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        # Xuống hàng riêng: không tranh chỗ với tool toolbar khi cửa sổ hẹp, nhờ đó
        # nút overflow ">>" của tool toolbar luôn tới được (mọi tool truy cập được).
        self.addToolBarBreak(Qt.TopToolBarArea)
        self.addToolBar(Qt.TopToolBarArea, tb)

        for text, icon, slot, shortcut, tip in (
            ("Thu nhỏ", "zoom_out", self.canvas.zoom_out, "Ctrl+-", "Thu nhỏ"),
            ("Phóng to", "zoom_in", self.canvas.zoom_in, "Ctrl+=", "Phóng to"),
            ("Vừa khung", "zoom_fit", self.canvas.zoom_fit, "Ctrl+0", "Vừa khung nhìn"),
            ("100%", "zoom_actual", self.canvas.zoom_actual, "Ctrl+1", "Kích thước thật 100%"),
        ):
            act = QAction(text, self)
            act.setIcon(tool_icon(icon))
            act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(f"{tip} ({shortcut})")
            act.triggered.connect(slot)
            tb.addAction(act)
            # Giữ bar gọn: 2 nút này chỉ hiện icon trong toolbar; nhưng nhờ có text
            # nhãn, overflow menu ">>" khi cửa sổ nhỏ hiện chữ thay vì dòng trống.
            if icon in ("zoom_out", "zoom_in"):
                btn = tb.widgetForAction(act)
                if btn is not None:
                    btn.setToolButtonStyle(Qt.ToolButtonIconOnly)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        tb.addWidget(self.zoom_label)

    def _sync_zoom_label(self, percent: float) -> None:
        text = f"{round(percent)}%"
        self.zoom_label.setText(text)
        self.status_zoom.setText(text)
        # Zoom phát cả sau khi crop → cập nhật luôn kích thước ảnh.
        self._update_image_size_status()

    # ---------- panel thuộc tính (dock phải) ----------
    @staticmethod
    def _new_group(title: str) -> tuple[QWidget, QVBoxLayout]:
        """Tạo một nhóm thuộc tính có tiêu đề; trả về (widget, layout nội dung)."""
        group = QWidget()
        gl = QVBoxLayout(group)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(4)
        gl.addWidget(QLabel(f"<b>{title}</b>"))
        return group, gl

    def _build_properties_panel(self) -> None:
        from PySide6.QtWidgets import QDockWidget

        dock = QDockWidget("Tool Properties", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        panel = QWidget()
        panel.setObjectName("propsPanel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        # Mỗi nhóm là một widget độc lập để ẩn/hiện theo công cụ đang chọn.
        self._prop_groups: dict[str, QWidget] = {}

        # --- Express Styles (LUÔN hiện, KHÔNG vào _prop_groups) ---
        from PySide6.QtWidgets import QGridLayout
        quick_group, qg = self._new_group("Express Styles")
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for i, preset in enumerate(QUICK_STYLES):
            btn = QPushButton()
            btn.setFixedSize(52, 30)
            btn.setIcon(QIcon(self._quick_style_pixmap(preset)))
            btn.setIconSize(QSize(46, 24))
            btn.setToolTip(preset["name"])
            btn.clicked.connect(lambda _=False, p=preset: self._apply_quick_style(p))
            grid.addWidget(btn, i // 3, i % 3)
        qg.addWidget(grid_host)
        layout.addWidget(quick_group)

        # --- Nhóm Màu ---
        color_group, cg = self._new_group("Màu")
        colors = QWidget()
        cl = QHBoxLayout(colors)
        cl.setContentsMargins(0, 0, 0, 0)
        for hex_color in QUICK_COLORS:
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setStyleSheet(
                f"background:{hex_color}; border:1px solid #888; "
                "border-radius:4px; padding:0;"
            )
            btn.clicked.connect(lambda _=False, c=hex_color: self._set_color(QColor(c)))
            cl.addWidget(btn)
        cg.addWidget(colors)
        more_color = QPushButton("Chọn màu khác...")
        more_color.clicked.connect(self._pick_custom_color)
        cg.addWidget(more_color)
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(20)
        cg.addWidget(self.color_preview)
        layout.addWidget(color_group)
        self._prop_groups["color"] = color_group

        # --- Nhóm Độ dày nét ---
        width_group, wg = self._new_group("Độ dày nét")
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 40)
        self.width_slider.setValue(self.canvas.state.width)
        self.width_label = QLabel(f"{self.canvas.state.width} pt")
        # Kéo slider: cập nhật label/state live; chốt 1 StyleCommand khi nhả chuột
        # để tránh spam undo mỗi tick.
        self.width_slider.valueChanged.connect(self._set_width)
        self.width_slider.sliderReleased.connect(self._commit_width)
        wg.addWidget(self.width_slider)
        wg.addWidget(self.width_label)
        layout.addWidget(width_group)
        self._prop_groups["width"] = width_group

        # --- Nhóm Cỡ chữ ---
        font_group, fg = self._new_group("Cỡ chữ")
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 96)
        self.font_slider.setValue(self.canvas.state.font_size)
        self.font_label = QLabel(f"{self.canvas.state.font_size} pt")
        self.font_slider.valueChanged.connect(self._set_font_size)
        self.font_slider.sliderReleased.connect(self._commit_font_size)
        fg.addWidget(self.font_slider)
        fg.addWidget(self.font_label)
        layout.addWidget(font_group)
        self._prop_groups["font"] = font_group

        # --- Nhóm Số bước ---
        step_group, sg = self._new_group("Số bước")
        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Số kế tiếp:"))
        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 999)
        self.step_spin.setValue(self.canvas.state.step_number)
        self.step_spin.valueChanged.connect(self._set_step_number)
        step_row.addWidget(self.step_spin)
        reset_step = QPushButton("Reset = 1")
        reset_step.clicked.connect(lambda: self.step_spin.setValue(1))
        step_row.addWidget(reset_step)
        sg.addLayout(step_row)
        layout.addWidget(step_group)
        self._prop_groups["step"] = step_group

        # --- Nhóm Biểu tượng (chọn glyph cho công cụ Stamp) ---
        stamp_group, stg = self._new_group("Biểu tượng")
        stamp_row = QWidget()
        srl = QHBoxLayout(stamp_row)
        srl.setContentsMargins(0, 0, 0, 0)
        self._stamp_buttons: dict[str, QPushButton] = {}
        for name in STAMP_NAMES:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(34, 34)
            btn.setIcon(QIcon(self._stamp_pixmap(name)))
            btn.setIconSize(QSize(26, 26))
            btn.setToolTip(name)
            btn.clicked.connect(lambda _=False, n=name: self._select_stamp(n))
            srl.addWidget(btn)
            self._stamp_buttons[name] = btn
        stg.addWidget(stamp_row)
        layout.addWidget(stamp_group)
        self._prop_groups["stamp"] = stamp_group
        self._sync_stamp_buttons()

        # --- Nhóm Độ trong suốt (universal, chỉ hiện khi có item chọn) ---
        opacity_group, og = self._new_group("Độ trong suốt")
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(100)
        self.opacity_label = QLabel("100%")
        # Kéo: cập nhật label live (không undo); nhả chuột: chốt 1 StyleCommand.
        self.opacity_slider.valueChanged.connect(self._set_opacity_label)
        self.opacity_slider.sliderReleased.connect(self._commit_opacity)
        og.addWidget(self.opacity_slider)
        og.addWidget(self.opacity_label)
        layout.addWidget(opacity_group)
        self._prop_groups["opacity"] = opacity_group

        # --- Nhóm Đổ bóng (universal) ---
        shadow_group, shg = self._new_group("Đổ bóng")
        self.shadow_check = QCheckBox("Đổ bóng")
        self.shadow_check.toggled.connect(self._toggle_shadow)
        shg.addWidget(self.shadow_check)
        layout.addWidget(shadow_group)
        self._prop_groups["shadow"] = shadow_group

        # --- Nhóm Tô nền (chỉ rect/ellipse có viền; không vào TOOL_PROPS) ---
        fill_group, flg = self._new_group("Tô nền")
        self.fill_check = QCheckBox("Tô nền")
        self.fill_check.toggled.connect(self._toggle_fill)
        flg.addWidget(self.fill_check)
        fill_colors = QWidget()
        fcl = QHBoxLayout(fill_colors)
        fcl.setContentsMargins(0, 0, 0, 0)
        for hex_color in QUICK_COLORS:
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setStyleSheet(
                f"background:{hex_color}; border:1px solid #888; "
                "border-radius:4px; padding:0;"
            )
            # Nhấp swatch nền: tự bật fill bằng màu đó.
            btn.clicked.connect(lambda _=False, c=hex_color: self._set_fill(QColor(c)))
            fcl.addWidget(btn)
        flg.addWidget(fill_colors)
        more_fill = QPushButton("Chọn màu nền…")
        more_fill.clicked.connect(self._pick_fill_color)
        flg.addWidget(more_fill)
        self.fill_preview = QLabel()
        self.fill_preview.setFixedHeight(20)
        flg.addWidget(self.fill_preview)
        layout.addWidget(fill_group)
        self._prop_groups["fill"] = fill_group

        # --- Trạng thái rỗng: công cụ không có thuộc tính ---
        self._empty_group = QLabel(
            "Công cụ này không có thuộc tính tuỳ chỉnh."
        )
        self._empty_group.setWordWrap(True)
        self._empty_group.setStyleSheet("color:#9AA0A6;")
        layout.addWidget(self._empty_group)

        layout.addStretch(1)
        hint = QLabel("Mẹo: chọn công cụ 'Chọn' rồi nhấn Delete để xoá đối tượng.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9AA0A6;")
        layout.addWidget(hint)

        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._set_color(self.canvas.state.color)

    def _update_props_visibility(self, tool: Tool) -> None:
        """Chỉ hiện các nhóm thuộc tính liên quan tới công cụ đang chọn."""
        active = TOOL_PROPS.get(tool, [])
        for key, group in self._prop_groups.items():
            group.setVisible(key in active)
        self._empty_group.setVisible(len(active) == 0)

    def _refresh_props(self) -> None:
        """Cập nhật panel: theo ITEM đang chọn nếu có, ngược lại theo công cụ.

        Khi đúng 1 item được chọn (kể cả ở công cụ Chọn), hiện đúng nhóm thuộc
        tính của chính item đó và đồng bộ giá trị màu/độ dày/cỡ chữ về style hiện
        tại — đồng bộ là thao tác hiển thị, KHÔNG phát sinh undo.
        """
        item = self.canvas.selected_annotation()
        if item is None:
            self._update_props_visibility(self.canvas.state.tool)
            return
        props = item_style_props(item)
        groups = props["groups"]
        for key, group in self._prop_groups.items():
            group.setVisible(key in groups)
        self._empty_group.setVisible(not groups)
        if props["color"] is not None:
            self._sync_color_preview(props["color"])
        if props["width"] is not None:
            self._sync_slider(self.width_slider, props["width"], self.width_label)
        if props["font_size"] is not None:
            self._sync_slider(self.font_slider, props["font_size"], self.font_label)
        if "opacity" in props:
            self._sync_opacity(props["opacity"])
        if "shadow" in props:
            self.shadow_check.blockSignals(True)
            self.shadow_check.setChecked(props["shadow"])
            self.shadow_check.blockSignals(False)
        if "fill_enabled" in props:
            self.fill_check.blockSignals(True)
            self.fill_check.setChecked(props["fill_enabled"])
            self.fill_check.blockSignals(False)
        if "fill_color" in props:
            self._sync_fill_preview(props["fill_color"])

    def _sync_color_preview(self, color: QColor) -> None:
        """Hiện màu của item đang chọn ở ô preview (không đổi state, không undo)."""
        self.color_preview.setStyleSheet(
            f"background:{color.name()}; border:1px solid #888; border-radius:4px;"
        )

    def _sync_slider(self, slider: QSlider, value: int, label: QLabel) -> None:
        """Đặt slider về giá trị của item mà KHÔNG bắn valueChanged (tránh undo)."""
        slider.blockSignals(True)
        slider.setValue(int(value))
        slider.blockSignals(False)
        label.setText(f"{slider.value()} pt")

    # ---------- thanh dưới ----------
    def _build_bottom_toolbar(self) -> None:
        tb = QToolBar("Hành động")
        tb.setObjectName("bottomBar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.BottomToolBarArea, tb)
        for text, icon, slot, shortcut, tip in (
            ("Lưu vào thư viện", "save", self._save_to_library, "Ctrl+S", "Lưu ảnh vào thư viện"),
            ("Xuất ra file...", "export", self._export_file, "Ctrl+E", "Xuất ảnh ra file"),
            # Copy nhận cả Ctrl+C lẫn Ctrl+Shift+C cho tiện tay.
            ("Copy", "copy", self._copy_clipboard, ("Ctrl+C", "Ctrl+Shift+C"), "Copy ảnh vào clipboard"),
        ):
            keys = [shortcut] if isinstance(shortcut, str) else list(shortcut)
            act = QAction(text, self)
            act.setIcon(tool_icon(icon))
            act.setShortcuts([QKeySequence(k) for k in keys])
            act.setToolTip(f"{tip} ({' / '.join(keys)})")
            act.triggered.connect(slot)
            tb.addAction(act)

    # ---------- dải ảnh gần đây (filmstrip) ----------
    def _build_recent_dock(self) -> None:
        """Dock dưới chứa dải thumbnail các ảnh gần đây để chuyển nhanh.

        Editor KHÔNG biết LibraryManager: controller bơm dữ liệu qua
        set_recent_captures() và lắng nghe open_capture_requested.
        """
        dock = QDockWidget("Ảnh gần đây", self)
        dock.setObjectName("recentDock")
        dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        strip = QListWidget()
        strip.setObjectName("recentStrip")
        strip.setViewMode(QListWidget.IconMode)
        strip.setFlow(QListWidget.LeftToRight)
        strip.setWrapping(False)
        strip.setMovement(QListWidget.Static)
        strip.setResizeMode(QListWidget.Adjust)
        strip.setUniformItemSizes(True)
        strip.setIconSize(QSize(72, 72))
        strip.setFixedHeight(96)
        strip.setSpacing(4)
        strip.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        strip.itemClicked.connect(self._on_recent_item_clicked)
        # Right-click → menu "Xoá ảnh"; phím Delete xử lý qua eventFilter.
        strip.setContextMenuPolicy(Qt.CustomContextMenu)
        strip.customContextMenuRequested.connect(self._on_recent_context_menu)
        strip.installEventFilter(self)

        self.recent_strip = strip
        self.recent_dock = dock
        dock.setWidget(strip)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        dock.hide()

    def set_recent_captures(self, items: list[dict]) -> None:
        """Dựng lại dải thumbnail. item = {"id": int, "thumb": str, "label": str}.

        Rỗng → ẩn dock. Sau khi dựng, đồng bộ highlight theo ảnh đang mở.
        """
        self.recent_strip.clear()
        for it in items:
            pix = QPixmap(str(it.get("thumb", "")))
            icon = QIcon(pix) if not pix.isNull() else QIcon()
            lw = QListWidgetItem(icon, "")
            lw.setData(Qt.UserRole, int(it["id"]))
            lw.setToolTip(str(it.get("label", "")))
            lw.setSizeHint(QSize(84, 84))
            self.recent_strip.addItem(lw)
        self.recent_dock.setVisible(bool(items))
        self._sync_recent_highlight()

    def _sync_recent_highlight(self) -> None:
        """Chọn item khớp _current_capture_id (hiển thị, KHÔNG phát signal)."""
        if not hasattr(self, "recent_strip"):
            return
        cid = self._current_capture_id
        self.recent_strip.blockSignals(True)
        self.recent_strip.clearSelection()
        self.recent_strip.setCurrentItem(None)
        for i in range(self.recent_strip.count()):
            item = self.recent_strip.item(i)
            if cid is not None and item.data(Qt.UserRole) == cid:
                item.setSelected(True)
                self.recent_strip.setCurrentItem(item)
                self.recent_strip.scrollToItem(item)
                break
        self.recent_strip.blockSignals(False)

    def _on_recent_item_clicked(self, item: QListWidgetItem) -> None:
        cid = item.data(Qt.UserRole)
        if cid is None:
            return
        cid = int(cid)
        # Bỏ qua nếu là ảnh đang mở (tránh reload thừa); giữ nguyên highlight.
        if cid == self._current_capture_id:
            self._sync_recent_highlight()
            return
        self.open_capture_requested.emit(cid)

    def _on_recent_context_menu(self, pos) -> None:
        """Right-click thumbnail → menu 'Xoá ảnh'."""
        item = self.recent_strip.itemAt(pos)
        if item is None:
            return
        cid = item.data(Qt.UserRole)
        if cid is None:
            return
        menu = QMenu(self)
        act_del = menu.addAction("Xoá ảnh")
        chosen = menu.exec(self.recent_strip.viewport().mapToGlobal(pos))
        if chosen is act_del:
            self._request_delete_capture(int(cid))

    def _request_delete_capture(self, capture_id: int) -> None:
        """Hỏi xác nhận (mặc định No) rồi phát yêu cầu xoá lên controller."""
        reply = QMessageBox.question(
            self, "Xoá ảnh", "Xoá ảnh này khỏi thư viện?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.delete_capture_requested.emit(capture_id)

    # ---------- status bar ----------
    def _build_status_bar(self) -> None:
        """Thanh trạng thái: gợi ý công cụ (trái) + kích thước ảnh & zoom (phải)."""
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.status_hint = QLabel("")
        sb.addWidget(self.status_hint, 1)

        self.status_size = QLabel("—")
        self.status_zoom = QLabel("100%")
        sep = QLabel("│")
        sep.setStyleSheet("color:#55585E;")
        sb.addPermanentWidget(self.status_size)
        sb.addPermanentWidget(sep)
        sb.addPermanentWidget(self.status_zoom)

    def _update_image_size_status(self) -> None:
        rect = self.canvas.scene().sceneRect()
        w, h = int(round(rect.width())), int(round(rect.height()))
        if self.canvas.has_image() and w > 0 and h > 0:
            self.status_size.setText(f"{w} × {h} px")
        else:
            self.status_size.setText("—")

    # ---------- empty state + toast (vi-tương tác) ----------
    def _build_overlays(self) -> None:
        """Màn hình rỗng có CTA + widget toast nổi, đều phủ lên canvas.

        Parent vào viewport() của QGraphicsView (KHÔNG phải view) để chắc chắn
        nổi trên vùng vẽ — tránh gotcha Qt: con của view bị viewport che mất.
        """
        viewport = self.canvas.viewport()
        # --- Empty state ---
        self._empty_state = QWidget(viewport)
        self._empty_state.setObjectName("emptyState")
        el = QVBoxLayout(self._empty_state)
        el.setAlignment(Qt.AlignCenter)
        el.setSpacing(10)

        title = QLabel("Chưa có ảnh để chỉnh sửa")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("Chụp màn hình hoặc mở một ảnh có sẵn để bắt đầu.")
        sub.setObjectName("emptySub")
        sub.setAlignment(Qt.AlignCenter)
        el.addWidget(title)
        el.addWidget(sub)
        el.addSpacing(8)

        cta = QHBoxLayout()
        cta.setAlignment(Qt.AlignCenter)
        cta.setSpacing(10)
        btn_region = QPushButton("Chụp vùng")
        btn_region.setIcon(tool_icon("capture_region"))
        btn_region.clicked.connect(self.request_capture_region.emit)
        btn_full = QPushButton("Chụp toàn màn hình")
        btn_full.setIcon(tool_icon("capture_full"))
        btn_full.setObjectName("secondary")
        btn_full.clicked.connect(self.request_capture_fullscreen.emit)
        btn_open = QPushButton("Mở ảnh...")
        btn_open.setIcon(tool_icon("open"))
        btn_open.setObjectName("secondary")
        btn_open.clicked.connect(self._open_image_file)
        cta.addWidget(btn_region)
        cta.addWidget(btn_full)
        cta.addWidget(btn_open)
        el.addLayout(cta)
        self._empty_state.hide()

        # --- Toast ---
        self._toast = QLabel(viewport)
        self._toast.setObjectName("toast")
        self._toast.setAlignment(Qt.AlignCenter)
        self._toast_effect = QGraphicsOpacityEffect(self._toast)
        self._toast.setGraphicsEffect(self._toast_effect)
        self._toast_anim = QPropertyAnimation(self._toast_effect, b"opacity", self)
        self._toast_anim.setDuration(600)
        self._toast_anim.setStartValue(1.0)
        self._toast_anim.setEndValue(0.0)
        self._toast_anim.finished.connect(self._toast.hide)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast_anim.start)
        self._toast.hide()

        # Theo dõi viewport đổi kích thước để đặt lại vị trí overlay.
        viewport.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Phím Delete trên dải ảnh gần đây → yêu cầu xoá item đang chọn.
        if obj is getattr(self, "recent_strip", None) \
                and event.type() == QEvent.KeyPress \
                and event.key() == Qt.Key_Delete:
            item = self.recent_strip.currentItem()
            if item is not None:
                cid = item.data(Qt.UserRole)
                if cid is not None:
                    self._request_delete_capture(int(cid))
                return True
        if obj is self.canvas.viewport() and event.type() in (
            QEvent.Resize, QEvent.Show,
        ):
            self._empty_state.setGeometry(self.canvas.viewport().rect())
            self._position_toast()
        return super().eventFilter(obj, event)

    def _refresh_empty_state(self) -> None:
        show = not self.canvas.has_image()
        self._empty_state.setGeometry(self.canvas.viewport().rect())
        self._empty_state.setVisible(show)
        if show:
            self._empty_state.raise_()

    def _position_toast(self) -> None:
        c = self.canvas.viewport().rect()
        self._toast.adjustSize()
        x = c.center().x() - self._toast.width() // 2
        y = c.bottom() - self._toast.height() - 30
        self._toast.move(max(0, x), max(0, y))

    def _show_toast(self, text: str) -> None:
        self._toast.setText(text)
        self._position_toast()
        self._toast_anim.stop()
        self._toast_effect.setOpacity(1.0)
        self._toast.show()
        self._toast.raise_()
        self._toast_timer.start(1600)

    def _open_image_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Mở ảnh", "",
            "Ảnh (*.png *.jpg *.jpeg *.bmp);;Tất cả tệp (*)",
        )
        if not path:
            return
        image = QImage(path)
        if not image.isNull():
            self.load_image(image)

    # ---------- xử lý ----------
    def load_image(self, image: QImage, capture_id: int | None = None) -> None:
        self.canvas.load_image(image)
        self._current_capture_id = capture_id
        self._update_image_size_status()
        self._refresh_empty_state()
        self._sync_recent_highlight()

    @property
    def current_capture_id(self) -> int | None:
        return self._current_capture_id

    def _select_tool(self, tool: Tool) -> None:
        self.canvas.state.tool = tool
        if tool in self._tool_actions:
            self._tool_actions[tool].setChecked(True)
        self.status_hint.setText(TOOL_HINTS.get(tool, ""))
        self._refresh_props()
        self.canvas.refresh_handles()

    def _on_resize_preview(self, w: float, h: float) -> None:
        self.status_hint.setText(f"Kích thước: {round(w)} × {round(h)} px")

    def _on_resize_finished(self) -> None:
        self.status_hint.setText(TOOL_HINTS.get(self.canvas.state.tool, ""))

    def _set_color(self, color: QColor) -> None:
        self.canvas.state.color = color
        self.color_preview.setStyleSheet(
            f"background:{color.name()}; border:1px solid #888; border-radius:4px;"
        )
        # Áp ngay lên item đang chọn (an toàn khi chưa chọn gì: trả về False).
        self.canvas.apply_style_to_selection(color=color)

    def _pick_custom_color(self) -> None:
        color = QColorDialog.getColor(self.canvas.state.color, self, "Chọn màu")
        if color.isValid():
            self._set_color(color)

    @staticmethod
    def _stamp_pixmap(name: str, size: int = 26, color: str = "#E8E8E8") -> QPixmap:
        """Chip glyph cho nút chọn stamp (tái dùng _paint_stamp_glyph của canvas)."""
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(Qt.NoPen))
        m = size * 0.1
        _paint_stamp_glyph(painter, name, QRectF(m, m, size - 2 * m, size - 2 * m))
        painter.end()
        return pm

    def _select_stamp(self, name: str) -> None:
        """Đặt biểu tượng kế tiếp cho công cụ Stamp + cập nhật nút đang chọn."""
        self.canvas.state.stamp_name = name
        self._sync_stamp_buttons()

    def _sync_stamp_buttons(self) -> None:
        """Đánh dấu nút stamp khớp state.stamp_name (hiển thị, không undo)."""
        current = self.canvas.state.stamp_name
        for name, btn in self._stamp_buttons.items():
            btn.setChecked(name == current)

    @staticmethod
    def _quick_style_pixmap(preset: dict, w: int = 46, h: int = 24) -> QPixmap:
        """Vẽ chip preview cho preset: hình bo góc theo pen màu+độ dày, tô nền nếu có."""
        pm = QPixmap(w, h)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen_w = max(1, min(int(preset.get("width", 2)), 6))
        painter.setPen(QPen(QColor(preset["color"]), pen_w))
        if preset.get("fill_enabled") and preset.get("fill"):
            painter.setBrush(QBrush(QColor(preset["fill"])))
        else:
            painter.setBrush(QBrush(Qt.NoBrush))
        m = pen_w / 2 + 2
        painter.drawRoundedRect(m, m, w - 2 * m, h - 2 * m, 4, 4)
        painter.end()
        return pm

    def _apply_quick_style(self, preset: dict) -> None:
        """Áp preset: cập nhật state vẽ-mới + 1 StyleCommand cho selection."""
        color = QColor(preset["color"])
        # State vẽ-mới: đặt màu + preview thủ công (KHÔNG dùng _set_color để tránh
        # phát sinh thêm 1 command áp-selection riêng cho màu).
        self.canvas.state.color = color
        self.color_preview.setStyleSheet(
            f"background:{color.name()}; border:1px solid #888; border-radius:4px;"
        )
        kwargs: dict = {"color": color}
        if "width" in preset:
            self.canvas.state.width = preset["width"]
            self._sync_slider(self.width_slider, preset["width"], self.width_label)
            kwargs["width"] = preset["width"]
        if "fill" in preset:
            kwargs["fill"] = QColor(preset["fill"])
        if "fill_enabled" in preset:
            kwargs["fill_enabled"] = preset["fill_enabled"]
        if "shadow" in preset:
            kwargs["shadow"] = preset["shadow"]
        if "opacity" in preset:
            kwargs["opacity"] = preset["opacity"]
        if "font_size" in preset:
            self.canvas.state.font_size = preset["font_size"]
            kwargs["font_size"] = preset["font_size"]
        # 1 lần gọi → tối đa 1 StyleCommand (an toàn khi chưa chọn item: trả False).
        self.canvas.apply_style_to_selection(**kwargs)
        self._refresh_props()

    def _set_width(self, value: int) -> None:
        # Live: chỉ cập nhật state (nét vẽ mới) + label, KHÔNG push command.
        self.canvas.state.width = value
        self.width_label.setText(f"{value} pt")

    def _commit_width(self) -> None:
        # Nhả chuột: áp 1 StyleCommand cho item đang chọn.
        self.canvas.apply_style_to_selection(width=self.width_slider.value())

    def _set_font_size(self, value: int) -> None:
        self.canvas.state.font_size = value
        self.font_label.setText(f"{value} pt")

    def _commit_font_size(self) -> None:
        self.canvas.apply_style_to_selection(font_size=self.font_slider.value())

    def _set_opacity_label(self, value: int) -> None:
        # Live: chỉ cập nhật label khi kéo, chốt command lúc nhả chuột.
        self.opacity_label.setText(f"{value}%")

    def _commit_opacity(self) -> None:
        self.canvas.apply_style_to_selection(
            opacity=self.opacity_slider.value() / 100.0
        )

    def _toggle_shadow(self, checked: bool) -> None:
        # 1 command mỗi lần bấm; an toàn khi chưa chọn gì (trả False).
        self.canvas.apply_style_to_selection(shadow=checked)

    def _toggle_fill(self, checked: bool) -> None:
        self.canvas.apply_style_to_selection(fill_enabled=checked)

    def _set_fill(self, color: QColor) -> None:
        # Nhấp màu nền: tự bật fill bằng màu đó (mutate_item_style tự setBrush).
        self.canvas.apply_style_to_selection(fill=color)

    def _pick_fill_color(self) -> None:
        color = QColorDialog.getColor(self.canvas.state.color, self, "Chọn màu nền")
        if color.isValid():
            self._set_fill(color)

    def _sync_fill_preview(self, color: QColor | None) -> None:
        """Hiện màu nền hiện tại ở ô preview (không đổi state, không undo)."""
        if color is None:
            self.fill_preview.setStyleSheet(
                "background:transparent; border:1px dashed #888; border-radius:4px;"
            )
        else:
            self.fill_preview.setStyleSheet(
                f"background:{color.name()}; border:1px solid #888; border-radius:4px;"
            )

    def _sync_opacity(self, value_float: float) -> None:
        """Đặt slider + label độ trong suốt theo item, KHÔNG bắn valueChanged."""
        percent = round(value_float * 100)
        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(percent)
        self.opacity_slider.blockSignals(False)
        self.opacity_label.setText(f"{self.opacity_slider.value()}%")

    def _set_step_number(self, value: int) -> None:
        self.canvas.state.step_number = value

    def _sync_step_number(self, value: int) -> None:
        """Đồng bộ ô SpinBox khi canvas tự tăng/đặt lại số bước."""
        self.step_spin.blockSignals(True)
        self.step_spin.setValue(value)
        self.step_spin.blockSignals(False)

    def _save_to_library(self) -> None:
        if not self.canvas.has_image():
            return
        self.save_to_library.emit(self.canvas.render_to_image())
        self._show_toast("Đã lưu vào thư viện")

    def _export_file(self) -> None:
        if not self.canvas.has_image():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất ảnh", "snagtin.png",
            "PNG (*.png);;JPEG (*.jpg);;Bitmap (*.bmp)",
        )
        if path:
            import os
            if self.canvas.render_to_image().save(path):
                self._show_toast(f"Đã xuất: {os.path.basename(path)}")

    def _copy_clipboard(self) -> None:
        if not self.canvas.has_image():
            return
        QGuiApplication.clipboard().setImage(self.canvas.render_to_image())
        self._show_toast("Đã copy vào clipboard")
