"""The circuit pane: renders every QuantumCircuit the editor code defines."""

import base64

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea, QStackedWidget,
    QToolButton, QVBoxLayout, QWidget,
)

STYLES = ["iqp", "iqp-dark", "clifford", "textbook", "bw"]


class CircuitView(QWidget):
    settingsChanged = Signal()  # style or fold changed: diagram must be re-rendered
    circuitSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._circuits = []
        self._pixmap = None
        self._zoom = 1.0
        self._fit = True

        self.circuit_box = QComboBox()
        self.circuit_box.setMinimumWidth(120)
        self.circuit_box.setToolTip("Circuits defined in the editor")
        self.circuit_box.currentIndexChanged.connect(self._show_current)

        self.mode_box = QComboBox()
        self.mode_box.addItems(["Diagram", "Text"])
        self.mode_box.currentIndexChanged.connect(self._show_current)

        self.style_box = QComboBox()
        self.style_box.addItems(STYLES)
        self.style_box.setToolTip("Diagram style")
        self.style_box.currentIndexChanged.connect(lambda _: self.settingsChanged.emit())

        self.fold_box = QComboBox()
        self.fold_box.addItems(["No wrap", "Wrap 25", "Wrap 50"])
        self.fold_box.setToolTip("Wrap long circuits onto several rows")
        self.fold_box.currentIndexChanged.connect(lambda _: self.settingsChanged.emit())

        def tool(text, tip, slot):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            return b

        top = QHBoxLayout()
        top.setContentsMargins(6, 6, 6, 0)
        top.addWidget(QLabel("Circuit"))
        top.addWidget(self.circuit_box)
        top.addWidget(self.mode_box)
        top.addWidget(self.style_box)
        top.addWidget(self.fold_box)
        top.addStretch(1)
        top.addWidget(tool("−", "Zoom out (Ctrl+-)", lambda: self.zoom_by(1 / 1.25)))
        top.addWidget(tool("Fit", "Fit to pane", self.fit))
        top.addWidget(tool("1:1", "Actual size", lambda: self.set_zoom(1.0)))
        top.addWidget(tool("+", "Zoom in (Ctrl+=)", lambda: self.zoom_by(1.25)))

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setStyleSheet("background:white;")
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.image)
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setStyleSheet("QScrollArea { background:#ffffff; border:none; }")

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(11)
        self.text.setFont(mono)

        self.placeholder = QLabel(
            "No circuit yet.\n\nDefine a QuantumCircuit in the editor,\n"
            "for example  qc = QuantumCircuit(2)")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color:#7f848e; font-size:14px;")

        self.stack = QStackedWidget()
        self.stack.addWidget(self.placeholder)
        self.stack.addWidget(self.scroll)
        self.stack.addWidget(self.text)

        self.stats = QLabel()
        self.stats.setStyleSheet("color:#abb2bf; padding:4px 8px;")
        self.stats.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            "background:#3b2226; color:#f0a3aa; padding:6px 8px; font-family:monospace;")
        self.banner.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.banner)
        layout.addWidget(self.stats)

    # ----- settings sent to the renderer -------------------------------
    def style(self):
        return self.style_box.currentText()

    def fold(self):
        return [-1, 25, 50][self.fold_box.currentIndex()]

    def current_name(self):
        i = self.circuit_box.currentIndex()
        return self._circuits[i]["name"] if 0 <= i < len(self._circuits) else None

    # ----- results -------------------------------------------------------
    def show_result(self, result):
        previous = self.current_name()
        self._circuits = result.get("circuits", [])
        self.circuit_box.blockSignals(True)
        self.circuit_box.clear()
        for c in self._circuits:
            self.circuit_box.addItem(c["name"])
        names = [c["name"] for c in self._circuits]
        if previous in names:
            self.circuit_box.setCurrentIndex(names.index(previous))
        elif names:
            # Default to the most recently defined circuit.
            self.circuit_box.setCurrentIndex(len(names) - 1)
        self.circuit_box.blockSignals(False)

        error = result.get("error")
        if error:
            line = result.get("error_line")
            where = f"Line {line}: " if line else ""
            stale = "  (diagram shows the circuit up to the error)" if self._circuits else ""
            self.banner.setText(where + error + stale)
            self.banner.show()
        else:
            self.banner.hide()
        self._show_current()

    def show_message(self, message):
        self.banner.setText(message)
        self.banner.show()

    def _show_current(self):
        i = self.circuit_box.currentIndex()
        if not (0 <= i < len(self._circuits)):
            self.stack.setCurrentWidget(self.placeholder)
            self.stats.setText("")
            return
        c = self._circuits[i]
        self.circuitSelected.emit(c["name"])
        ops = "  ".join(f"{k}×{v}" for k, v in c["ops"].items()) or "no operations"
        self.stats.setText(
            f"<b>{c['name']}</b> · {c['num_qubits']} qubits · {c['num_clbits']} clbits · "
            f"depth {c['depth']} · {c['size']} ops &nbsp;&nbsp; {ops}")
        self.text.setPlainText(c["text"])

        if self.mode_box.currentText() == "Text" or not c.get("png"):
            if c.get("draw_error") and self.mode_box.currentText() != "Text":
                self.stats.setText(self.stats.text() + f"<br>Diagram unavailable: {c['draw_error']}")
            self.stack.setCurrentWidget(self.text)
            return
        pm = QPixmap()
        pm.loadFromData(base64.b64decode(c["png"]), "PNG")
        self._pixmap = pm
        # Match the pane to the diagram's own background (dark styles).
        bg = pm.toImage().pixelColor(2, 2).name()
        self.image.setStyleSheet(f"background:{bg};")
        self.scroll.setStyleSheet(f"QScrollArea {{ background:{bg}; border:none; }}")
        self.stack.setCurrentWidget(self.scroll)
        self._apply_zoom()

    # ----- zoom ------------------------------------------------------------
    def fit(self):
        self._fit = True
        self._apply_zoom()

    def set_zoom(self, z):
        self._fit = False
        self._zoom = max(0.1, min(z, 6.0))
        self._apply_zoom()

    def zoom_by(self, factor):
        self.set_zoom(self._current_scale() * factor)

    def _current_scale(self):
        if not self._pixmap or self._pixmap.isNull():
            return self._zoom
        return self.image.width() / max(1, self._pixmap.width())

    def _apply_zoom(self):
        if not self._pixmap or self._pixmap.isNull():
            return
        if self._fit:
            area = self.scroll.viewport().size()
            scale = min(area.width() / self._pixmap.width(), area.height() / self._pixmap.height(), 1.0)
        else:
            scale = self._zoom
        scaled = self._pixmap.scaled(
            max(1, int(self._pixmap.width() * scale)), max(1, int(self._pixmap.height() * scale)),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image.setPixmap(scaled)
        self.image.resize(scaled.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit:
            self._apply_zoom()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
            event.accept()
        else:
            super().wheelEvent(event)
