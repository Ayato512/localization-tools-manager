"""
本地化工具箱 - 启动器
=====================
双击本文件即可弹出工具菜单，点击按钮启动对应工具。

如果双击没反应，请先运行 "首次安装.bat"（Windows）或 "首次安装.command"（Mac）安装依赖。
"""
import sys
import os
import subprocess
import platform

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# ---- 工具清单 ---------------------------------------------------------
# 每一项：(显示名, 一句话说明, core/ 下的脚本文件名, 是否仅 Windows 可用)
TOOLS = [
    ("🔍  Excel 搜索器",       "在多个 Excel 文件 / 多个 Sheet 里跨表搜索内容",      "ExcelSearcher_Final.py",                       True),
    ("📝  语料对齐",           "中日文语料按标点同步拆分对齐（含模糊匹配）",         "corpus_tool.py",                                False),
    ("🔄  TMX 转换",           "把 Excel 双语对照表转成翻译记忆库 TMX 格式",         "tmx_tool.py",                                   False),
    ("📚  术语抽取",           "从中文语料里基于熵 + PMI 自动抽取术语候选",         "term extractor.py",                             False),
    ("📊  Excel 合并",         "把多个 Excel 文件按原样合并到一个工作簿",            "表格合并.py",                                   False),
    ("✂️  Excel 拆分",         "把一个多 Sheet 的 Excel 拆成多个独立文件（保留格式/图片/公式）", "表格拆分.py",                       False),
    ("📐  Excel 重排对齐",     "Excel 列重排、按下划线尾号对齐",                    "excel竖排改横排对齐.py",                        False),
    ("🎨  美术资产对照",       "调用 Gemini 模型对美术资产做 OCR / 对照比较",        "Asset Management 3.3 with Gemini.py",      False),
]


class Launcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("本地化工具箱")
        self.resize(560, 620)

        self.core_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
        self.is_windows = platform.system() == "Windows"

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        # 标题
        title = QLabel("🧰  本地化工具箱")
        title.setFont(QFont("", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("点击下方按钮启动对应工具")
        subtitle.setStyleSheet("color: #888;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #ddd;")
        layout.addWidget(line)
        layout.addSpacing(6)

        # 工具按钮列表
        for display_name, desc, script_name, win_only in TOOLS:
            row = QHBoxLayout()
            row.setSpacing(12)

            btn = QPushButton(display_name)
            btn.setMinimumHeight(48)
            btn.setMinimumWidth(180)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding-left: 16px;
                    font-size: 14px;
                    background-color: #f5f5f7;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #e8f0fe; border-color: #4a90e2; }
                QPushButton:pressed { background-color: #d6e4f8; }
            """)
            btn.clicked.connect(
                lambda _checked, s=script_name, w=win_only, n=display_name: self.run_tool(s, w, n)
            )

            label = QLabel(desc)
            label.setStyleSheet("color: #555; font-size: 12px;")
            label.setWordWrap(True)

            # Windows-only 标签
            if win_only:
                tag = QLabel("仅 Windows")
                tag.setStyleSheet(
                    "color: #b5651d; background:#fff4e6; "
                    "border:1px solid #ffd9a8; border-radius:4px; "
                    "padding:1px 6px; font-size:11px;"
                )
                tag.setFixedHeight(18)
                desc_box = QHBoxLayout()
                desc_box.setSpacing(6)
                desc_box.addWidget(tag)
                desc_box.addWidget(label, 1)
                desc_widget = QWidget()
                desc_widget.setLayout(desc_box)
                row.addWidget(btn)
                row.addWidget(desc_widget, 1)
            else:
                row.addWidget(btn)
                row.addWidget(label, 1)

            layout.addLayout(row)

        layout.addStretch(1)

        # 底部提示
        hint = QLabel(
            "💡 出错时请查看 <b>日志/</b> 文件夹下的 .log 文件；"
            "改了代码想留版本，请用 VS Code 左侧"
            '<span style="color:#4a90e2;">「源代码管理」</span>图标提交。'
        )
        hint.setStyleSheet("color: #888; font-size: 11px; padding-top: 8px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.setCentralWidget(central)

    def run_tool(self, script_name: str, win_only: bool, display_name: str):
        # Windows-only 工具在非 Windows 上给提示
        if win_only and not self.is_windows:
            QMessageBox.information(
                self,
                "仅支持 Windows",
                f"「{display_name}」依赖 Windows 上的 Excel 自动化（pywin32 + Excel 应用程序），"
                f"在 Mac/Linux 上无法运行。\n\n请在 Windows 电脑上使用本工具。",
            )
            return

        script_path = os.path.join(self.core_dir, script_name)
        if not os.path.isfile(script_path):
            QMessageBox.critical(
                self, "找不到脚本",
                f"找不到 {script_path}\n请确认 core/ 文件夹下脚本文件完整。"
            )
            return

        try:
            # 用当前 Python 解释器以 core/ 作为工作目录起子进程
            # 把 stderr 收起来，方便子进程崩溃时弹窗显示报错
            proc = subprocess.Popen(
                [sys.executable, script_path],
                cwd=self.core_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            QMessageBox.critical(self, "启动失败", f"启动「{display_name}」时出错:\n{e}")
            return

        # 用 QTimer 在后台轮询子进程：如果在 1.5s 内立刻崩了（典型是 import 失败 / 立即异常），
        # 就抓住 stderr 弹窗给用户看。
        # 工具正常运行的话进程会持续存活，1.5s 后我们就不再监控（让它自由运行）。
        from PyQt6.QtCore import QTimer

        def check_dead():
            if proc.poll() is None:
                # 还活着，认为正常运行了，不再监控
                return
            # 已经退出
            return_code = proc.returncode
            try:
                err = proc.stderr.read() if proc.stderr else ""
            except Exception:
                err = ""

            if return_code == 0:
                # 正常结束，不打扰
                return

            err_text = (err or "").strip() or "（子进程未输出错误信息）"
            # 友好提示常见错误
            hint = ""
            if "ModuleNotFoundError" in err_text or "No module named" in err_text:
                hint = (
                    "\n\n💡 看起来是缺少 Python 依赖包。\n"
                    "解决办法：双击项目根目录的 “首次安装.bat”（Windows）"
                    "或 “首次安装.command”（Mac）重新安装依赖。"
                )
            elif "_tkinter" in err_text:
                hint = (
                    "\n\n💡 当前 Python 没有 tkinter 模块。\n"
                    "Mac 上可用 Homebrew 安装带 tk 的 Python:\n"
                    "    brew install python-tk"
                )

            # 截断过长 stderr
            shown = err_text if len(err_text) <= 1500 else err_text[:1500] + "\n...(已截断)"

            QMessageBox.critical(
                self,
                f"「{display_name}」启动失败",
                f"工具进程已退出 (退出码 {return_code})。\n\n"
                f"错误信息:\n{shown}{hint}",
            )

        QTimer.singleShot(1500, check_dead)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = Launcher()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
