"""Main window: editor on the left, live circuit diagram on the right,
run console at the bottom."""

import os
import sys
import tempfile

from PySide6.QtCore import QProcess, QSettings, Qt
from PySide6.QtGui import QAction, QColor, QFontDatabase, QKeySequence, QPalette, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from . import __version__
from .circuit_view import CircuitView
from .editor import CodeEditor
from .gate_palette import GatePalette
from .preview import PreviewController

EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")

STARTER = '''from math import pi

from qiskit import QuantumCircuit

# Edit the code: the circuit on the right redraws as you type.
qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.barrier()
qc.measure([0, 1, 2], [0, 1, 2])
'''


class MainWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.path = None
        self.settings = QSettings("QiskitIDE", "QiskitIDE")
        self.run_proc = None
        self._run_file = None

        self.editor = CodeEditor()
        self.palette = GatePalette()
        self.circuit = CircuitView()

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        palette_scroll = QScrollArea()
        palette_scroll.setWidget(self.palette)
        palette_scroll.setWidgetResizable(True)
        palette_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        palette_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        palette_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        palette_scroll.setFixedHeight(self.palette.sizeHint().height() + 12)
        lv.addWidget(palette_scroll)
        lv.addWidget(self.editor, 1)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(11)
        self.console.setFont(mono)
        self.console.setStyleSheet("background:#1e2127; color:#abb2bf; border:none;")
        self.console.setPlaceholderText("Output from Run (F5) appears here.")

        self.h_split = QSplitter(Qt.Orientation.Horizontal)
        self.h_split.addWidget(left)
        self.h_split.addWidget(self.circuit)
        self.h_split.setSizes([620, 660])
        self.v_split = QSplitter(Qt.Orientation.Vertical)
        self.v_split.addWidget(self.h_split)
        self.v_split.addWidget(self.console)
        self.v_split.setSizes([620, 180])
        self.setCentralWidget(self.v_split)

        self.preview = PreviewController(parent=self)
        self.preview.started.connect(lambda: self.render_label.setText("Rendering…"))
        self.preview.finished.connect(self._on_preview)

        self.live_box = QCheckBox("Live preview")
        self.live_box.setChecked(True)
        self.live_box.toggled.connect(lambda on: on and self.refresh_preview(immediate=True))
        self.render_label = QLabel()
        self.pos_label = QLabel("Ln 1, Col 1")
        sb = self.statusBar()
        sb.addWidget(self.render_label, 1)
        sb.addPermanentWidget(self.pos_label)
        sb.addPermanentWidget(self.live_box)

        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorLineChanged.connect(lambda l, c: self.pos_label.setText(f"Ln {l}, Col {c}"))
        self.editor.document().modificationChanged.connect(lambda _: self._update_title())
        self.circuit.settingsChanged.connect(lambda: self.refresh_preview(immediate=True))
        self.circuit.circuitSelected.connect(self.palette.set_target)
        self.palette.gateRequested.connect(self.insert_gate)

        self._build_menus()
        self.resize(1280, 820)
        if path:
            self.open_path(path)
        else:
            self.editor.setPlainText(STARTER)
            self.editor.document().setModified(False)
            self._update_title()
        self.refresh_preview(immediate=True)

    # ----- menus -----------------------------------------------------------
    def _build_menus(self):
        def act(menu, text, slot, shortcut=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        m = self.menuBar().addMenu("&File")
        act(m, "&New", self.new_file, QKeySequence.StandardKey.New)
        act(m, "&Open…", self.open_dialog, QKeySequence.StandardKey.Open)
        act(m, "&Save", self.save, QKeySequence.StandardKey.Save)
        act(m, "Save &As…", self.save_as, QKeySequence.StandardKey.SaveAs)
        ex = m.addMenu("Examples")
        if os.path.isdir(EXAMPLES_DIR):
            for name in sorted(os.listdir(EXAMPLES_DIR)):
                if name.endswith(".py"):
                    full = os.path.join(EXAMPLES_DIR, name)
                    act(ex, name[:-3].replace("_", " ").title(), lambda _=False, p=full: self._open_example(p))
        m.addSeparator()
        act(m, "&Quit", self.close, QKeySequence.StandardKey.Quit)

        m = self.menuBar().addMenu("&Edit")
        act(m, "&Undo", self.editor.undo, QKeySequence.StandardKey.Undo)
        act(m, "&Redo", self.editor.redo, QKeySequence.StandardKey.Redo)
        m.addSeparator()
        act(m, "Toggle &Comment", self.editor.toggle_comment, "Ctrl+/")

        m = self.menuBar().addMenu("&View")
        act(m, "Zoom Diagram &In", lambda: self.circuit.zoom_by(1.25), "Ctrl+=")
        act(m, "Zoom Diagram &Out", lambda: self.circuit.zoom_by(1 / 1.25), "Ctrl+-")
        act(m, "&Fit Diagram", self.circuit.fit, "Ctrl+0")
        act(m, "&Refresh Diagram", lambda: self.refresh_preview(immediate=True), "Ctrl+R")

        m = self.menuBar().addMenu("&Run")
        self.run_action = act(m, "&Run Script", self.run_script, "F5")
        self.stop_action = act(m, "&Stop", self.stop_script, "Shift+F5")
        self.stop_action.setEnabled(False)
        act(m, "&Clear Console", self.console.clear)

        m = self.menuBar().addMenu("&Help")
        act(m, "&About", lambda: QMessageBox.about(
            self, "Qiskit IDE",
            f"Qiskit IDE {__version__}\n\nEdit Qiskit code on the left; every QuantumCircuit "
            "it defines is drawn on the right as you type."))

    # ----- live preview ------------------------------------------------------
    def _cwd(self):
        return os.path.dirname(self.path) if self.path else os.getcwd()

    def _on_text_changed(self):
        if self.live_box.isChecked():
            self.refresh_preview()

    def refresh_preview(self, immediate=False):
        self.preview.request(self.editor.toPlainText(), self.circuit.style(),
                             self.circuit.fold(), self._cwd(), immediate=immediate)

    def _on_preview(self, result):
        self.circuit.show_result(result)
        self.editor.set_error_line(result.get("error_line"))
        n = len(result.get("circuits", []))
        if result.get("error"):
            self.render_label.setText("Code has an error" + (f" (line {result['error_line']})"
                                                             if result.get("error_line") else ""))
        else:
            self.render_label.setText(f"{n} circuit{'s' if n != 1 else ''} rendered")

    # ----- gate palette ------------------------------------------------------
    def insert_gate(self, method, args):
        target = self.circuit.current_name() or "qc"
        c = self.editor.textCursor()
        line = c.block().text()
        indent = line[: len(line) - len(line.lstrip())]
        code = f"{target}.{method}({args})"
        c.beginEditBlock()
        if line.strip():
            c.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            c.insertText("\n" + indent + code)
        else:
            c.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            c.insertText(code)
        c.endEditBlock()
        # Select the arguments so the user can type the qubit indices straight away.
        if args:
            c.movePosition(QTextCursor.MoveOperation.Left, n=1)
            c.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(args))
        self.editor.setTextCursor(c)
        self.editor.setFocus()

    # ----- files -------------------------------------------------------------
    def _update_title(self):
        name = os.path.basename(self.path) if self.path else "untitled.py"
        dirty = "•" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{dirty}{name} — Qiskit IDE")

    def _confirm_discard(self):
        if not self.editor.document().isModified():
            return True
        r = QMessageBox.question(
            self, "Unsaved changes", "Save changes before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save()
        return r == QMessageBox.StandardButton.Discard

    def new_file(self):
        if self._confirm_discard():
            self.path = None
            self.editor.setPlainText(STARTER)
            self.editor.document().setModified(False)
            self._update_title()

    def open_dialog(self):
        if not self._confirm_discard():
            return
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, "Open", start, "Python files (*.py);;All files (*)")
        if path:
            self.open_path(path)

    def _open_example(self, path):
        if self._confirm_discard():
            with open(path, encoding="utf-8") as f:
                self.editor.setPlainText(f.read())
            self.path = None  # Save As, so the bundled example is not overwritten
            self.editor.document().setModified(False)
            self._update_title()

    def open_path(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            QMessageBox.warning(self, "Open failed", str(e))
            return
        self.path = os.path.abspath(path)
        self.settings.setValue("last_dir", os.path.dirname(self.path))
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self._update_title()

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
        except OSError as e:
            QMessageBox.warning(self, "Save failed", str(e))
            return False
        self.editor.document().setModified(False)
        self._update_title()
        self.statusBar().showMessage(f"Saved {self.path}", 3000)
        return True

    def save_as(self):
        start = self.path or os.path.join(self.settings.value("last_dir", os.path.expanduser("~")),
                                          "circuit.py")
        path, _ = QFileDialog.getSaveFileName(self, "Save As", start, "Python files (*.py)")
        if not path:
            return False
        self.path = os.path.abspath(path)
        self.settings.setValue("last_dir", os.path.dirname(self.path))
        return self.save()

    # ----- running -----------------------------------------------------------
    def run_script(self):
        if self.run_proc is not None:
            return
        fd, self._run_file = tempfile.mkstemp(suffix=".py", prefix="qiskit_ide_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        self.console.clear()
        self._console_write(f"$ python {os.path.basename(self.path or 'untitled.py')}\n", "#7f848e")
        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setArguments(["-u", self._run_file])
        proc.setWorkingDirectory(self._cwd())
        proc.readyReadStandardOutput.connect(
            lambda: self._console_write(bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")))
        proc.readyReadStandardError.connect(
            lambda: self._console_write(bytes(proc.readAllStandardError()).decode("utf-8", "replace"), "#e06c75"))
        proc.finished.connect(self._on_run_finished)
        self.run_proc = proc
        self.run_action.setEnabled(False)
        self.stop_action.setEnabled(True)
        proc.start()

    def stop_script(self):
        if self.run_proc is not None:
            self.run_proc.kill()

    def _on_run_finished(self, code, _status):
        self._console_write(f"\n[process exited with code {code}]\n", "#7f848e")
        self.run_proc.deleteLater()
        self.run_proc = None
        self.run_action.setEnabled(True)
        self.stop_action.setEnabled(False)
        if self._run_file:
            try:
                os.remove(self._run_file)
            except OSError:
                pass
            self._run_file = None

    def _console_write(self, text, color=None):
        c = self.console.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        fmt = c.charFormat()
        fmt.setForeground(QColor(color or "#abb2bf"))
        c.insertText(text, fmt)
        self.console.setTextCursor(c)
        self.console.ensureCursorVisible()

    def closeEvent(self, event):
        if not self._confirm_discard():
            event.ignore()
            return
        self.stop_script()
        self.preview.shutdown()
        event.accept()


def _dark_palette(app):
    app.setStyle("Fusion")
    p = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window, "#21252b"), (QPalette.ColorRole.WindowText, "#abb2bf"),
        (QPalette.ColorRole.Base, "#282c34"), (QPalette.ColorRole.AlternateBase, "#2c313a"),
        (QPalette.ColorRole.Text, "#abb2bf"), (QPalette.ColorRole.Button, "#2c313a"),
        (QPalette.ColorRole.ButtonText, "#abb2bf"), (QPalette.ColorRole.Highlight, "#3e4451"),
        (QPalette.ColorRole.HighlightedText, "#ffffff"), (QPalette.ColorRole.ToolTipBase, "#21252b"),
        (QPalette.ColorRole.ToolTipText, "#abb2bf"), (QPalette.ColorRole.PlaceholderText, "#5c6370"),
    ]:
        p.setColor(role, QColor(color))
    app.setPalette(p)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Qiskit IDE")
    _dark_palette(app)
    win = MainWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    win.show()
    sys.exit(app.exec())
