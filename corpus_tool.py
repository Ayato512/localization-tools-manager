import sys
import os
import pandas as pd
import re
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from rapidfuzz import fuzz

# --- 1. 核心处理与同步拆分引擎 ---
class CorpusProcessor:
    @staticmethod
    def sync_split(src_text, tgt_text, align_comma=True):
        """同步拆分：支持中日文标点映射对齐"""
        # 定义分隔符：终结符必须对齐，停顿符根据开关对齐
        if align_comma:
            # 日文顿号 、 对应 中文逗号 ，
            s_delims = r'([、。！？\n])'
            t_delims = r'([，。！？\n])'
        else:
            s_delims = r'([。！？\n])'
            t_delims = r'([。！？\n])'
            
        s_parts = re.split(s_delims, str(src_text))
        t_parts = re.split(t_delims, str(tgt_text))
        
        def rebuild(parts):
            segs = ["".join(i) for i in zip(parts[0::2], parts[1::2])]
            if len(parts) % 2 != 0: segs.append(parts[-1])
            return [s.strip() for s in segs if s.strip()]

        s_segs = rebuild(s_parts)
        t_segs = rebuild(t_parts)

        # 语义对齐校验：只有段落数相等才拆分，否则保留长句
        if len(s_segs) == len(t_segs) and len(s_segs) > 1:
            return list(zip(s_segs, t_segs))
        return [(src_text, tgt_text)]

    @staticmethod
    def get_fingerprint(text, custom_regex):
        """生成影子文本：用于去重判定"""
        if not isinstance(text, str): return ""
        # 1. 屏蔽用户定义的代码模式 (如 #颜色#)
        text = re.sub(custom_regex, '[CODE]', text)
        # 2. 屏蔽数字
        text = re.sub(r'\d+', '[#]', text)
        # 3. 基础预处理
        text = text.replace(' ', '').replace('　', '').strip()
        return text

