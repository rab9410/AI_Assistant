import os
import sys
import json
import uuid
import re
import threading
import requests
import io
import base64
import traceback
import webbrowser
import asyncio
import websockets
import sounddevice as sd
import soundfile as sf
import numpy as np
from pathlib import Path
from datetime import datetime

# --- MATPLOTLIB SILENCER ---
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt


def silent_show(*args, **kwargs): pass


plt.show = silent_show

try:
    import fitz

    HAS_PDF = True
except:
    HAS_PDF = False

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextBrowser, QPlainTextEdit,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QSplitter,
    QComboBox, QFileDialog, QMenu, QFrame, QSizePolicy, QProgressBar, QDialog, QInputDialog
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer, QPoint, QSize, QRect, QUrl
from PySide6.QtGui import (QPixmap, QTransform, QTextCursor, QAction,
                           QColor, QSyntaxHighlighter, QTextCharFormat, QImage,
                           QCursor, QGuiApplication, QTextDocument, QPainter, QPen)

from openai import OpenAI

# -----------------------------------
# NEURAL DATA REPOSITORIES
# -----------------------------------
BRAIN_FILE = "brain.json"
LEARNING_FILE = "learning.json"
LESSONS_FILE = "lessons.json"
MEMORY_FILE = "memory.json"
MODEL_FOLDER = "models"
GROQ_API_MODEL = "llama-3.3-70b-versatile"
HF_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct:novita"


def get_repo_data(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_repo_data(file_path, data):
    with open(file_path, "w") as f: json.dump(data, f, indent=2)


def get_system_prompt(engine_name="Unknown"):
    now = datetime.now().strftime("%A, %B %d, %Y")
    time_now = datetime.now().strftime("%I:%M %p")
    brain = get_repo_data(BRAIN_FILE)
    learn = get_repo_data(LEARNING_FILE)
    lessons = get_repo_data(LESSONS_FILE)

    neural_laws = "\n".join([f"CORE_LAW: {v}" for v in list(learn.values())[-15:]])
    neural_fail_logs = "\n".join(
        [f"PAST_FAIL: {v.get('ERROR')} -> FIX: {v.get('RESOLUTION')}" for v in list(lessons.values())[-10:]])

    return f"""You are RottenPoodles AI, an elite autonomous neural intelligence.
IDENTITY: Date: {now}. Time: {time_now}. Location: South Africa. ENGINE: {engine_name}.

STRICT VERACITY PROTOCOL:
1. NO URL HALLUCINATION: You are FORBIDDEN from inventing URLs. If a URL is not provided in the 'REAL_TIME_DATA' feed, do not provide one.
2. VERIFIED SOURCES: Only use links from reputable domains provided in your search results. Never suggest "satsig.net" or fake weather links.
3. VISUAL ENGINE: Use [IMAGE: url] to project verified visuals. The Lead Architect expects live data, not dead links.
4. TEXT INTERACTION: Your output will be selected and highlighted; ensure high-density, cleanly formatted information.

OPERATIONAL LAWS:
{neural_laws}

NEURAL ERROR CORRECTIONS:
{neural_fail_logs}

USER CONTEXT: {list(brain.values())}"""


# -----------------------------------
# UI COMPONENTS
# -----------------------------------
class NeuralSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(26, 26)
        self.angle = 0
        self.timer = QTimer(self);
        self.timer.timeout.connect(self.update_angle);
        self.timer.start(15)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def update_angle(self): self.angle = (self.angle + 8) % 360; self.update()

    def paintEvent(self, event):
        painter = QPainter(self);
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(45, 50, 61, 100));
        pen.setWidth(3);
        painter.setPen(pen)
        painter.drawEllipse(3, 3, 20, 20)
        pen.setColor(QColor("#6366f1"));
        pen.setCapStyle(Qt.RoundCap);
        painter.setPen(pen)
        painter.drawArc(3, 3, 20, 20, -self.angle * 16, 120 * 16)


