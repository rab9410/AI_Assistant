import re


def render_markdown_to_html(text):
    """
    Convert markdown text to styled HTML compatible with QTextBrowser.
    """

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    code_blocks = {}

    def _save_code(match):
        idx = len(code_blocks)
        key = f"@@CODEBLOCK_{idx}@@"
        lang = match.group(1) or "code"
        code = match.group(2).strip()

        block_html = (
            f'<div style="margin:10px 0;border-radius:8px;background:#0d0d0d;border:1px solid #333;">'
            f'<div style="background:#2f2f2f;color:#b4b4b4;padding:5px 12px;font-size:10px;'
            f'border-top-left-radius:8px;border-top-right-radius:8px;font-family:sans-serif;">{lang.upper()}</div>'
            f'<pre style="padding:12px;color:#e6edf3;font-family:Consolas,monospace;font-size:13px;">{code}</pre>'
            f'</div>'
        )

        code_blocks[key] = block_html
        return f"\n{key}\n"

    text = re.sub(r"```(\w*)\n(.*?)```", _save_code, text, flags=re.DOTALL)

    text = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.*?)_", r"<i>\1</i>", text)

    lines = text.split("\n")
    output = []

    for line in lines:
        stripped = line.strip()

        if stripped in code_blocks:
            output.append(code_blocks[stripped])
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            size = 22 - level * 2
            output.append(
                f'<div style="font-size:{size}px;font-weight:bold;margin:10px 0;color:#fff;">{title}</div>'
            )
            continue

        if stripped.startswith("- "):
            output.append(
                f'<div style="margin-left:12px;">• {stripped[2:]}</div>'
            )
            continue

        if stripped:
            output.append(
                f'<div style="margin-bottom:12px;line-height:1.6;">{stripped}</div>'
            )

    return "".join(output)