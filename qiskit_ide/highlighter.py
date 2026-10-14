"""Syntax highlighting for Python with extra emphasis on Qiskit names."""

import keyword
import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

QISKIT_CLASSES = [
    "QuantumCircuit", "QuantumRegister", "ClassicalRegister", "AncillaRegister",
    "Parameter", "ParameterVector", "Gate", "Instruction", "Measure", "Barrier",
    "Statevector", "Operator", "DensityMatrix", "SparsePauliOp", "Pauli",
    "transpile", "generate_preset_pass_manager", "StatevectorSampler",
    "StatevectorEstimator", "Sampler", "Estimator", "AerSimulator",
    "QFT", "QFTGate", "GroverOperator", "ZZFeatureMap", "EfficientSU2", "RealAmplitudes",
    "plot_histogram", "plot_bloch_multivector", "circuit_drawer",
]

QISKIT_GATES = [
    "h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx", "sxdg", "id",
    "rx", "ry", "rz", "p", "u", "r", "cx", "cy", "cz", "ch", "cp", "crx", "cry", "crz",
    "cu", "cs", "csdg", "csx", "swap", "iswap", "ccx", "ccz", "cswap", "mcx", "mcp",
    "rxx", "ryy", "rzz", "rzx", "ecr", "dcx", "measure", "measure_all", "barrier",
    "reset", "initialize", "prepare_state", "unitary", "append", "compose",
    "draw", "inverse", "decompose", "add_register", "if_test", "for_loop", "while_loop",
]


def _fmt(color, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


# A dark palette (One Dark inspired).
FORMATS = {
    "keyword": _fmt("#c678dd", bold=True),
    "builtin": _fmt("#56b6c2"),
    "qiskit": _fmt("#e5c07b", bold=True),
    "gate": _fmt("#61afef", bold=True),
    "number": _fmt("#d19a66"),
    "string": _fmt("#98c379"),
    "comment": _fmt("#7f848e", italic=True),
    "decorator": _fmt("#e06c75"),
    "self": _fmt("#e06c75", italic=True),
    "defname": _fmt("#61afef"),
}

BUILTINS = ["print", "range", "len", "list", "dict", "set", "tuple", "int", "float",
            "str", "bool", "enumerate", "zip", "map", "filter", "sum", "min", "max",
            "abs", "round", "isinstance", "super", "open", "sorted", "reversed", "any", "all"]


class PythonQiskitHighlighter(QSyntaxHighlighter):
    STATE_NONE, STATE_TRIPLE_SINGLE, STATE_TRIPLE_DOUBLE = 0, 1, 2

    def __init__(self, document):
        super().__init__(document)
        rules = [
            (r"\b(" + "|".join(keyword.kwlist) + r")\b", "keyword"),
            (r"\b(" + "|".join(BUILTINS) + r")\b(?=\s*\()", "builtin"),
            (r"\b(" + "|".join(QISKIT_CLASSES) + r")\b", "qiskit"),
            (r"\bqiskit(\.\w+)*\b", "qiskit"),
            (r"\.(" + "|".join(QISKIT_GATES) + r")\b(?=\s*\()", "gate"),
            (r"\b(pi|np\.pi|math\.pi)\b", "number"),
            (r"\b[0-9]+(\.[0-9]*)?([eE][+-]?[0-9]+)?j?\b", "number"),
            (r"\b0[xX][0-9a-fA-F]+\b", "number"),
            (r"^\s*@\w+(\.\w+)*", "decorator"),
            (r"\bself\b", "self"),
            (r"(?<=\bdef\s)\w+|(?<=\bclass\s)\w+", "defname"),
        ]
        self._rules = [(re.compile(p), FORMATS[k]) for p, k in rules]
        # Strings and comments are scanned separately so keywords inside them
        # are not coloured.
        self._string_or_comment = re.compile(
            r"""(#.*$)|([rRbBuUfF]{0,2}"(?:[^"\\\n]|\\.)*"?)|([rRbBuUfF]{0,2}'(?:[^'\\\n]|\\.)*'?)"""
        )

    def highlightBlock(self, text):
        for regex, fmt in self._rules:
            for m in regex.finditer(text):
                start, end = m.span()
                if regex.pattern.startswith(r"\.("):
                    start += 1  # don't colour the dot
                self.setFormat(start, end - start, fmt)

        self.setCurrentBlockState(self.STATE_NONE)
        pos = self._triple_quotes(text)
        while pos < len(text):
            m = self._string_or_comment.search(text, pos)
            if not m:
                break
            s = m.group(0)
            if s.lstrip("rRbBuUfF").startswith(('"""', "'''")):
                # Hand off to the triple-quote scanner from here.
                pos = self._triple_quotes(text, m.start())
                continue
            kind = "comment" if m.group(1) else "string"
            self.setFormat(m.start(), len(s), FORMATS[kind])
            pos = m.end()
            if kind == "comment":
                break

    def _triple_quotes(self, text, start=None):
        """Handle multi-line strings. Returns the index to resume scanning at."""
        fmt = FORMATS["string"]
        prev = self.previousBlockState()
        if start is None:
            if prev not in (self.STATE_TRIPLE_SINGLE, self.STATE_TRIPLE_DOUBLE):
                return 0
            delim = "'''" if prev == self.STATE_TRIPLE_SINGLE else '"""'
            begin, search_from = 0, 0
        else:
            i = start
            while text[i] in "rRbBuUfF":
                i += 1
            delim = text[i:i + 3]
            begin, search_from = start, i + 3
        end = text.find(delim, search_from)
        if end == -1:
            self.setFormat(begin, len(text) - begin, fmt)
            self.setCurrentBlockState(
                self.STATE_TRIPLE_SINGLE if delim == "'''" else self.STATE_TRIPLE_DOUBLE)
            return len(text)
        self.setFormat(begin, end + 3 - begin, fmt)
        return end + 3
