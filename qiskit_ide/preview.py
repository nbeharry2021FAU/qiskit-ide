"""Debounced, out-of-process rendering of the editor's circuits."""

import json
import os
import sys

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_worker.py")


class PreviewController(QObject):
    started = Signal()
    finished = Signal(dict)

    def __init__(self, delay_ms=500, timeout_ms=15000, parent=None):
        super().__init__(parent)
        self._debounce = QTimer(self, singleShot=True, interval=delay_ms)
        self._debounce.timeout.connect(self._start)
        self._timeout = QTimer(self, singleShot=True, interval=timeout_ms)
        self._timeout.timeout.connect(self._on_timeout)
        self._proc = None
        self._pending = None
        self._timed_out = False

    def request(self, source, style, fold, cwd, immediate=False):
        self._pending = {"source": source, "style": style, "fold": fold, "cwd": cwd}
        if immediate:
            self._debounce.stop()
            self._start()
        else:
            self._debounce.start()

    def _start(self):
        if self._pending is None:
            return
        if self._proc is not None:
            # A render is running; the newest request starts when it ends.
            return
        req, self._pending = self._pending, None
        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setArguments([WORKER])
        if req["cwd"] and os.path.isdir(req["cwd"]):
            proc.setWorkingDirectory(req["cwd"])
        proc.finished.connect(lambda *_: self._on_finished(proc))
        self._proc = proc
        self._timed_out = False
        self.started.emit()
        proc.start()
        proc.write(json.dumps(req).encode("utf-8"))
        proc.closeWriteChannel()
        self._timeout.start()

    def _on_timeout(self):
        if self._proc is not None:
            self._timed_out = True
            self._proc.kill()

    def _on_finished(self, proc):
        self._timeout.stop()
        out = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        err = bytes(proc.readAllStandardError()).decode("utf-8", "replace")
        proc.deleteLater()
        self._proc = None
        if self._timed_out:
            result = {"ok": False, "circuits": [], "stdout": "",
                      "error": "Preview stopped: the code took longer than "
                               f"{self._timeout.interval() // 1000}s. Use Run (F5) for long jobs.",
                      "error_line": None, "timeout": True}
        else:
            try:
                result = json.loads(out)
            except ValueError:
                result = {"ok": False, "circuits": [], "stdout": out,
                          "error": (err.strip().splitlines() or ["Preview process failed"])[-1],
                          "error_line": None}
        self.finished.emit(result)
        if self._pending is not None:
            self._start()

    def shutdown(self):
        self._debounce.stop()
        if self._proc is not None:
            self._proc.kill()
            self._proc.waitForFinished(1000)
