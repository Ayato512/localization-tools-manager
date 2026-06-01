import sys
import os
import pandas as pd
from lxml import etree
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, 
                             QMessageBox, QComboBox, QGroupBox)
from PyQt6.QtCore import Qt

class TMXConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('语料库 Excel 转 TMX 工具')
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout()

        # --- 文件选择区 ---
        file_group = QGroupBox("文件设置")
        file_layout = QVBoxLayout()
        
        self.btn_select = QPushButton('选择 Excel 文件')
        self.btn_select.clicked.connect(self.open_file)
        self.lbl_file_path = QLabel('未选择文件')
        self.lbl_file_path.setWordWrap(True)
        self.lbl_file_path.setStyleSheet("color: gray;")
        
        file_layout.addWidget(self.btn_select)
        file_layout.addWidget(self.lbl_file_path)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # --- 语言与表头配置区 ---
        config_group = QGroupBox("转换配置")
        config_grid = QVBoxLayout()

        # 源语言配置
        src_layout = QHBoxLayout()
        src_layout.addWidget(QLabel("源语言列名:"))
        self.input_src_col = QLineEdit()
        self.input_src_col.setPlaceholderText("例如: Japanese")
        self.input_src_col.setText("Source") # 默认值
        src_layout.addWidget(self.input_src_col)
        
        src_layout.addWidget(QLabel("代码:"))
        self.combo_src_lang = QComboBox()
        self.combo_src_lang.addItems(["ja-JP", "zh-CN", "en-US", "ko-KR"])
        src_layout.addWidget(self.combo_src_lang)
        config_grid.addLayout(src_layout)

        # 目标语言配置
        tgt_layout = QHBoxLayout()
        tgt_layout.addWidget(QLabel("目标列名:"))
        self.input_tgt_col = QLineEdit()
        self.input_tgt_col.setPlaceholderText("例如: Chinese")
        self.input_tgt_col.setText("Target") # 默认值
        tgt_layout.addWidget(self.input_tgt_col)
        
        tgt_layout.addWidget(QLabel("代码:"))
        self.combo_tgt_lang = QComboBox()
        self.combo_tgt_lang.addItems(["zh-CN", "ja-JP", "en-US", "ko-KR"])
        tgt_layout.addWidget(self.combo_tgt_lang)
        config_grid.addLayout(tgt_layout)

        config_group.setLayout(config_grid)
        layout.addWidget(config_group)

        # --- 执行区 ---
        self.btn_convert = QPushButton('开始转换并导出 TMX')
        self.btn_convert.setFixedHeight(40)
        self.btn_convert.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.btn_convert.clicked.connect(self.start_conversion)
        layout.addWidget(self.btn_convert)

        self.setLayout(layout)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 Excel 文件", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            self.lbl_file_path.setText(file_path)
            # 尝试自动读取表头填充到输入框（可选优化）
            try:
                df = pd.read_excel(file_path, nrows=0)
                cols = df.columns.tolist()
                if len(cols) >= 2:
                    self.input_src_col.setText(cols[0])
                    self.input_tgt_col.setText(cols[1])
            except:
                pass

    def start_conversion(self):
        input_path = self.lbl_file_path.text()
        if not os.path.exists(input_path):
            QMessageBox.warning(self, "错误", "请先选择有效的 Excel 文件")
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "保存 TMX 文件", "output.tmx", "TMX Files (*.tmx)")
        if not save_path:
            return

        try:
            self.convert_logic(
                input_path, 
                save_path, 
                self.combo_src_lang.currentText(),
                self.combo_tgt_lang.currentText(),
                self.input_src_col.text(),
                self.input_tgt_col.text()
            )
            QMessageBox.information(self, "成功", f"转换完成！\n保存至: {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "转换失败", f"发生错误: {str(e)}")

    def convert_logic(self, input_file, output_file, src_lang, tgt_lang, src_col, tgt_col):
        df = pd.read_excel(input_file)
        
        tmx = etree.Element('tmx', version='1.4')
        header = etree.SubElement(tmx, 'header', {
            'creationtool': 'PyQt6_TMX_Tool',
            'segtype': 'sentence',
            'o-tmf': 'Excel',
            'adminlang': 'en-US',
            'srclang': src_lang,
            'datatype': 'plaintext',
            'creationdate': datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        })
        body = etree.SubElement(tmx, 'body')
        
        for _, row in df.iterrows():
            source_text = str(row[src_col]) if pd.notnull(row[src_col]) else ""
            target_text = str(row[tgt_col]) if pd.notnull(row[tgt_col]) else ""
            if not source_text.strip(): continue
                
            tu = etree.SubElement(body, 'tu')
            # 源语
            tuv_s = etree.SubElement(tu, 'tuv', {etree.QName("http://www.w3.org/XML/1998/namespace", "lang"): src_lang})
            etree.SubElement(tuv_s, 'seg').text = source_text
            # 目标语
            tuv_t = etree.SubElement(tu, 'tuv', {etree.QName("http://www.w3.org/XML/1998/namespace", "lang"): tgt_lang})
            etree.SubElement(tuv_t, 'seg').text = target_text

        tree = etree.ElementTree(tmx)
        tree.write(output_file, encoding='utf-8', xml_declaration=True, pretty_print=True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TMXConverterApp()
    ex.show()
    sys.exit(app.exec())
