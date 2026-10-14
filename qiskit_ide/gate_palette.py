"""A row of gate buttons that write Qiskit code into the editor."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

# (label, method, argument template, tooltip)
GATES = [
    ("H", "h", "0", "Hadamard"),
    ("X", "x", "0", "Pauli-X (NOT)"),
    ("Y", "y", "0", "Pauli-Y"),
    ("Z", "z", "0", "Pauli-Z"),
    ("S", "s", "0", "S (√Z)"),
    ("T", "t", "0", "T (π/8)"),
    ("RX", "rx", "pi / 2, 0", "X rotation (angle, qubit)"),
    ("RY", "ry", "pi / 2, 0", "Y rotation (angle, qubit)"),
    ("RZ", "rz", "pi / 2, 0", "Z rotation (angle, qubit)"),
    ("CX", "cx", "0, 1", "Controlled-NOT (control, target)"),
    ("CZ", "cz", "0, 1", "Controlled-Z"),
    ("SWAP", "swap", "0, 1", "Swap two qubits"),
    ("CCX", "ccx", "0, 1, 2", "Toffoli (control, control, target)"),
    ("Barrier", "barrier", "", "Barrier across all qubits"),
    ("Measure", "measure", "0, 0", "Measure (qubit, clbit)"),
    ("Measure all", "measure_all", "", "Measure every qubit"),
]


class GatePalette(QWidget):
    gateRequested = Signal(str, str)  # method, argument template

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)
        self.target = QLabel()
        self.target.setStyleSheet("color:#7f848e;")
        layout.addWidget(self.target)
        for label, method, args, tip in GATES:
            b = QToolButton()
            b.setText(label)
            b.setToolTip(f"{tip}\nInserts .{method}({args})")
            b.setStyleSheet(
                "QToolButton { background:#2f3542; color:#61afef; border:1px solid #3e4451;"
                " border-radius:3px; padding:2px 6px; font-weight:bold; }"
                "QToolButton:hover { background:#3e4451; }")
            b.clicked.connect(lambda _=False, m=method, a=args: self.gateRequested.emit(m, a))
            layout.addWidget(b)
        layout.addStretch(1)
        self.set_target("qc")

    def set_target(self, name):
        self.target.setText(f"Add to <b style='color:#e5c07b'>{name}</b>:")
