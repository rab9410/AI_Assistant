from PySide6.QtWidgets import (
    QPushButton, QWidget, QPlainTextEdit,
    QMenu, QDialog, QVBoxLayout, QLabel
)
from PySide6.QtCore import (
    QTimer, Qt, QSize, QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QPainter, QPen, QColor, QGuiApplication, QPixmap
)


class AnimatedButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_size = QSize(38, 38)
        self._anim = QPropertyAnimation(self, b"minimumSize")
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.OutBack)

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setEndValue(
            QSize(
                self.base_size.width() + 6,
                self.base_size.height() + 6
            )
        )
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setEndValue(self.base_size)
        self._anim.start()
        super().leaveEvent(event)


class NeuralSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(15)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _tick(self):
        self.angle = (self.angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(45, 50, 61, 100))
        pen.setWidth(3)
        p.setPen(pen)
        p.drawEllipse(3, 3, 20, 20)
        pen.setColor(QColor("#818cf8"))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(3, 3, 20, 20, -self.angle * 16, 120 * 16)


class GrowingTextEdit(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPlaceholderText("Message RottenPoodles...")
        self.textChanged.connect(self._resize)
        self.setFixedHeight(48)

    def _resize(self):
        h = min(
            max(48, int(self.document().size().height()) + 15),
            300
        )
        self.setFixedHeight(h)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            event.modifiers() & Qt.ShiftModifier
        ):
            w = self.window()
            if hasattr(w, "send_message"):
                w.send_message()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu {"
            "    background: #151a24;"
            "    color: #d1d5db;"
            "    border: 1px solid #1e2a3a;"
            "    border-radius: 10px;"
            "    padding: 6px 4px;"
            "    font-size: 13px;"
            "}"
            "QMenu::item {"
            "    padding: 9px 28px 9px 18px;"
            "    border-radius: 6px;"
            "    margin: 1px 4px;"
            "}"
            "QMenu::item:selected {"
            "    background: #1e2a3a;"
            "    color: #f1f5f9;"
            "}"
            "QMenu::item:disabled {"
            "    color: #475569;"
            "}"
            "QMenu::separator {"
            "    height: 1px;"
            "    background: #1e2532;"
            "    margin: 5px 12px;"
            "}"
        )

        undo = menu.addAction("  ⟲  Undo")
        undo.setEnabled(self.document().isUndoAvailable())
        redo = menu.addAction("  ⟳  Redo")
        redo.setEnabled(self.document().isRedoAvailable())

        menu.addSeparator()

        cut = menu.addAction("  ✂  Cut")
        cut.setEnabled(self.textCursor().hasSelection())
        copy = menu.addAction("  📋  Copy")
        copy.setEnabled(self.textCursor().hasSelection())
        paste = menu.addAction("  📥  Paste")
        paste.setEnabled(self.canPaste())

        menu.addSeparator()

        sel_all = menu.addAction("  Select All")
        clear = menu.addAction("  🗑  Clear All")
        clear.setEnabled(not self.document().isEmpty())

        action = menu.exec(event.globalPos())

        if action == undo:
            self.undo()
        elif action == redo:
            self.redo()
        elif action == cut:
            self.cut()
        elif action == copy:
            self.copy()
        elif action == paste:
            self.paste()
        elif action == sel_all:
            self.selectAll()
        elif action == clear:
            self.clear()


class ImageLightbox(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chart View")
        self.setStyleSheet(
            "background-color:#0b0d11;"
            "border:1px solid #1e2532;"
        )
        layout = QVBoxLayout(self)
        lbl = QLabel()
        screen = QGuiApplication.primaryScreen().size()
        scaled = pixmap.scaled(
            int(screen.width() * 0.85),
            int(screen.height() * 0.85),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        lbl.setPixmap(scaled)
        lbl.setAlignment(Qt.AlignCenter)
        btn = QPushButton("Dismiss")
        btn.setStyleSheet(
            "background:#818cf8; color:white; padding:10px;"
            "border-radius:12px; font-weight:bold; border:none;"
        )
        btn.clicked.connect(self.accept)
        layout.addWidget(lbl)
        layout.addWidget(btn)
        self.resize(scaled.width() + 40, scaled.height() + 100)