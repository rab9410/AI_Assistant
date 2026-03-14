import hashlib
import io
import json
import os
import re
import sys
import threading
from datetime import datetime

import numpy as np
import requests
import torch
import uuid
from pathlib import Path
from sentence_transformers import SentenceTransformer, util

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt


def silent_show(*args, **kwargs):
    pass


plt.show = silent_show

try:
    import fitz

    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

from PySide6.QtWidgets import (
    QMainWindow, QTextBrowser, QPlainTextEdit,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QComboBox,
    QFileDialog, QMenu, QFrame, QProgressBar, QDialog,
    QInputDialog, QApplication
)
from PySide6.QtCore import (
    QThread, Signal, Qt, QTimer, QSize, QRect, QUrl,
    QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import (
    QPixmap, QTextCursor, QColor, QImage, QGuiApplication,
    QTextDocument, QPainter, QPen, QFont
)

from openai import OpenAI

from app.config import (
    DATA_DIR, THREAD_DIR, SYS_DIR, KNOWLEDGE_DIR,
    MEMORY_FILE, THREADS_META, KNOWLEDGE_CACHE,
    KNOWLEDGE_MANIFEST, KNOWLEDGE_SUMMARIES,
    GROQ_API_MODEL, HF_MODEL_ID, MAX_THREAD_NAME_LEN
)
from app.prompts import SYSTEM_PROMPT_TEMPLATE

from app.rag import RAG_ENGINE

from app.utils import (
    get_repo_data, bg_save, read_thread_history,
    write_thread_history, truncate_name
)

from app.tools import execute_tool_logic

from app.sync_worker import SyncWorker

from app.ai_worker import AIWorker

from app.ui_components import (
    AnimatedButton, NeuralSpinner,
    GrowingTextEdit, ImageLightbox
)

from app.markdown_renderer import render_markdown_to_html

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_context = ""
        self.worker = None
        self.think_time = 0.0
        self.is_generating = False
        self._message_count = 0

        self.setup_ui()
        self._create_avatar_resources()
        self.think_timer = QTimer(self)
        self.think_timer.timeout.connect(self._tick_timer)

        self.chats = self._load_threads_meta()
        self.current_chat = (
            self.chats[0] if self.chats else self.add_chat()
        )
        self.setWindowTitle("RottenPoodles AI")
        self.resize(1200, 900)
        self.update_sidebar()
        self.load_history()

    def _load_threads_meta(self):
        if THREADS_META.exists():
            try:
                data = json.loads(
                    THREADS_META.read_text(encoding="utf-8")
                )
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return []

    # ── AVATAR RESOURCES ─────────────────────────────────────
    def _create_avatar_resources(self):
        avatar_size = 32

        f = QFont("Inter", 12)
        f.setWeight(QFont.Bold)

        self._ai_avatar = QImage(
            avatar_size,
            avatar_size,
            QImage.Format_ARGB32
        )
        self._ai_avatar.fill(QColor(0, 0, 0, 0))
        p = QPainter(self._ai_avatar)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#6366f1"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, avatar_size, avatar_size)
        p.setPen(QColor("white"))
        p.setFont(f)
        p.drawText(
            QRect(0, 0, avatar_size, avatar_size),
            Qt.AlignCenter,
            "R"
        )
        p.end()

        self._user_avatar = QImage(
            avatar_size,
            avatar_size,
            QImage.Format_ARGB32
        )
        self._user_avatar.fill(QColor(0, 0, 0, 0))
        p = QPainter(self._user_avatar)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#10b981"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, avatar_size, avatar_size)
        p.setPen(QColor("white"))
        p.setFont(f)
        p.drawText(
            QRect(0, 0, avatar_size, avatar_size),
            Qt.AlignCenter,
            "Y"
        )
        p.end()

    def _ensure_avatars(self):
        doc = self.chat_display.document()
        doc.addResource(
            QTextDocument.ImageResource,
            QUrl("avatar_ai"), self._ai_avatar
        )
        doc.addResource(
            QTextDocument.ImageResource,
            QUrl("avatar_user"), self._user_avatar
        )

    # ── UI SETUP ──────────────────────────────────────────────
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setStyleSheet(self._get_qss())

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(15, 30, 15, 20)

        self.new_chat_btn = QPushButton("+ New Thread")
        self.new_chat_btn.setObjectName("NewChatBtn")
        self.new_chat_btn.setFixedHeight(36)
        self.new_chat_btn.setToolTip(
            "Start a new conversation thread"
        )
        self.new_chat_btn.clicked.connect(self.add_chat)

        self.chat_list = QListWidget()
        self.chat_list.setObjectName("ChatList")
        self.chat_list.itemClicked.connect(self.switch_chat)
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(
            self.sidebar_menu
        )
        self.chat_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.chat_list.setWordWrap(False)
        self.chat_list.setTextElideMode(Qt.ElideRight)

        self.ingest_btn = QPushButton("⚙ Sync Knowledge")
        self.ingest_btn.setObjectName("GhostBtn")
        self.ingest_btn.setFixedHeight(34)
        self.ingest_btn.setToolTip(
            "Synchronise knowledge base from the sys/ folder"
        )
        self.ingest_btn.clicked.connect(self.start_sync)

        self.sync_status_label = QLabel("")
        self.sync_status_label.setStyleSheet(
            "color:#64748b; font-size:10px; font-weight:bold;"
        )
        self.sync_status_label.hide()

        self.sync_progress_bar = QProgressBar()
        self.sync_progress_bar.setFixedHeight(4)
        self.sync_progress_bar.setTextVisible(False)
        self.sync_progress_bar.setStyleSheet(
            "QProgressBar {"
            "    background:#1e232d; border:none;"
            "    border-radius:2px;"
            "}"
            "QProgressBar::chunk {"
            "    background:#818cf8; border-radius:2px;"
            "}"
        )
        self.sync_progress_bar.hide()

        self.model_box = QComboBox()
        self.model_box.addItems([
            "Groq Cloud (Llama 3.3)",
            "Hugging Face (Llama 3.1)"
        ])
        self.model_box.setToolTip("Select AI model backend")

        side_layout.addWidget(self.new_chat_btn)
        side_layout.addWidget(self.chat_list)
        side_layout.addStretch()
        side_layout.addWidget(self.ingest_btn)
        side_layout.addWidget(self.sync_status_label)
        side_layout.addWidget(self.sync_progress_bar)
        side_layout.addWidget(self.model_box)

        chat_area = QWidget()
        chat_layout = QVBoxLayout(chat_area)
        chat_layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        header.setContentsMargins(40, 20, 40, 10)
        title = QLabel("ROTTENPOODLES AI")
        title.setObjectName("MainTitle")
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("GhostBtn")
        self.clear_btn.setToolTip(
            "Clear conversation and start fresh"
        )
        self.clear_btn.clicked.connect(self.clear_chat_data)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.clear_btn)

        self.chat_display = QTextBrowser()
        self.chat_display.setObjectName("ChatDisplay")
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setTextInteractionFlags(
            Qt.TextSelectableByMouse
            | Qt.LinksAccessibleByMouse
            | Qt.TextSelectableByKeyboard
        )
        self.chat_display.mousePressEvent = (
            self._handle_img_click
        )
        self.chat_display.setContextMenuPolicy(
            Qt.CustomContextMenu
        )
        self.chat_display.customContextMenuRequested.connect(
            self._chat_context_menu
        )

        footer_wrap = QVBoxLayout()
        footer_wrap.setContentsMargins(80, 8, 80, 30)

        self.input_container = QFrame()
        self.input_container.setObjectName("InputContainer")
        input_h = QHBoxLayout(self.input_container)
        input_h.setContentsMargins(15, 5, 15, 5)

        self.plus_btn = AnimatedButton("+")
        self.plus_btn.setObjectName("CircleBtn")
        self.plus_btn.setFixedSize(38, 38)
        self.plus_btn.setToolTip(
            "Attach a document (PDF, TXT, MD, CSV, JSON, PY)"
        )
        self.plus_btn.clicked.connect(self.upload_doc)

        self.input_box = GrowingTextEdit()
        self.input_box.setObjectName("MainInput")

        self.think_ui = QWidget()
        self.think_ui.setObjectName("ThinkUi")
        self.think_ui.setFixedSize(80, 40)
        self.think_ui.hide()
        self.think_ui.setAttribute(Qt.WA_TranslucentBackground)
        th_lay = QHBoxLayout(self.think_ui)
        th_lay.setContentsMargins(0, 0, 0, 0)
        self.spinner = NeuralSpinner()
        self.timer_label = QLabel("0.0s")
        self.timer_label.setStyleSheet(
            "color:#818cf8; font-weight:bold; "
            "font-size:12px; background:transparent;"
        )
        th_lay.addWidget(self.spinner)
        th_lay.addWidget(self.timer_label)

        self.action_btn = AnimatedButton("➤")
        self.action_btn.setObjectName("SendBtn")
        self.action_btn.setFixedSize(38, 38)
        self.action_btn.setToolTip("Send message (Enter)")
        self.action_btn.clicked.connect(self.handle_action)

        input_h.addWidget(self.plus_btn)
        input_h.addWidget(self.input_box)
        input_h.addWidget(self.think_ui)
        input_h.addWidget(self.action_btn)
        footer_wrap.addWidget(self.input_container)

        chat_layout.addLayout(header)
        chat_layout.addWidget(self.chat_display, 1)
        chat_layout.addLayout(footer_wrap)

        layout.addWidget(sidebar)
        layout.addWidget(chat_area)

    # ── CONTEXT MENU ─────────────────────────────────────────
    def _context_menu_style(self):
        return (
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
            "QMenu::icon {"
            "    padding-left: 8px;"
            "}"
        )

    def _chat_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(self._context_menu_style())

        has_sel = self.chat_display.textCursor().hasSelection()

        copy_sel = menu.addAction("  📋  Copy Selected Text")
        copy_sel.setEnabled(has_sel)
        copy_all = menu.addAction("  📄  Copy Entire Chat")
        menu.addSeparator()
        regen = menu.addAction("  🔄  Regenerate Response")
        regen.setEnabled(not self.is_generating)
        menu.addSeparator()
        export_txt = menu.addAction("  💾  Export as Text")
        export_md = menu.addAction("  📝  Export as Markdown")
        menu.addSeparator()
        scroll_top = menu.addAction("  ⬆  Scroll to Top")
        scroll_bot = menu.addAction("  ⬇  Scroll to Bottom")
        menu.addSeparator()
        clear_act = menu.addAction("  🗑  Clear Chat")

        action = menu.exec(
            self.chat_display.mapToGlobal(pos)
        )

        if action == copy_sel:
            self.chat_display.copy()
        elif action == copy_all:
            QGuiApplication.clipboard().setText(
                self.chat_display.toPlainText()
            )
        elif action == regen:
            self._regenerate_last()
        elif action == export_txt:
            self._export_chat("txt")
        elif action == export_md:
            self._export_chat("md")
        elif action == scroll_top:
            self.chat_display.moveCursor(QTextCursor.Start)
        elif action == scroll_bot:
            self.chat_display.moveCursor(QTextCursor.End)
        elif action == clear_act:
            self.clear_chat_data()

    def _regenerate_last(self):
        if self.is_generating:
            return
        tid = self.current_chat['id']
        history = read_thread_history(tid)
        while history and history[-1].get("role") == "assistant":
            history.pop()
        if not history:
            return
        write_thread_history(tid, history)
        self.load_history()
        self.is_generating = True
        self.input_box.setEnabled(False)
        self.action_btn.setToolTip("Stop generation")
        self.think_time = 0.0
        self.think_ui.show()
        self.action_btn.setText("■")
        self.think_timer.start(100)
        eng = (
            "groq"
            if "Groq" in self.model_box.currentText()
            else "hf"
        )
        self.worker = AIWorker(
            history, engine_type=eng, thread_id=tid
        )
        self.worker.finished.connect(self._on_reply)
        self.worker.intermediate.connect(self._on_intermediate)
        self.worker.image_ready.connect(self.add_img)
        self.worker.start()

    def _export_chat(self, fmt="txt"):
        ext = ("Text Files (*.txt)" if fmt == "txt"
               else "Markdown Files (*.md)")
        default_name = (
            f"{self.current_chat.get('name', 'chat')}.{fmt}"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Chat", default_name, ext
        )
        if not path:
            return
        history = read_thread_history(
            self.current_chat['id']
        )
        lines = []
        for m in history:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user":
                label = "You" if fmt == "txt" else "### You"
                clean = re.sub(
                    r"ATTACHED_DOCUMENT\s*$$.*?$$:\n?",
                    "", content, flags=re.IGNORECASE
                ).strip()
                lines.append(f"{label}\n{clean}\n")
            elif role == "assistant":
                try:
                    jd = json.loads(content)
                    if isinstance(jd, dict) and jd.get(
                            "mode"
                    ) in ("tool", "chart"):
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass
                label = (
                    "RottenPoodles AI"
                    if fmt == "txt"
                    else "### RottenPoodles AI"
                )
                lines.append(f"{label}\n{content}\n")
        try:
            Path(path).write_text(
                "\n".join(lines), encoding="utf-8"
            )
            self.append_status(
                f"Chat exported to {Path(path).name}"
            )
        except Exception as e:
            self.append_status(f"Export failed: {str(e)}")

    # ── STYLESHEET ───────────────────────────────────────────
    def _get_qss(self):
        return (
            "QMainWindow, QWidget {"
            "    background-color: #0b0d11;"
            "    color: #e2e8f0;"
            "    font-family: 'Inter', 'Segoe UI',"
            "        'Helvetica Neue', sans-serif;"
            "}"
            "QScrollBar:vertical {"
            "    background: transparent;"
            "    width: 6px;"
            "    margin: 0;"
            "    border: none;"
            "}"
            "QScrollBar::handle:vertical {"
            "    background: rgba(255,255,255,0.08);"
            "    min-height: 40px;"
            "    border-radius: 3px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            "    background: rgba(255,255,255,0.15);"
            "}"
            "QScrollBar::add-line:vertical,"
            "QScrollBar::sub-line:vertical,"
            "QScrollBar::add-page:vertical,"
            "QScrollBar::sub-page:vertical {"
            "    background: none;"
            "    height: 0;"
            "}"
            "QScrollBar:horizontal {"
            "    background: transparent;"
            "    height: 0px;"
            "    border: none;"
            "}"
            "#Sidebar {"
            "    background-color: #0d0f14;"
            "    border-right: 1px solid #161b22;"
            "}"
            "#MainTitle {"
            "    font-size: 10px;"
            "    color: #3b4252;"
            "    font-weight: 900;"
            "    letter-spacing: 5px;"
            "}"
            "#ChatList {"
            "    background: transparent;"
            "    border: none;"
            "    outline: none;"
            "    margin-top: 10px;"
            "    font-size: 12px;"
            "}"
            "#ChatList::item {"
            "    padding: 10px 12px;"
            "    margin: 1px 0px;"
            "    border-radius: 8px;"
            "    color: #8892a4;"
            "    border-left: 3px solid transparent;"
            "}"
            "#ChatList::item:hover {"
            "    background-color: #111620;"
            "    color: #c8d0df;"
            "}"
            "#ChatList::item:selected {"
            "    background-color: #151c2a;"
            "    color: #a5b4fc;"
            "    font-weight: 600;"
            "    border-left: 3px solid #818cf8;"
            "}"
            "#NewChatBtn {"
            "    background-color: #111620;"
            "    color: #94a3b8;"
            "    border-radius: 10px;"
            "    font-weight: 600;"
            "    font-size: 12px;"
            "    border: 1px solid #1e2532;"
            "}"
            "#NewChatBtn:hover {"
            "    background-color: #1a2233;"
            "    color: #a5b4fc;"
            "    border-color: #818cf8;"
            "}"
            "#GhostBtn {"
            "    background: transparent;"
            "    color: #475569;"
            "    border: 1px solid #1a1f2b;"
            "    border-radius: 8px;"
            "    padding: 6px 15px;"
            "    font-size: 11px;"
            "    font-weight: bold;"
            "}"
            "#GhostBtn:hover {"
            "    background: rgba(129,140,248,0.08);"
            "    border-color: #818cf8;"
            "    color: #a5b4fc;"
            "}"
            "#CircleBtn {"
            "    background-color: #161b22;"
            "    border-radius: 19px;"
            "    color: #94a3b8;"
            "    font-size: 22px;"
            "    border: 1px solid #1e2532;"
            "}"
            "#CircleBtn:hover {"
            "    background-color: #1e2532;"
            "    color: #a5b4fc;"
            "    border-color: #818cf8;"
            "}"
            "#SendBtn {"
            "    background-color: #818cf8;"
            "    border-radius: 19px;"
            "    color: white;"
            "    border: none;"
            "    font-weight: bold;"
            "}"
            "#SendBtn:hover {"
            "    background-color: #6366f1;"
            "}"
            "#ChatDisplay {"
            "    background-color: #0b0d11;"
            "    border: none;"
            "    padding: 0px;"
            "    selection-background-color: #334155;"
            "    selection-color: #f1f5f9;"
            "}"
            "#InputContainer {"
            "    background-color: #111620;"
            "    border: 1px solid #1e2532;"
            "    border-radius: 24px;"
            "}"
            "#InputContainer:focus-within {"
            "    border-color: #334155;"
            "}"
            "#MainInput {"
            "    background: transparent;"
            "    border: none;"
            "    color: #f1f5f9;"
            "    font-size: 14px;"
            "    selection-background-color: #334155;"
            "}"
            "QComboBox {"
            "    background: #111620;"
            "    border: 1px solid #1e2532;"
            "    border-radius: 10px;"
            "    padding: 10px;"
            "    color: #94a3b8;"
            "    margin-top: 5px;"
            "    font-size: 11px;"
            "}"
            "QComboBox::drop-down {"
            "    border: none;"
            "}"
            "QComboBox QAbstractItemView {"
            "    background: #111620;"
            "    color: #94a3b8;"
            "    border: 1px solid #1e2532;"
            "    selection-background-color: #1e2532;"
            "    outline: none;"
            "}"
            "#ThinkUi {"
            "    background: transparent;"
            "    border: none;"
            "}"
            "QToolTip {"
            "    background-color: #1e2532;"
            "    color: #e2e8f0;"
            "    border: 1px solid #334155;"
            "    border-radius: 6px;"
            "    padding: 6px 10px;"
            "    font-size: 11px;"
            "}"
        )

    # ── SYNC CONTROLS ────────────────────────────────────────
    def start_sync(self):
        self.ingest_btn.setEnabled(False)
        self.sync_status_label.show()
        self.sync_progress_bar.show()
        self.sync_progress_bar.setRange(0, 100)
        self.sync_progress_bar.setValue(0)
        self._sync_anim_timer = QTimer(self)
        self._sync_anim_timer.timeout.connect(
            self._animate_sync
        )
        self._sync_anim_timer.start(500)
        self._sync_w = SyncWorker()
        self._sync_w.progress.connect(self._on_sync_progress)
        self._sync_w.finished.connect(self._on_sync_finished)
        self._sync_w.start()

    def _animate_sync(self):
        t = self.ingest_btn.text()
        if "..." in t:
            self.ingest_btn.setText("⚙ Syncing.")
        elif ".." in t:
            self.ingest_btn.setText("⚙ Syncing...")
        else:
            self.ingest_btn.setText("⚙ Syncing..")

    def _on_sync_progress(self, msg, val):
        self.sync_status_label.setText(msg)
        self.sync_progress_bar.setValue(val)

    def _on_sync_finished(self, count):
        self._sync_anim_timer.stop()
        self.ingest_btn.setEnabled(True)
        self.ingest_btn.setText("⚙ Sync Knowledge")
        self.sync_progress_bar.setValue(100)
        if count > 0:
            self.sync_status_label.setText(
                f"✓ {count} chunks indexed"
            )
            self.append_bubble(
                "assistant",
                f"Knowledge synchronised — {count} chunks "
                f"indexed and ready."
            )
        else:
            self.sync_status_label.setText(
                "Already up to date."
            )
        QTimer.singleShot(5000, self.sync_status_label.hide)
        QTimer.singleShot(5000, self.sync_progress_bar.hide)

    # ── DISPLAY HELPERS ──────────────────────────────────────
    def _handle_img_click(self, e):
        super(
            QTextBrowser, self.chat_display
        ).mousePressEvent(e)
        cursor = self.chat_display.cursorForPosition(
            e.position().toPoint()
        )
        fmt = cursor.charFormat()
        if fmt.isImageFormat():
            i_id = fmt.toImageFormat().name()
            res = self.chat_display.document().resource(
                QTextDocument.ResourceType.ImageResource,
                QUrl(i_id)
            )
            if res:
                pix = (
                    QPixmap.fromImage(res)
                    if isinstance(res, QImage) else res
                )
                if isinstance(pix, QPixmap):
                    ImageLightbox(pix, self).exec()

    def append_bubble(self, role, content):
        """Render a chat message in modern ChatGPT-style layout."""
        if role == "assistant":
            try:
                jd = json.loads(content)
                if isinstance(jd, dict) and jd.get("mode") in ("tool", "chart"):
                    return
            except (json.JSONDecodeError, TypeError):
                pass

        if role == "system":
            return

        is_user = role == "user"

        clean = re.sub(
            r"\[LEARN:.*?\]|REAL_TIME_DATA_RESULT:.*|TOOL RESULT.*|LIVE TOOL DATA.*|ATTACHED_DOCUMENT\s*\[.*?\]:\n?",
            "",
            content,
            flags=re.IGNORECASE | re.DOTALL
        ).strip()

        if not clean:
            return

        self._ensure_avatars()
        timestamp = datetime.now().strftime("%I:%M %p")

        bg_color = "#0f1720" if is_user else "#151a24"
        avatar_src = "avatar_user" if is_user else "avatar_ai"
        display_name = "You" if is_user else "RottenPoodles"

        rendered_body = clean if is_user else render_markdown_to_html(clean)

        html = (
            f'<div style="background-color:{bg_color}; padding:22px 0; border-bottom:1px solid #11161f;">'
            f'  <table width="100%" border="0" cellspacing="0" cellpadding="0">'
            f'    <tr>'
            f'      <td width="72"></td>'
            f'      <td width="44" valign="top">'
            f'        <img src="{avatar_src}" width="30" height="30">'
            f'      </td>'
            f'      <td style="padding-left:16px;">'
            f'        <div style="color:#ffffff; font-weight:700; font-size:13px; margin-bottom:6px;">'
            f'          {display_name} '
            f'          <span style="color:#7c8596; font-weight:400; font-size:11px;">{timestamp}</span>'
            f'        </div>'
            f'        <div style="color:#ececec; font-size:14px; line-height:1.65;">{rendered_body}</div>'
            f'      </td>'
            f'      <td width="72"></td>'
            f'    </tr>'
            f'  </table>'
            f'</div>'
        )

        self.chat_display.append(html)
        self.chat_display.moveCursor(QTextCursor.End)

    def append_status(self, text):
        """Render a system/status pill in the centre."""
        safe = (
            text
            .replace("&", "&")
            .replace("<", "<")
            .replace(">", ">")
        )
        html = (
            f'<div style="margin: 15px 0; text-align: center;">'
            f'<span style="background-color: #1e2532; color: #94a3b8; padding: 5px 12px; border-radius: 12px; font-size: 11px;">'
            f'{safe}'
            f'</span>'
            f'</div>'
        )
        self.chat_display.append(html)
        self.chat_display.moveCursor(QTextCursor.End)

    def add_img(self, data):
        """Render a chart image in a styled container."""
        img_id = f"img_{uuid.uuid4().hex}.png"
        qimg = QImage.fromData(data)
        if qimg.isNull():
            return
        self.chat_display.document().addResource(
            QTextDocument.ImageResource,
            QUrl(img_id), qimg
        )
        html = (
            f'<div style="margin: 20px 0; text-align: center;">'
            f'  <div style="display: inline-block; padding: 10px; background: #161b22; border: 1px solid #30363d; border-radius: 12px;">'
            f'    <img src="{img_id}"><br>'
            f'    <div style="color: #64748b; font-size: 11px; margin-top: 8px;">📊 Chart Generated | Click to expand</div>'
            f'  </div>'
            f'</div>'
        )
        self.chat_display.append(html)
        self.chat_display.moveCursor(QTextCursor.End)

    def _tick_timer(self):
        self.think_time += 0.1
        self.timer_label.setText(f"{self.think_time:.1f}s")

    # ── FILE UPLOAD ──────────────────────────────────────────
    def upload_doc(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "",
            "Documents (*.txt *.pdf *.md *.csv "
            "*.json *.py *.log)"
        )
        if not path:
            return
        try:
            if path.lower().endswith(".pdf") and HAS_PDF:
                doc = fitz.open(path)
                text = "\n".join(
                    page.get_text() for page in doc
                )
                doc.close()
            else:
                with open(
                        path, 'r', encoding='utf-8',
                        errors='ignore'
                ) as f:
                    text = f.read()
            fname = Path(path).name
            self.file_context = (
                f"ATTACHED_DOCUMENT [{fname}]:\n"
                f"{text[:12000]}"
            )
            self.append_bubble(
                "assistant",
                f"📎 Document attached: **{fname}** "
                f"({len(text):,} chars). "
                f"Ready for your question."
            )
        except Exception as e:
            self.append_bubble(
                "assistant",
                f"⚠️ Could not read file: {str(e)}"
            )

    # ── THREAD MANAGEMENT ────────────────────────────────────
    def add_chat(self):
        nc = {
            "id": str(uuid.uuid4()),
            "name": f"Thread {len(self.chats) + 1}"
        }
        self.chats.insert(0, nc)
        self.current_chat = nc
        self.file_context = ""
        if hasattr(self, 'chat_list'):
            self.update_sidebar()
            self.load_history()
            self.save_meta()
        return nc

    def clear_chat_data(self):
        tid = self.current_chat['id']
        path = THREAD_DIR / f"{tid}.json"
        if path.exists():
            path.write_text("[]", encoding="utf-8")
        self.chat_display.clear()
        self.file_context = ""
        self._message_count = 0

    def switch_chat(self, item):
        row = self.chat_list.row(item)
        if 0 <= row < len(self.chats):
            self.current_chat = self.chats[row]
            self.file_context = ""
            self.load_history()

    def sidebar_menu(self, pos):
        item = self.chat_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet(self._context_menu_style())

        rename_a = menu.addAction("  ✏️  Rename")
        dup_a = menu.addAction("  📋  Duplicate")
        menu.addSeparator()
        del_a = menu.addAction("  🗑  Delete")

        action = menu.exec(
            self.chat_list.mapToGlobal(pos)
        )
        idx = self.chat_list.row(item)

        if action == del_a:
            tid = self.chats[idx]['id']
            (THREAD_DIR / f"{tid}.json").unlink(
                missing_ok=True
            )
            self.chats.pop(idx)
            self.save_meta()
            self.current_chat = (
                self.chats[0] if self.chats
                else self.add_chat()
            )
            self.update_sidebar()
            self.load_history()

        elif action == rename_a:
            old_name = self.chats[idx]['name']
            new_name, ok = QInputDialog.getText(
                self, "Rename Thread",
                "New name:", text=old_name
            )
            if ok and new_name.strip():
                self.chats[idx]['name'] = truncate_name(
                    new_name.strip()
                )
                self.save_meta()
                self.update_sidebar()

        elif action == dup_a:
            src = self.chats[idx]
            new_id = str(uuid.uuid4())
            src_hist = read_thread_history(src['id'])
            nc = {
                "id": new_id,
                "name": truncate_name(
                    src['name'] + " (copy)"
                )
            }
            self.chats.insert(0, nc)
            write_thread_history(new_id, src_hist)
            self.current_chat = nc
            self.save_meta()
            self.update_sidebar()
            self.load_history()

    def update_sidebar(self):
        self.chat_list.clear()
        for i, c in enumerate(self.chats):
            display_name = truncate_name(
                c.get("name", "Thread")
            )
            item = QListWidgetItem(display_name)
            item.setToolTip(c.get("name", "Thread"))
            self.chat_list.addItem(item)
            if c["id"] == self.current_chat["id"]:
                self.chat_list.setCurrentRow(i)

    def save_meta(self):
        bg_save(THREADS_META, self.chats)

    def load_history(self):
        self.chat_display.clear()
        self._message_count = 0
        history = read_thread_history(
            self.current_chat['id']
        )
        for m in history:
            role = m.get("role", "")
            content = m.get("content", "")
            if role in ("user", "assistant"):
                self.append_bubble(role, content)

    # ── MESSAGE FLOW ─────────────────────────────────────────
    def handle_action(self):
        if self.action_btn.text() == "■":
            if self.worker:
                self.worker._is_running = False
            self._reset_after_reply()
            self.append_bubble(
                "assistant", "Generation stopped."
            )
        else:
            self.send_message()

    def send_message(self):
        if self.is_generating:
            return
        text = self.input_box.toPlainText().strip()
        if not text and not self.file_context:
            return

        self.is_generating = True
        self.input_box.setEnabled(False)
        self.action_btn.setToolTip("Stop generation")

        actual = (
            f"{self.file_context}\n\n{text}"
            if self.file_context else text
        )

        self.append_bubble("user", text)
        self.input_box.clear()
        self.file_context = ""

        self.think_time = 0.0
        self.think_ui.show()
        self.action_btn.setText("■")
        self.think_timer.start(100)

        tid = self.current_chat['id']
        history = read_thread_history(tid)
        history.append({"role": "user", "content": actual})
        write_thread_history(tid, history)

        eng = (
            "groq"
            if "Groq" in self.model_box.currentText()
            else "hf"
        )
        self.worker = AIWorker(
            history, engine_type=eng, thread_id=tid
        )
        self.worker.finished.connect(self._on_reply)
        self.worker.intermediate.connect(self._on_intermediate)
        self.worker.image_ready.connect(self.add_img)
        self.worker.start()

    def _on_intermediate(self, text):
        self.append_status(f"⟳ {text}")

    def _on_reply(self, reply_text, model_name):
        self._reset_after_reply()

        clean = reply_text.strip()
        if not clean:
            return

        self.append_bubble("assistant", clean)

        source_tid = (
            self.worker.source_thread_id
            if self.worker
            else self.current_chat['id']
        )
        history = read_thread_history(source_tid)
        history.append({
            "role": "assistant", "content": clean
        })

        if (len(history) == 2
                and source_tid == self.current_chat['id']):
            name = self.current_chat.get("name", "")
            if name.startswith("Thread "):
                first_msg = history[0].get("content", "")
                display_msg = re.sub(
                    r"ATTACHED_DOCUMENT\s*$$.*?$$:\n?",
                    "", first_msg,
                    flags=re.IGNORECASE
                ).strip()
                if display_msg:
                    self.current_chat["name"] = (
                        truncate_name(display_msg)
                    )
                    self.update_sidebar()

        write_thread_history(source_tid, history)
        self.save_meta()

    def _reset_after_reply(self):
        self.is_generating = False
        self.input_box.setEnabled(True)
        self.input_box.setFocus()
        self.think_timer.stop()
        self.think_ui.hide()
        self.action_btn.setText("➤")
        self.action_btn.setToolTip("Send message (Enter)")


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Inter", 10)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())