# --- 2. 预览对话框 ---
class PreviewDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提炼效果预览 (前10条)")
        self.resize(1000, 600)
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget(len(data), 4)
        self.table.setHorizontalHeaderLabels(["原文分段", "译文分段", "去重指纹 (影子文本)", "备注"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        for i, row in enumerate(data):
            self.table.setItem(i, 0, QTableWidgetItem(str(row['src'])))
            self.table.setItem(i, 1, QTableWidgetItem(str(row['tgt'])))
            self.table.setItem(i, 2, QTableWidgetItem(str(row['fingerprint'])))
            self.table.setItem(i, 3, QTableWidgetItem(str(row['memo'])))
        
        layout.addWidget(self.table)
        btn = QPushButton("确定并开始正式处理")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

# --- 3. 主界面与线程控制 ---
class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("中日文语料提炼专家版")
        self.setMinimumWidth(800)
        self.file_path = ""
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 1. 文件选择
        f_box = QHBoxLayout()
        self.lbl_path = QLineEdit(); self.lbl_path.setPlaceholderText("请选择Excel文件...")
        btn_file = QPushButton("浏览"); btn_file.clicked.connect(self.select_file)
        f_box.addWidget(self.lbl_path); f_box.addWidget(btn_file)
        main_layout.addLayout(f_box)

        # 2. 配置面板
        cfg_layout = QHBoxLayout()
        
        # 列名设置
        col_group = QGroupBox("列名映射")
        col_form = QFormLayout(col_group)
        self.src_name = QLineEdit("日文"); self.tgt_name = QLineEdit("中文"); self.memo_name = QLineEdit("备注")
        col_form.addRow("原文列:", self.src_name)
        col_form.addRow("译文列:", self.tgt_name)
        col_form.addRow("备注列:", self.memo_name)
        cfg_layout.addWidget(col_group)

        # 规则设置
        rule_group = QGroupBox("处理规则")
        rule_form = QVBoxLayout(rule_group)
        self.regex_input = QLineEdit("#.*?#")
        rule_form.addWidget(QLabel("代码屏蔽正则 (如 #.*?#):"))
        rule_form.addWidget(self.regex_input)
        self.cb_align = QCheckBox("同步对齐 (日文、 <-> 中文，)"); self.cb_align.setChecked(True)
        self.cb_split = QCheckBox("启用最小句段拆分"); self.cb_split.setChecked(True)
        self.cb_regex_dedup = QCheckBox("启用变量查重 (L2)"); self.cb_regex_dedup.setChecked(True)
        rule_form.addWidget(self.cb_align); rule_form.addWidget(self.cb_split); rule_form.addWidget(self.cb_regex_dedup)
        cfg_layout.addWidget(rule_group)
        
        main_layout.addLayout(cfg_layout)

        # 3. 日志与操作
        self.log_area = QPlainTextEdit(); self.log_area.setReadOnly(True)
        main_layout.addWidget(QLabel("运行日志:"))
        main_layout.addWidget(self.log_area)

        btn_box = QHBoxLayout()
        self.btn_preview = QPushButton("预览效果"); self.btn_preview.clicked.connect(self.run_preview)
        self.btn_run = QPushButton("正式执行提炼"); self.btn_run.clicked.connect(self.run_full)
        self.btn_run.setStyleSheet("background-color: #27ae60; color: white; height: 35px;")
        btn_box.addWidget(self.btn_preview); btn_box.addWidget(self.btn_run)
        main_layout.addLayout(btn_box)

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择Excel", "", "Excel Files (*.xlsx *.xls)")
        if path: 
            self.file_path = path
            self.lbl_path.setText(path)

    def get_config(self):
        return {
            'src': self.src_name.text(), 'tgt': self.tgt_name.text(), 'memo': self.memo_name.text(),
            'regex': self.regex_input.text(), 'align': self.cb_align.isChecked(),
            'split': self.cb_split.isChecked(), 'do_regex': self.cb_regex_dedup.isChecked()
        }

    def process_logic(self, limit=None):
        """核心处理逻辑，支持全量或限量预览"""
        df = pd.read_excel(self.file_path)
        if limit: df = df.head(limit)
        
        cfg = self.get_config()
        results = []
        
        for _, row in df.iterrows():
            s_raw, t_raw = str(row[cfg['src']]), str(row[cfg['tgt']])
            memo = row.get(cfg['memo'], "")
            
            # 执行拆分
            if cfg['split']:
                pairs = CorpusProcessor.sync_split(s_raw, t_raw, cfg['align'])
            else:
                pairs = [(s_raw, t_raw)]
                
            for s, t in pairs:
                results.append({
                    'src': s, 'tgt': t, 
                    'fingerprint': CorpusProcessor.get_fingerprint(s, cfg['regex']),
                    'memo': memo
                })
        return pd.DataFrame(results)

    def run_preview(self):
        if not self.file_path: return
        preview_df = self.process_logic(limit=10)
        dlg = PreviewDialog(preview_df.to_dict('records'), self)
        dlg.exec()

    def run_full(self):
        if not self.file_path: return
        self.log_area.appendPlainText(">>> 开始全量处理...")
        
        # 1. 预处理与拆分
        df_processed = self.process_logic()
        orig_len = len(df_processed)
        
        # 2. 择优排序
        # 简单长度+中日文占比评分
        df_processed['score'] = df_processed['src'].apply(lambda x: len(str(x)) + (len(re.findall(r'[\u4e00-\u9fa5\u3040-\u30ff]', str(x))) * 2))
        df_processed = df_processed.sort_values(by='score', ascending=False)
        
        # 3. 级联去重
        if self.cb_regex_dedup.isChecked():
            # 按指纹去重（影子文本）
            df_processed = df_processed.drop_duplicates(subset=['fingerprint'], keep='first')
        else:
            # 仅完全去重
            df_processed = df_processed.drop_duplicates(subset=['src', 'tgt'], keep='first')
            
        self.log_area.appendPlainText(f"提炼完成！原始句对: {orig_len} -> 去重后: {len(df_processed)}")
        
        save_path, _ = QFileDialog.getSaveFileName(self, "保存语料", "clean_corpus.xlsx", "Excel (*.xlsx)")
        if save_path:
            # 导出时删除辅助列
            df_processed[['src', 'tgt', 'memo']].to_excel(save_path, index=False)
            self.log_area.appendPlainText(f"成功导出至: {save_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())