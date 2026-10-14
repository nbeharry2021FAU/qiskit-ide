"""Code editor widget: line numbers, current-line and error-line highlights,
auto-indent and simple bracket handling."""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QTextCursor, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from .highlighter import PythonQiskitHighlighter

INDENT = "    "
PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}


class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    cursorLineChanged = Signal(int, int)  # line, column (1-based)

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet(
            "QPlainTextEdit { background:#282c34; color:#abb2bf; border:none;"
            " selection-background-color:#3e4451; }")

        self.highlighter = PythonQiskitHighlighter(self.document())
        self._error_line = None

        self._numbers = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_numbers)
        self.cursorPositionChanged.connect(self._refresh_extra_selections)
        self.cursorPositionChanged.connect(self._emit_cursor)
        self._update_margin()
        self._refresh_extra_selections()

    # ----- line numbers -------------------------------------------------
    def line_number_width(self):
        digits = max(3, len(str(self.blockCount())))
        return 16 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, *_):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_numbers(self, rect, dy):
        if dy:
            self._numbers.scroll(0, dy)
        else:
            self._numbers.update(0, rect.y(), self._numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._numbers.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self._numbers)
        painter.fillRect(event.rect(), QColor("#21252b"))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                if self._error_line == number + 1:
                    painter.setPen(QColor("#e06c75"))
                elif number == current:
                    painter.setPen(QColor("#d7dae0"))
                else:
                    painter.setPen(QColor("#636d83"))
                painter.drawText(0, top, self._numbers.width() - 8, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1

    # ----- highlights ---------------------------------------------------
    def set_error_line(self, line):
        """Mark a 1-based line as the error location (None clears it)."""
        if line != self._error_line:
            self._error_line = line
            self._refresh_extra_selections()
            self._numbers.update()

    def _refresh_extra_selections(self):
        selections = []
        cur = QTextEdit.ExtraSelection()
        cur.format.setBackground(QColor("#2c313c"))
        cur.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        cur.cursor = self.textCursor()
        cur.cursor.clearSelection()
        selections.append(cur)
        if self._error_line:
            block = self.document().findBlockByNumber(self._error_line - 1)
            if block.isValid():
                err = QTextEdit.ExtraSelection()
                err.format.setBackground(QColor(224, 108, 117, 60))
                err.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                err.cursor = QTextCursor(block)
                selections.append(err)
        self.setExtraSelections(selections)

    def _emit_cursor(self):
        c = self.textCursor()
        self.cursorLineChanged.emit(c.blockNumber() + 1, c.positionInBlock() + 1)

    # ----- editing behaviour -------------------------------------------
    def keyPressEvent(self, event):
        key, text = event.key(), event.text()
        cursor = self.textCursor()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            line = cursor.block().text()[:cursor.positionInBlock()]
            indent = line[: len(line) - len(line.lstrip())]
            if line.rstrip().endswith(":"):
                indent += INDENT
            super().keyPressEvent(event)
            self.insertPlainText(indent)
            return

        if key == Qt.Key.Key_Tab and not cursor.hasSelection():
            self.insertPlainText(INDENT)
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and cursor.hasSelection():
            self._shift_selection(dedent=key == Qt.Key.Key_Backtab)
            return

        if key == Qt.Key.Key_Backspace and not cursor.hasSelection():
            before = cursor.block().text()[:cursor.positionInBlock()]
            if before and before.strip() == "" and len(before) % 4 == 0:
                for _ in range(4):
                    cursor.deletePreviousChar()
                return

        if text in PAIRS and not cursor.hasSelection():
            nxt = self._next_char()
            if text in "\"'" and nxt == text:
                cursor.movePosition(QTextCursor.MoveOperation.Right)
                self.setTextCursor(cursor)
                return
            if text in "([{" or not (nxt.isalnum() or nxt == "_"):
                self.insertPlainText(text + PAIRS[text])
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Left)
                self.setTextCursor(cursor)
                return
        if text in ")]}" and self._next_char() == text:
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            self.setTextCursor(cursor)
            return

        if key == Qt.Key.Key_Slash and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.toggle_comment()
            return

        super().keyPressEvent(event)

    def _next_char(self):
        c = self.textCursor()
        text = c.block().text()
        i = c.positionInBlock()
        return text[i] if i < len(text) else ""

    def _selected_blocks(self):
        c = self.textCursor()
        doc = self.document()
        first = doc.findBlock(c.selectionStart())
        last = doc.findBlock(c.selectionEnd())
        if c.hasSelection() and last.position() == c.selectionEnd() and last != first:
            last = last.previous()
        return first, last

    def _shift_selection(self, dedent):
        first, last = self._selected_blocks()
        c = self.textCursor()
        c.beginEditBlock()
        block = first
        while True:
            bc = QTextCursor(block)
            if dedent:
                n = len(block.text()) - len(block.text().lstrip(" "))
                for _ in range(min(4, n)):
                    bc.deleteChar()
            else:
                bc.insertText(INDENT)
            if block == last:
                break
            block = block.next()
        c.endEditBlock()

    def toggle_comment(self):
        first, last = self._selected_blocks()
        blocks = []
        b = first
        while True:
            blocks.append(b)
            if b == last:
                break
            b = b.next()
        code = [b for b in blocks if b.text().strip()]
        uncomment = code and all(b.text().lstrip().startswith("#") for b in code)
        c = self.textCursor()
        c.beginEditBlock()
        for b in code:
            text = b.text()
            col = len(text) - len(text.lstrip())
            bc = QTextCursor(b)
            bc.movePosition(QTextCursor.MoveOperation.Right, n=col)
            if uncomment:
                n = 2 if text[col:col + 2] == "# " else 1
                for _ in range(n):
                    bc.deleteChar()
            else:
                bc.insertText("# ")
        c.endEditBlock()
