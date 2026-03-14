import json
import os
import re
import io
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from PySide6.QtCore import QThread, Signal
from openai import OpenAI

from app.prompts import SYSTEM_PROMPT_TEMPLATE

from app.config import (
    MEMORY_FILE,
    GROQ_API_MODEL,
    HF_MODEL_ID
)

from app.rag import RAG_ENGINE
from app.tools import execute_tool_logic
from app.utils import get_repo_data, bg_save

class AIWorker(QThread):
    finished = Signal(str, str)
    image_ready = Signal(bytes)
    intermediate = Signal(str)

    INTERMEDIATE_PHRASES = [
        "let me check", "let me look", "let me search",
        "let me fetch", "let me get", "let me find",
        "let me pull", "let me grab", "let me retrieve",
        "i'll check", "i'll look", "i'll search",
        "i'll fetch", "i'll get", "i'll find",
        "i'll pull", "i'll grab", "i'll retrieve",
        "checking now", "searching now", "fetching now",
        "looking up", "looking into", "pulling up",
        "one moment", "hold on", "just a moment",
        "let me see what", "i'll see what",
        "searching for", "checking the", "fetching the",
        "let me query", "querying", "retrieving",
    ]

    def __init__(self, messages, engine_type="groq",
                 thread_id=""):
        super().__init__()
        self.messages = list(messages)
        self.engine_type = engine_type
        self.source_thread_id = thread_id
        self._is_running = True

    def _is_intermediate_reply(self, msg):
        if len(msg) > 280:
            return False
        lower = msg.lower()
        return any(
            phrase in lower
            for phrase in self.INTERMEDIATE_PHRASES
        )

    def run(self):
        try:
            query = self.messages[-1].get("content", "")
            know_overview = RAG_ENGINE.get_knowledge_overview()

            # Keep router disabled for now until the system is fully stable again
            know_ctx = RAG_ENGINE.get_knowledge(query)

            playbook_categories = ""

            mem_ctx = json.dumps(get_repo_data(MEMORY_FILE)) or "{}"
            time_str = datetime.now().strftime(
                "%A, %B %d, %Y, %I:%M %p (UTC+2)"
            )

            sys_p = SYSTEM_PROMPT_TEMPLATE.format(
                time_str=time_str,
                know_overview=know_overview,
                know_ctx=know_ctx,
                mem_ctx=mem_ctx,
                playbook_categories=playbook_categories
            )

            working_msgs = list(self.messages)
            intermediate_count = 0

            allowed_tools = {
                "weather", "search", "market",
                "crypto", "news", "currency", "time"
            }

            for iteration in range(10):
                if not self._is_running:
                    return

                if self.engine_type == "groq":
                    api_key = os.environ.get("groq_api", "")
                    base_url = "https://api.groq.com/openai/v1"
                    model = GROQ_API_MODEL
                else:
                    api_key = os.environ.get("HF_TOKEN", "")
                    base_url = "https://router.huggingface.co/v1"
                    model = HF_MODEL_ID

                if not api_key:
                    self.finished.emit(
                        "⚠️ API key not configured. Set the environment variable and restart.",
                        "System"
                    )
                    return

                client = OpenAI(base_url=base_url, api_key=api_key)
                full_msgs = [{"role": "system", "content": sys_p}] + working_msgs

                resp = client.chat.completions.create(
                    messages=full_msgs,
                    model=model,
                    max_tokens=4000,
                    temperature=0.3
                )

                raw = (resp.choices[0].message.content or "").strip()

                if not raw:
                    self.finished.emit(
                        "Empty response. Please try again.",
                        self.engine_type
                    )
                    return

                jd = None
                try:
                    jd = json.loads(raw)
                except json.JSONDecodeError:
                    objects = re.findall(r"\{.*?\}(?=\s*\{|\s*$)", raw, re.DOTALL)
                    if objects:
                        try:
                            jd = json.loads(objects[0])
                        except json.JSONDecodeError:
                            pass
                    else:
                        match = re.search(r"\{.*\}", raw, re.DOTALL)
                        if match:
                            try:
                                jd = json.loads(match.group(0))
                            except json.JSONDecodeError:
                                pass

                if jd is None or not isinstance(jd, dict):
                    self.finished.emit(raw, self.engine_type)
                    return

                mode = jd.get("mode", "").lower().strip()

                if mode == "tool":
                    t_type = jd.get("tool", "").strip().lower()
                    t_args = jd.get("arguments") or {}

                    if not isinstance(t_args, dict):
                        t_args = {}

                    if t_type not in allowed_tools:
                        working_msgs.append({
                            "role": "assistant",
                            "content": json.dumps(jd)
                        })
                        working_msgs.append({
                            "role": "system",
                            "content": (
                                f"Invalid tool requested: '{t_type}'. "
                                "That is NOT a real tool. "
                                "Playbooks and reasoning categories are internal guidance only, never tools. "
                                "You must now continue by either:\n"
                                "1. replying normally with mode='reply', or\n"
                                "2. requesting one of the ONLY valid tools: "
                                "weather, search, market, crypto, news, currency, time.\n"
                                "Do NOT request any other tool."
                            )
                        })
                        continue

                    result = execute_tool_logic(t_type, t_args)

                    working_msgs.append({
                        "role": "assistant",
                        "content": json.dumps(jd)
                    })
                    working_msgs.append({
                        "role": "system",
                        "content": (
                                "LIVE TOOL DATA (incorporate naturally — do NOT repeat raw):\n"
                                + result
                        )
                    })
                    continue

                elif mode == "chart":
                    chart_data = jd.get("chart")
                    if isinstance(chart_data, dict):
                        self._render_chart(chart_data)

                    working_msgs.append({
                        "role": "assistant",
                        "content": json.dumps(jd)
                    })
                    working_msgs.append({
                        "role": "system",
                        "content": (
                            "Chart rendered and displayed. Now provide a concise summary."
                        )
                    })
                    continue


                elif mode == "reply":

                    msg = jd.get("message", "")

                    if isinstance(msg, (dict, list)):

                        msg = json.dumps(msg, indent=2)

                    else:

                        msg = str(msg).strip()

                    # Safety cleanup in case model accidentally included JSON fragments

                    msg = re.sub(r'^\s*\{"mode".*?"message"\s*:\s*"', '', msg)

                    msg = re.sub(r'"\s*\}\s*$', '', msg)

                    if not msg:
                        msg = "Request processed."

                    # Memory learning

                    mem = get_repo_data(MEMORY_FILE)

                    updated = False

                    for tk, tv in re.findall(

                            r"\[LEARN:\s*(.*?)\s*\|\s*(.*?)\s*\]",

                            msg,

                            re.IGNORECASE

                    ):

                        key = tk.strip().upper()

                        mem[key] = tv.strip()

                        if "_timestamps" not in mem:
                            mem["_timestamps"] = {}

                        mem["_timestamps"][key] = datetime.now().isoformat()

                        updated = True

                    if updated:
                        bg_save(MEMORY_FILE, mem)

                    msg = re.sub(

                        r"\[LEARN:.*?\]",

                        "",

                        msg,

                        flags=re.IGNORECASE

                    ).strip()

                    self.finished.emit(msg, self.engine_type)

                    return

                else:
                    fallback = jd.get("message", str(jd))
                    self.finished.emit(str(fallback), self.engine_type)
                    return

            self.finished.emit(
                "Could not complete after multiple attempts. Please try rephrasing.",
                self.engine_type
            )

        except Exception as e:
            self.finished.emit(
                f"⚠️ Error: {str(e)}\n\nIf this persists, please restart.",
                "System"
            )

    def _render_chart(self, c):
        try:
            plt.close('all')
            plt.style.use('dark_background')

            ctype = c.get("type", "line").lower()
            x = c.get("x", [])
            y = c.get("y", [])
            title = c.get("title", "Data Visualisation")
            ylabel = c.get("y_label", "")
            xlabel = c.get("x_label", "")
            color = c.get("color", "#818cf8")

            fig, ax = plt.subplots(figsize=(9, 4.5))
            fig.patch.set_alpha(0)
            ax.set_facecolor("#0d1117")

            if ctype == "line":
                ax.plot(
                    x, y, color=color, marker='o',
                    linewidth=2.5, markersize=4,
                    markerfacecolor='white'
                )
                if y and all(
                        isinstance(v, (int, float)) for v in y
                ):
                    ax.fill_between(
                        range(len(y)), y,
                        alpha=0.08, color=color
                    )
            elif ctype == "bar":
                bars = ax.bar(
                    x, y, color=color, width=0.6, zorder=3
                )
                for bar in bars:
                    h = bar.get_height()
                    label = (
                        f'{h:,.2f}' if isinstance(h, float)
                        else str(h)
                    )
                    ax.annotate(
                        label,
                        xy=(
                            bar.get_x()
                            + bar.get_width() / 2, h
                        ),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha='center', va='bottom',
                        color='#94a3b8', fontsize=8
                    )
            elif ctype == "pie":
                n = max(len(y), 1)
                palette = plt.cm.coolwarm(
                    np.linspace(0.1, 0.9, n)
                )
                _, _, autotexts = ax.pie(
                    y, labels=x, autopct='%1.1f%%',
                    colors=palette, startangle=140,
                    wedgeprops=dict(
                        edgecolor='#0b0d11', linewidth=1.5
                    )
                )
                for at in autotexts:
                    at.set_color('white')
                    at.set_fontsize(9)
            elif ctype == "scatter":
                ax.scatter(
                    x, y, color=color, s=60,
                    alpha=0.8, edgecolors='white',
                    linewidth=0.5
                )
                if (len(x) > 2
                        and all(
                            isinstance(v, (int, float))
                            for v in x
                        )
                        and all(
                            isinstance(v, (int, float))
                            for v in y
                        )):
                    z = np.polyfit(x, y, 1)
                    p = np.poly1d(z)
                    xnp = np.linspace(min(x), max(x), 100)
                    ax.plot(
                        xnp, p(xnp), "--",
                        color="#f59e0b", alpha=0.6,
                        linewidth=1.5
                    )
            elif ctype == "histogram":
                bins = min(20, max(len(y), 5))
                ax.hist(
                    y, bins=bins, color=color,
                    edgecolor='#0b0d11', alpha=0.85
                )

            ax.set_title(
                title, color="#94a3b8", fontsize=11,
                pad=14, fontweight='bold'
            )
            if ylabel:
                ax.set_ylabel(
                    ylabel, color="#64748b", fontsize=9
                )
            if xlabel:
                ax.set_xlabel(
                    xlabel, color="#64748b", fontsize=9
                )
            ax.tick_params(colors="#475569", labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor("#1e232d")
            ax.grid(
                True, linestyle='--',
                alpha=0.12, color='#475569'
            )
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(
                buf, format='png', dpi=130,
                bbox_inches='tight', transparent=True
            )
            plt.close(fig)
            self.image_ready.emit(buf.getvalue())

        except Exception as e:
            self.finished.emit(
                f"⚠️ Chart render failed: {str(e)}",
                "System"
            )