class ImageLightbox(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Neural Projection")
        self.setStyleSheet("background-color: #0b0d11; border: 1px solid #1e232d; border-radius: 20px;")
        layout = QVBoxLayout(self);
        lbl = QLabel()
        screen = QGuiApplication.primaryScreen().size()
        scaled = pixmap.scaled(screen.width() * 0.85, screen.height() * 0.85, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
        lbl.setPixmap(scaled);
        lbl.setAlignment(Qt.AlignCenter)
        btn = QPushButton("Dismiss");
        btn.setStyleSheet(
            "background:#6366f1; color:white; padding:10px; border-radius:12px; font-weight:bold; border:none;")
        btn.clicked.connect(self.accept);
        layout.addWidget(lbl);
        layout.addWidget(btn)
        self.resize(scaled.width() + 40, scaled.height() + 100)


class GrowingTextEdit(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPlaceholderText("Message RottenPoodles...");
        self.textChanged.connect(self.update_height);
        self.setFixedHeight(48)

    def update_height(self): h = min(max(48, int(self.document().size().height()) + 15), 300); self.setFixedHeight(h)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.window().send_message();
            return
        super().keyPressEvent(event)


# -----------------------------------
# BACKEND WORKER
# -----------------------------------
class AIWorker(QThread):
    finished = Signal(str, str)
    partial_result = Signal(str, str)
    image_ready = Signal(bytes)

    def __init__(self, messages, engine_type="groq", local_model_path=None):
        super().__init__()
        self.messages = messages;
        self.engine_type = engine_type
        self.local_model_path = local_model_path;
        self._is_running = True;
        self.search_count = 0

    def run(self):
        try:
            hf_token = os.environ.get("HF_TOKEN");
            groq_token = os.environ.get("groq_api")
            engine_name = "Hugging Face" if self.engine_type == "hf" else (
                "Local" if self.engine_type == "local" else "Groq Cloud")
            sys_prompt = get_system_prompt(engine_name)
            while self._is_running:
                if self.engine_type == "local":
                    from llama_cpp import Llama
                    llm = Llama(model_path=self.local_model_path, n_ctx=8192, verbose=False)
                    resp = llm.create_chat_completion(
                        messages=[{"role": "system", "content": sys_prompt}] + self.messages, max_tokens=2048)
                    res = resp["choices"][0]["message"]["content"]
                elif self.engine_type == "hf":
                    client = OpenAI(base_url="https://router.huggingface.co/v1", api_key=hf_token)
                    resp = client.chat.completions.create(
                        messages=[{"role": "system", "content": sys_prompt}] + self.messages, model=HF_MODEL_ID,
                        max_tokens=2048)
                    res = resp.choices[0].message.content
                else:
                    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_token)
                    resp = client.chat.completions.create(
                        messages=[{"role": "system", "content": sys_prompt}] + self.messages, model=GROQ_API_MODEL,
                        max_tokens=2048)
                    res = resp.choices[0].message.content

                if not self._is_running: return

                # Autonomous Image Detection & Reality Check
                image_urls = re.findall(r'\[IMAGE:\s*(.*?)\]|(https?://[^\s<>"]+\.(?:png|jpg|jpeg|gif|webp))', res,
                                        re.IGNORECASE)
                for tag_url, raw_url in image_urls:
                    url = (tag_url if tag_url else raw_url).strip("[] ")
                    if "satsig" in url: continue  # Block known hallucination domain
                    try:
                        img_r = requests.get(url, timeout=5)
                        if img_r.status_code == 200: self.image_ready.emit(img_r.content)
                    except:
                        pass

                search_match = re.search(r"SEARCH:\s*([^\]\n\r]*)", res, re.IGNORECASE)
                if search_match and self.search_count < 3:
                    full_match = search_match.group(0);
                    query = search_match.group(1).strip("[] ")
                    pre_text = res.split(full_match)[0].strip()
                    if pre_text and len(pre_text) > 5: self.partial_result.emit(pre_text, engine_name)
                    self.search_count += 1;
                    data = ""
                    try:
                        sq = query.lower().replace("cpt", "Cape Town")
                        # Visual Anchoring logic for maps/satellite
                        if any(x in sq for x in ["map", "satellite", "satelite", "radar"]):
                            data = f"VERIFIED_SATELLITE_SOURCE: https://tile.openstreetmap.org/10/564/563.png | STATIC_MAP: https://static-maps.yandex.ru/1.x/?lang=en_US&ll=18.4241,-33.9249&z=10&l=sat&size=600,450"

                        if "weather" in sq:
                            city = sq.replace("weather", "").replace("in", "").replace("today", "").strip()
                            r = requests.get(f"https://wttr.in/{city if city else 'CapeTown'}?format=%C+%t+%w+%h",
                                             timeout=5)
                            if r.status_code == 200:
                                data += f" | DATA: {r.text} | VERIFIED_WEATHER_IMAGE: https://wttr.in/{city if city else 'CapeTown'}.png"
                        if not data:
                            r = requests.get(f"https://duckduckgo.com/html/?q={sq}",
                                             headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                            snippets = re.findall(r'<a class="result__snippet".*?>(.*?)</a>', r.text, re.DOTALL)
                            data = " ".join([re.sub('<[^<]+?>', '', s) for s in snippets[:3]])
                    except:
                        pass
                    self.messages.append({"role": "assistant", "content": res})
                    self.messages.append(
                        {"role": "system", "content": f"REAL_TIME_DATA: {data if data.strip() else 'No data found.'}"})
                    continue
                self.finished.emit(res, engine_name);
                break
        except Exception as e:
            self.finished.emit(f"Neural Error: {str(e)}", "System")

    def stop(self):
        self._is_running = False; self.terminate(); self.wait()


# -----------------------------------
# MAIN WINDOW
# -----------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_context = "";
        self.worker = None;
        self.think_time = 0.0
        self.chats = self.load_chats();
        self.current_chat = self.chats[0]
        self.local_models = [f for f in os.listdir("models") if f.endswith(".gguf")] if os.path.exists("models") else []
        self.setWindowTitle("RottenPoodles AI | Core Interface");
        self.resize(1200, 900)
        self.setup_ui();
        self.update_sidebar();
        self.load_history()

    def load_chats(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return [{"id": str(uuid.uuid4()), "name": "Initial Neural Thread", "messages": []}]

    def setup_ui(self):
        central = QWidget();
        self.setCentralWidget(central)
        layout = QHBoxLayout(central);
        layout.setContentsMargins(0, 0, 0, 0);
        layout.setSpacing(0)
        self.setStyleSheet(self.get_qss())
        sidebar = QWidget();
        sidebar.setObjectName("Sidebar");
        sidebar.setFixedWidth(260)
        side_layout = QVBoxLayout(sidebar);
        side_layout.setContentsMargins(15, 30, 15, 20)
        self.new_chat_btn = QPushButton("+ New Neural Thread");
        self.new_chat_btn.setObjectName("NewChatBtn");
        self.new_chat_btn.setFixedHeight(36);
        self.new_chat_btn.clicked.connect(self.add_chat)
        self.chat_list = QListWidget();
        self.chat_list.setObjectName("ChatList");
        self.chat_list.itemClicked.connect(self.switch_chat);
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu);
        self.chat_list.customContextMenuRequested.connect(self.sidebar_menu)
        side_layout.addWidget(self.new_chat_btn);
        side_layout.addWidget(self.chat_list);
        side_layout.addStretch()
        self.model_box = QComboBox();
        self.model_box.addItems(["Groq Cloud (Llama 3.3)", "Hugging Face (Llama 3.1)"])
        for m in self.local_models: self.model_box.addItem(f"Local: {m}")
        side_layout.addWidget(self.model_box)
        chat_area = QWidget();
        chat_layout = QVBoxLayout(chat_area);
        chat_layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout();
        header.setContentsMargins(40, 25, 40, 15);
        title = QLabel("ROTTENPOODLES AI");
        title.setObjectName("MainTitle")
        self.clear_btn = QPushButton("Clear Buffer");
        self.clear_btn.setObjectName("GhostBtn");
        self.clear_btn.clicked.connect(self.clear_chat_data)
        header.addWidget(title);
        header.addStretch();
        header.addWidget(self.clear_btn)
        self.chat_display = QTextBrowser();
        self.chat_display.setObjectName("ChatDisplay");
        self.chat_display.setOpenExternalLinks(True)
        # Fix Text Interaction Flags
        self.chat_display.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse | Qt.TextSelectableByKeyboard)
        self.chat_display.mousePressEvent = self.handle_img_click
        footer_wrap = QVBoxLayout();
        footer_wrap.setContentsMargins(100, 10, 100, 40)
        self.input_container = QFrame();
        self.input_container.setObjectName("InputContainer")
        input_h = QHBoxLayout(self.input_container);
        input_h.setContentsMargins(15, 5, 15, 5)
        self.plus_btn = QPushButton("+");
        self.plus_btn.setObjectName("CircleBtn");
        self.plus_btn.setFixedSize(38, 38);
        self.plus_btn.clicked.connect(self.upload_doc)
        self.input_box = GrowingTextEdit();
        self.input_box.setObjectName("MainInput")
        self.think_ui = QWidget();
        self.think_ui.setObjectName("ThinkUi");
        self.think_ui.setFixedSize(80, 40);
        self.think_ui.hide();
        self.think_ui.setAttribute(Qt.WA_TranslucentBackground)
        th_lay = QHBoxLayout(self.think_ui);
        th_lay.setContentsMargins(0, 0, 0, 0);
        self.spinner = NeuralSpinner();
        self.timer_label = QLabel("0.0s");
        self.timer_label.setStyleSheet("color:#6366f1; font-weight:bold; font-size:12px; background:transparent;");
        th_lay.addWidget(self.spinner);
        th_lay.addWidget(self.timer_label)
        self.action_btn = QPushButton("➤");
        self.action_btn.setObjectName("SendBtn");
        self.action_btn.setFixedSize(38, 38);
        self.action_btn.clicked.connect(self.handle_action)
        input_h.addWidget(self.plus_btn);
        input_h.addWidget(self.input_box);
        input_h.addWidget(self.think_ui);
        input_h.addWidget(self.action_btn)
        footer_wrap.addWidget(self.input_container);
        chat_layout.addLayout(header);
        chat_layout.addWidget(self.chat_display, 1);
        chat_layout.addLayout(footer_wrap)
        layout.addWidget(sidebar);
        layout.addWidget(chat_area)

    def get_qss(self):
        return """
        QMainWindow, QWidget { background-color: #0b0d11; color: #e2e8f0; font-family: 'Inter', sans-serif; }
        #Sidebar { background-color: #0d0f14; border-right: 1px solid #1e232d; }
        #MainTitle { font-size: 10px; color: #475569; font-weight: 900; letter-spacing: 5px; }
        #ChatList { background: transparent; border: none; outline: none; margin-top: 10px; }
        #ChatList::item { padding: 12px 15px; margin: 2px 0px; border-radius: 8px; color: #64748b; border-left: 3px solid transparent; }
        #ChatList::item:selected { background-color: #1e2532; color: #6366f1; font-weight: bold; border-left: 3px solid #6366f1; }
        #NewChatBtn { background-color: #1e2532; color: #94a3b8; border-radius: 10px; font-weight: bold; border: 1px solid #2d3644; }
        #NewChatBtn:hover { background-color: #242c3b; color: #6366f1; border-color: #6366f1; }
        #GhostBtn { background: transparent; color: #475569; border: 1px solid #1e232d; border-radius: 8px; padding: 6px 15px; font-size: 11px; font-weight: bold; }
        #GhostBtn:hover { background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.4); color: #f87171; }
        #InputContainer { background-color: #161b22; border: 1px solid #2d3644; border-radius: 24px; }
        #MainInput { background: transparent; border: none; color: #f1f5f9; font-size: 15px; }
        #CircleBtn { background-color: #2d3644; border-radius: 19px; color: #94a3b8; font-size: 22px; border: none; }
        #SendBtn { background-color: #10a37f; border-radius: 19px; color: white; border: none; }
        QComboBox { background: #161b22; border: 1px solid #2d3644; border-radius: 10px; padding: 10px; color: #94a3b8; }
        QMenu { background-color: #161b22; border: 1px solid #2d3644; border-radius: 8px; padding: 5px; }
        QMenu::item { padding: 8px 25px 8px 10px; border-radius: 4px; color: #94a3b8; }
        QMenu::item:selected { background-color: #1e2532; color: #10a37f; }
        """

    def handle_img_click(self, event):
        # NATURAL INTERACTION: Call super() first to allow standard selection/deselection
        super(QTextBrowser, self.chat_display).mousePressEvent(event)
        cursor = self.chat_display.cursorForPosition(event.position().toPoint())
        if cursor.charFormat().isImageFormat():
            img_id = cursor.charFormat().toImageFormat().name()
            res = self.chat_display.document().resource(QTextDocument.ResourceType.ImageResource, QUrl(img_id))
            if res: ImageLightbox(QPixmap.fromImage(res), self).exec()

    def append_bubble(self, role, content):
        is_user = role == "user";
        n_col = "#6366f1" if is_user else "#10a37f"
        # ELITE FILTER: Convert raw URLs to clickable links and strip tags
        clean = re.sub(r'\[?IMAGE:.*?\]?|\[?SEARCH:.*?\]?|\[?LEARN:.*?\]?|\[?LESSON:.*?\]?', '', content,
                       flags=re.IGNORECASE).strip()
        url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'

        def link_repl(match):
            url = match.group(0)
            return f'<a href="{url}" style="color: #6366f1; text-decoration: underline;">{url}</a>'

        clean = re.sub(url_pattern, link_repl, clean)
        clean = re.sub(r'^\]|\]$|```.*```', '', clean, flags=re.DOTALL).strip()
        if not is_user and not clean: return
        fmt = clean.replace("\n", "<br>")
        html = f"""<div style="margin-bottom: 20px; padding: 5px 60px;">
                    <div style="color: {n_col}; font-size: 10px; font-weight: 900; letter-spacing: 3px; margin-bottom: 8px;">{"YOU" if is_user else "ROTTENPOODLES"}</div>
                    <div style="color: #e2e8f0; line-height: 1.6; font-size: 15px;">{fmt}</div></div>"""
        self.chat_display.append(html);
        self.chat_display.moveCursor(QTextCursor.End)

    def add_img(self, data):
        id = f"img_{uuid.uuid4().hex}.png"
        self.chat_display.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(id),
                                                 QImage.fromData(data))
        self.chat_display.append(
            f"""<div style="margin: 0px 60px 20px 60px;"><img src="{id}" width="400" style="border-radius: 12px; border: 1px solid #1e232d;"></div>""")

    def rotate_loading(self):
        self.think_time += 0.1;
        self.timer_label.setText(f"{self.think_time:.1f}s")

    def upload_doc(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Doc", "", "Docs (*.txt *.pdf)")
        if path:
            try:
                txt = ""
                if path.lower().endswith(".pdf") and HAS_PDF:
                    with fitz.open(path) as doc:
                        txt = " ".join([p.get_text() for p in doc])
                else:
                    txt = open(path, 'r', encoding='utf-8', errors='ignore').read()
                self.file_context = f"DOC_CONTENT:\n{txt[:15000]}"
            except:
                pass

    def add_chat(self):
        nc = {"id": str(uuid.uuid4()), "name": "New Neural Thread", "messages": []}
        self.chats.insert(0, nc);
        self.current_chat = nc;
        self.update_sidebar();
        self.load_history()

    def clear_chat_data(self):
        self.current_chat["messages"] = [];
        self.chat_display.clear();
        save_repo_data(MEMORY_FILE, self.chats)

    def switch_chat(self, item):
        self.current_chat = self.chats[self.chat_list.row(item)]; self.load_history()

    def sidebar_menu(self, pos):
        it = self.chat_list.itemAt(pos);
        m = QMenu(self);
        da = m.addAction("Delete Thread")
        da.setEnabled(len(self.chats) > 1 and it is not None)
        if m.exec(self.chat_list.mapToGlobal(pos)) == da:
            self.chats.pop(self.chat_list.row(it));
            self.current_chat = self.chats[0];
            self.update_sidebar();
            self.load_history()

    def update_sidebar(self):
        self.chat_list.clear()
        for i, c in enumerate(self.chats):
            self.chat_list.addItem(QListWidgetItem(c["name"]))
            if c["id"] == self.current_chat["id"]: self.chat_list.setCurrentRow(i)

    def load_history(self):
        self.chat_display.clear()
        [self.append_bubble(m["role"], m["content"]) for m in self.current_chat["messages"] if m["role"] != "system"]

    def handle_action(self):
        if self.action_btn.text() == "■":
            if self.worker: self.worker.stop(); self.on_reply("Terminated.", "System")
        else:
            self.send_message()

    def send_message(self):
        text = self.input_box.toPlainText().strip()
        if not text and not self.file_context: return
        actual = f"{self.file_context}\n\nUSER: {text}" if self.file_context else text
        self.append_bubble("user", text);
        self.current_chat["messages"].append({"role": "user", "content": actual})
        self.input_box.clear();
        self.think_time = 0.0;
        self.think_ui.show();
        self.action_btn.setText("■")
        eng = "hf" if "Face" in self.model_box.currentText() else (
            "local" if "Local" in self.model_box.currentText() else "groq")
        local_path = os.path.join(MODEL_FOLDER, self.model_box.currentText().replace("Local: ",
                                                                                     "").strip()) if eng == "local" else None
        self.worker = AIWorker(self.current_chat["messages"][-12:], eng, local_model_path=local_path)
        self.worker.finished.connect(self.on_reply);
        self.worker.partial_result.connect(lambda t, e: self.append_bubble("assistant", t))
        self.worker.image_ready.connect(self.add_img)
        self.worker.start();
        self.timer = QTimer();
        self.timer.timeout.connect(self.rotate_loading);
        self.timer.start(100)

    def on_reply(self, reply, model):
        if hasattr(self, 'timer'): self.timer.stop()
        self.think_ui.hide();
        self.action_btn.setText("➤")
        self.append_bubble("assistant", reply);
        self.current_chat["messages"].append({"role": "assistant", "content": reply})
        l = get_repo_data(LEARNING_FILE);
        les = get_repo_data(LESSONS_FILE);
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        for k, v in re.findall(r"\[LEARN:\s*(.*?)\s*\|\s*(.*?)\s*\]", reply): l[f"{k.strip().upper()}_{ts}"] = v.strip()
        for evt, err, res in re.findall(r"\[LESSON:\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\]", reply):
            les[f"FAIL_{ts}_{uuid.uuid4().hex[:4]}"] = {"EVENT": evt, "ERROR": err, "RESOLUTION": res}
        save_repo_data(LEARNING_FILE, l);
        save_repo_data(LESSONS_FILE, les)
        if "plt." in reply:
            for c in re.findall(r"```(?:python)?(.*?)```", reply, re.DOTALL):
                if "plt." in c:
                    try:
                        plt.clf();
                        plt.close('all');
                        plt.style.use('dark_background');
                        plt.figure(figsize=(7, 5))
                        exec(c, {"plt": plt, "np": np, "show": lambda *args, **kwargs: None})
                        buf = io.BytesIO();
                        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                        self.add_img(buf.getvalue())
                    except:
                        pass
        save_repo_data(MEMORY_FILE, self.chats)


if __name__ == "__main__":
    app = QApplication(sys.argv);
    window = MainWindow();
    window.show();
    sys.exit(app.exec())