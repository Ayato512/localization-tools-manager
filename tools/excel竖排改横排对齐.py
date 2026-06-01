import sys
import os
import pandas as pd
import re
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QLabel, 
                             QFileDialog, QMessageBox, QFrame, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# ===================== 核心逻辑：数据处理线程 =====================
class ProcessingThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, input_path, output_path):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path

    def run(self):
        try:
            # 1. 读取数据
            df = pd.read_excel(self.input_path, header=None)
            col_a, col_b = df.columns[0], df.columns[1]

            # 2. 提取尾号逻辑（下划线后内容）
            def extract_suffix(text):
                text = str(text).strip()
                return text.split('_')[-1] if '_' in text else text

            df['group_id'] = df[col_a].apply(extract_suffix)

            # 3. 归类合并
            final_rows = []
            for _, group in df.groupby('group_id', sort=False):
                combined_row = []
                for _, row in group.iterrows():
                    combined_row.extend([row[col_a], row[col_b]])
                final_rows.append(combined_row)

            # 4. 构建结果表并命名列
            result_df = pd.DataFrame(final_rows)
            max_cols = len(result_df.columns)
            new_headers = []
            for i in range((max_cols + 1) // 2):
                new_headers.extend([f"ID_{i+1}", f"内容_{i+1}"])
            result_df.columns = new_headers[:max_cols]

            # 5. 导出
            result_df.to_excel(self.output_path, index=False)
            self.finished_signal.emit(f"处理成功！\n输出文件：{self.output_path}")

        except Exception as e:
            self.error_signal.emit(str(e))

# ===================== UI 界面：PyQt6 =====================
class MergeToolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Excel 尾号行转列合并工具 V1.0")
        self.resize(600, 250)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)

        # --- 输入文件 ---
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("请选择或拖入源 Excel 文件...")
        btn_input = QPushButton("📁 选择输入文件")
        btn_input.clicked.connect(self.select_input)
        input_layout.addWidget(QLabel("源文件:"))
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(btn_input)
        layout.addLayout(input_layout)

        # --- 输出文件 ---
        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("请选择保存路径...")
        btn_output = QPushButton("💾 选择保存位置")
        btn_output.clicked.connect(self.select_output)
        output_layout.addWidget(QLabel("保存到:"))
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(btn_output)
        layout.addLayout(output_layout)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # --- 说明文字 ---
        tip_label = QLabel("提示：程序将自动根据 ID 最后一个下划线 '_' 后的内容进行分组合并。")
        tip_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(tip_label)

        # --- 进度条 ---
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(10)
        layout.addWidget(self.pbar)

        # --- 运行按钮 ---
        self.btn_run = QPushButton("🚀 开始转换数据")
        self.btn_run.setFixedHeight(45)
        self.btn_run.setStyleSheet("""
            QPushButton { background-color: #0078d4; color: white; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.btn_run.clicked.connect(self.start_process)
        layout.addWidget(self.btn_run)

    def select_input(self):
        file, _ = QFileDialog.getOpenFileName(self, "选择源 Excel", "", "Excel Files (*.xlsx *.xls)")
        if file:
            self.input_edit.setText(file)
            # 自动生成一个默认输出路径
            base, ext = os.path.splitext(file)
            self.output_edit.setText(f"{base}_合并结果{ext}")

    def select_output(self):
        file, _ = QFileDialog.getSaveFileName(self, "选择保存位置", self.output_edit.text(), "Excel Files (*.xlsx)")
        if file:
            self.output_edit.setText(file)

    def start_process(self):
        in_p = self.input_edit.text()
        out_p = self.output_edit.text()

        if not os.path.exists(in_p):
            QMessageBox.warning(self, "错误", "输入文件路径无效！")
            return
        
        self.btn_run.setEnabled(False)
        self.pbar.setRange(0, 0) # 开启繁忙动画

        self.thread = ProcessingThread(in_p, out_p)
        self.thread.finished_signal.connect(self.on_success)
        self.thread.error_signal.connect(self.on_fail)
        self.thread.start()

    def on_success(self, msg):
        self.pbar.setRange(0, 100)
        self.pbar.setValue(100)
        self.btn_run.setEnabled(True)
        QMessageBox.information(self, "完成", msg)

    def on_fail(self, err):
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "失败", f"处理过程中出现错误：\n{err}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 设置全局字体（可选）
    app.setStyle("Fusion") 
    window = MergeToolApp()
    window.show()
    sys.exit(app.exec())
