import math
from collections import defaultdict, Counter
import jieba.posseg as pseg
import re

class EntropyTermExtractor:
    def __init__(self, min_freq=2, min_pmi=1.5, min_entropy=0.8):
        """
        :param min_freq: 最小出现频次
        :param min_pmi: 最小内部凝固度 (值越大，词组结合越紧密，过滤掉的松散组合越多)
        :param min_entropy: 最小边界自由度 (值越大，要求该词作为独立词汇的特征越明显)
        """
        self.min_freq = min_freq
        self.min_pmi = min_pmi
        self.min_entropy = min_entropy
        
        self.word_freq = Counter()        # 记录所有 n-gram 的频次
        self.left_neighbors = defaultdict(Counter)  # 记录左邻字/词
        self.right_neighbors = defaultdict(Counter) # 记录右邻字/词
        self.total_tokens = 0
        
        # 严格停用词表，针对游戏语料扩充
        self.stop_words = {
            '的', '了', '在', '被', '与', '或', '及', '进行', '通过', '能够', '可以', 
            '点击', '滑动', '获取', '消耗', '进入', '成功', '失败', '造成', '产生', 
            '期间', '状态', '一个', '没有', '什么', '这个'
        }
        # 允许作为术语开头和结尾的词性 (名词, 动名词, 专有名词, 英文等)
        self.valid_pos = {'n', 'nz', 'ns', 'nt', 'nw', 'vn', 'eng', 'l', 'i'}

    def _calc_entropy(self, neighbor_counter):
        """计算信息熵"""
        total = sum(neighbor_counter.values())
        if total == 0: return 0.0
        return sum(- (v / total) * math.log2(v / total) for v in neighbor_counter.values())

    def extract(self, raw_items):
        """
        传入字典列表 [{"id": "1", "masked_txt": "文本", "txt": "原文本"}, ...]
        返回提纯后的术语候选字典
        """
        # 1. 扫描语料，收集 N-Gram 统计信息 (这里最大收集 3-gram)
        for item in raw_items:
            segments = re.split(r'[，。！？；、\n\r]', item['masked_txt'])
            for seg in segments:
                if '__SYM_LOCK__' in seg: seg = seg.replace('__SYM_LOCK__', '。')
                if len(seg.strip()) < 2: continue
                
                # 结巴分词获取 Token 序列
                tokens = list(pseg.cut(seg))
                self.total_tokens += len(tokens)
                
                for i in range(len(tokens)):
                    w1 = tokens[i]
                    self.word_freq[(w1.word,)] += 1
                    
                    # Bigram (2-gram)
                    if i < len(tokens) - 1:
                        w2 = tokens[i+1]
                        bi = (w1.word, w2.word)
                        self.word_freq[bi] += 1
                        if i > 0: self.left_neighbors[bi][tokens[i-1].word] += 1
                        if i < len(tokens) - 2: self.right_neighbors[bi][tokens[i+2].word] += 1

                    # Trigram (3-gram)
                    if i < len(tokens) - 2:
                        w2 = tokens[i+1]
                        w3 = tokens[i+2]
                        tri = (w1.word, w2.word, w3.word)
                        self.word_freq[tri] += 1
                        if i > 0: self.left_neighbors[tri][tokens[i-1].word] += 1
                        if i < len(tokens) - 3: self.right_neighbors[tri][tokens[i+3].word] += 1

        # 2. 计算凝固度 (PMI) 和 边界熵 (Entropy)，筛选词汇
        valid_terms = {}
        for ngram_tuple, freq in self.word_freq.items():
            if len(ngram_tuple) < 2: continue # 单字/单词本身已经是独立词了，我们主要挖掘多词组合的新术语
            if freq < self.min_freq: continue
            
            # 基础规则过滤：不含停用词，且开头结尾词性必须是名词类
            word_str = "".join(ngram_tuple)
            if any(sw in ngram_tuple for sw in self.stop_words): continue
            
            # 由于上面只存了字符串，这里简单回测一下词性（也可以在前面存对象）
            temp_pos = list(pseg.cut(word_str))
            if temp_pos[0].flag not in self.valid_pos or temp_pos[-1].flag not in self.valid_pos:
                continue

            # 计算内部凝固度 PMI
            # 对于 2-gram: p(xy) / (p(x)*p(y))
            # 对于 3-gram: min( PMI(x, yz), PMI(xy, z) )
            pmi = 0.0
            p_ngram = freq / self.total_tokens
            if len(ngram_tuple) == 2:
                p_x = self.word_freq[(ngram_tuple[0],)] / self.total_tokens
                p_y = self.word_freq[(ngram_tuple[1],)] / self.total_tokens
                if p_x > 0 and p_y > 0:
                    pmi = math.log2(p_ngram / (p_x * p_y))
            elif len(ngram_tuple) == 3:
                p_x = self.word_freq[(ngram_tuple[0],)] / self.total_tokens
                p_yz = self.word_freq[(ngram_tuple[1], ngram_tuple[2])] / self.total_tokens
                pmi_1 = math.log2(p_ngram / (p_x * p_yz)) if (p_x * p_yz) > 0 else 0
                
                p_xy = self.word_freq[(ngram_tuple[0], ngram_tuple[1])] / self.total_tokens
                p_z = self.word_freq[(ngram_tuple[2],)] / self.total_tokens
                pmi_2 = math.log2(p_ngram / (p_xy * p_z)) if (p_xy * p_z) > 0 else 0
                
                pmi = min(pmi_1, pmi_2) # 木桶效应，取连接最弱的一环

            # 计算左右边界熵
            left_entropy = self._calc_entropy(self.left_neighbors[ngram_tuple])
            right_entropy = self._calc_entropy(self.right_neighbors[ngram_tuple])
            min_entropy = min(left_entropy, right_entropy)

            # 核心判决！
            if pmi >= self.min_pmi and min_entropy >= self.min_entropy:
                # 寻找例文
                best_item = max([r for r in raw_items if word_str in r['txt']], key=lambda x: len(x['txt']), default=None)
                if best_item:
                    valid_terms[word_str] = {
                        "freq": freq, 
                        "best_id": best_item['id'], 
                        "best_ctx": best_item['txt'],
                        "pmi": round(pmi, 2),
                        "entropy": round(min_entropy, 2)
                    }

        # 3. 子串压制算法（如果“超级生命药水”和“生命药水”都存活，保留长的）
        sorted_c = sorted(valid_terms.items(), key=lambda x: len(x[0]), reverse=True)
        final_local_terms, suppressed = {}, set()
        for word, info in sorted_c:
            if word in suppressed: continue
            for ow, oinfo in sorted_c:
                if ow != word and ow in word and oinfo['freq'] <= info['freq'] * 1.5:
                    suppressed.add(ow)
            final_local_terms[word] = info

        return final_local_terms

import sys, subprocess, threading, json, os, traceback, re
from collections import Counter
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed

def install_dependencies():
    required = ["pandas", "openpyxl", "jieba", "openai", "requests"]
    for lib in required:
        try: __import__(lib)
        except ImportError: subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

install_dependencies()
import pandas as pd
from openai import OpenAI
import jieba.posseg as pseg
from threading import Lock

class TermMatrixApp:
    def __init__(self, root):
        self.root = root
        self.root.title("游戏术语提取控制台 - 进阶调优版")
        self.root.geometry("1100x850")
        
        # --- 变量定义 ---
        self.file_path = tk.StringVar()
        self.api_key = tk.StringVar()
        self.base_url = tk.StringVar(value="https://api.openai.com/v1")
        self.model_name = tk.StringVar(value="gemini-3-flash") 
        self.use_ai = tk.BooleanVar(value=False)
        self.map_id = tk.StringVar(value="ID")
        self.map_text = tk.StringVar(value="Text")
        self.map_extra = tk.StringVar(value="Notes")
        self.sym_start = tk.StringVar(value="【")
        self.sym_end = tk.StringVar(value="】")

        self.regex_rules = [] # [{"name": "换行符", "type": "single", "p1": r"<br/>", "p2": "", "active": True}]
        
        self.load_config() 
        self.setup_ui()

    def load_config(self):
        self.config_file = "term_config.json"
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    conf = json.load(f)
                    self.file_path.set(conf.get("file_path", ""))
                    self.api_key.set(conf.get("api_key", ""))
                    self.base_url.set(conf.get("base_url", "https://api.openai.com/v1"))
                    self.model_name.set(conf.get("model_name", "gemini-3-flash"))
                    self.sym_start.set(conf.get("sym_start", "【"))
                    self.sym_end.set(conf.get("sym_end", "】"))
                    self.regex_rules = conf.get("regex_rules", [])
                    self.out_dir = conf.get("out_dir", os.getcwd())
            except: self.out_dir = os.getcwd()
        else:
            self.out_dir = os.getcwd()

    def save_config(self):
        conf = {
            "file_path": self.file_path.get(), "api_key": self.api_key.get(),
            "base_url": self.base_url.get(), "model_name": self.model_name.get(),
            "sym_start": self.sym_start.get(), "sym_end": self.sym_end.get(),
            "regex_rules": self.regex_rules, "out_dir": self.out_dir
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(conf, f, ensure_ascii=False, indent=4)

    def setup_ui(self):
        # 1. 基础配置
        f_top = ttk.LabelFrame(self.root, text="I/O 与字段映射", padding=5)
        f_top.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(f_top, textvariable=self.file_path, width=60).grid(row=0, column=0, columnspan=4, padx=5, pady=2)
        ttk.Button(f_top, text="选择语料", command=lambda: self.file_path.set(filedialog.askopenfilename())).grid(row=0, column=4)
        ttk.Button(f_top, text="设置输出路径", command=lambda: setattr(self, 'out_dir', filedialog.askdirectory())).grid(row=0, column=5)

        ttk.Label(f_top, text="ID列:").grid(row=1, column=0)
        ttk.Entry(f_top, textvariable=self.map_id, width=10).grid(row=1, column=1)
        ttk.Label(f_top, text="文本列:").grid(row=1, column=2)
        ttk.Entry(f_top, textvariable=self.map_text, width=10).grid(row=1, column=3)
        ttk.Label(f_top, text="备注列:").grid(row=1, column=4)
        ttk.Entry(f_top, textvariable=self.map_extra, width=15).grid(row=1, column=5)
        
        ttk.Label(f_top, text="锁定符(起):").grid(row=1, column=6)
        ttk.Entry(f_top, textvariable=self.sym_start, width=4).grid(row=1, column=7)
        ttk.Label(f_top, text="(止):").grid(row=1, column=8)
        ttk.Entry(f_top, textvariable=self.sym_end, width=4).grid(row=1, column=9)

        # 2. 正则表达式规则管理器 (重点重构)
        f_regex = ttk.LabelFrame(self.root, text="语料清洗引擎 (RegEx 预处理)", padding=5)
        f_regex.pack(fill="x", padx=10, pady=5)
        
        self.tree_reg = ttk.Treeview(f_regex, columns=("name", "type", "rule", "active"), show="headings", height=4)
        self.tree_reg.heading("name", text="规则名称"); self.tree_reg.column("name", width=120)
        self.tree_reg.heading("type", text="模式"); self.tree_reg.column("type", width=80)
        self.tree_reg.heading("rule", text="正则模式 (Pattern)"); self.tree_reg.column("rule", width=400)
        self.tree_reg.heading("active", text="状态"); self.tree_reg.column("active", width=60)
        self.tree_reg.pack(side="left", fill="both", expand=True)
        self.refresh_regex_list()

        btn_f = ttk.Frame(f_regex)
        btn_f.pack(side="right", padx=5)
        ttk.Button(btn_f, text="添加单一规则", command=lambda: self.edit_regex("single")).pack(fill="x", pady=2)
        ttk.Button(btn_f, text="添加成对规则", command=lambda: self.edit_regex("paired")).pack(fill="x", pady=2)
        ttk.Button(btn_f, text="删除选中", command=self.del_regex).pack(fill="x", pady=2)

        # 3. AI 配置
        f_ai = ttk.LabelFrame(self.root, text="AI 打标配置", padding=5)
        f_ai.pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(f_ai, text="启用 AI 后期校验", variable=self.use_ai).pack(side="left", padx=5)
        ttk.Label(f_ai, text="Key:").pack(side="left")
        ttk.Entry(f_ai, textvariable=self.api_key, show="*", width=20).pack(side="left", padx=5)
        ttk.Label(f_ai, text="URL:").pack(side="left")
        ttk.Entry(f_ai, textvariable=self.base_url, width=25).pack(side="left", padx=5)

        # 4. 日志面板 (替代庞大的 Treeview)
        f_log = ttk.LabelFrame(self.root, text="执行日志与进度监控", padding=5)
        f_log.pack(fill="both", expand=True, padx=10, pady=5)
        self.prog_bar = ttk.Progressbar(f_log, mode='determinate')
        self.prog_bar.pack(fill="x", pady=2)
        
        self.txt_log = tk.Text(f_log, state="disabled", bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 10))
        sc = ttk.Scrollbar(f_log, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sc.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

        self.btn_run = ttk.Button(self.root, text="🚀 启动提取流水线", command=self.start_workflow)
        self.btn_run.pack(pady=10)

    # --- 正则规则管理 ---
    def refresh_regex_list(self):
        self.tree_reg.delete(*self.tree_reg.get_children())
        for r in self.regex_rules:
            status = "✅ 启用" if r['active'] else "❌ 停用"
            desc = r['p1'] if r['type'] == 'single' else f"起:{r['p1']} | 止:{r['p2']}"
            self.tree_reg.insert("", "end", values=(r['name'], r['type'], desc, status))

    def edit_regex(self, r_type):
        win = tk.Toplevel(self.root)
        win.title("编辑清洗规则")
        
        tk.Label(win, text="规则名称:").grid(row=0, column=0, pady=5)
        e_name = ttk.Entry(win); e_name.grid(row=0, column=1)
        
        if r_type == "single":
            tk.Label(win, text="剔除正则(如 <br/>):").grid(row=1, column=0, pady=5)
            e_p1 = ttk.Entry(win, width=30); e_p1.grid(row=1, column=1)
            e_p2 = None
        else:
            tk.Label(win, text="起始正则(如 <color.*?>):").grid(row=1, column=0, pady=5)
            e_p1 = ttk.Entry(win, width=30); e_p1.grid(row=1, column=1)
            tk.Label(win, text="结束正则(如 </color>):").grid(row=2, column=0, pady=5)
            e_p2 = ttk.Entry(win, width=30); e_p2.grid(row=2, column=1)

        def save():
            rule = {"name": e_name.get() or "未命名", "type": r_type, "active": True,
                    "p1": e_p1.get(), "p2": e_p2.get() if e_p2 else ""}
            self.regex_rules.append(rule)
            self.save_config()
            self.refresh_regex_list()
            win.destroy()
            
        ttk.Button(win, text="保存规则", command=save).grid(row=3, columnspan=2, pady=10)

    def del_regex(self):
        sel = self.tree_reg.selection()
        if not sel: return
        idx = self.tree_reg.index(sel[0])
        del self.regex_rules[idx]
        self.save_config()
        self.refresh_regex_list()

    # --- 日志与多线程同步 ---
    def log(self, text, val=None):
        self.root.after(0, self._sync_log, text, val)
        
    def _sync_log(self, text, val):
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", f"> {text}\n")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")
        if val is not None: self.prog_bar['value'] = val

    def start_workflow(self):
        if not self.file_path.get(): return
        self.btn_run.config(state="disabled")
        self.txt_log.config(state="normal"); self.txt_log.delete(1.0, "end"); self.txt_log.config(state="disabled")
        threading.Thread(target=self.core_engine, daemon=True).start()

    # --- 核心提取引擎 ---
    def core_engine(self):
        try:
            self.save_config()
            self.log("=== 启动游戏术语提取流水线 ===", 5)
            
            # 1. 数据加载
            p = self.file_path.get()
            df = pd.read_excel(p) if p.endswith(('.xlsx', '.xls')) else pd.read_csv(p)
            id_col, text_col = self.map_id.get(), self.map_text.get()
            raw_items = []
            for _, row in df.iterrows():
                txt = str(row[text_col]) if not pd.isna(row[text_col]) else ""
                if txt.strip(): raw_items.append({"id": str(row[id_col]), "txt": txt.strip(), "raw": txt.strip()})
            
            self.log(f"[阶段1] 数据加载完成，共 {len(raw_items)} 条有效文本。", 10)

            # 2. 正则清洗
            active_rules = [r for r in self.regex_rules if r['active']]
            if active_rules:
                self.log(f"[阶段2] 正在执行 {len(active_rules)} 条正则清洗规则...")
                for item in raw_items:
                    for r in active_rules:
                        try:
                            if r['type'] == 'single':
                                item['txt'] = re.sub(r['p1'], '', item['txt'])
                            elif r['type'] == 'paired':
                                # 将成对的起止代码剔除，只保留中间文本
                                pattern = f"{r['p1']}(.*?){r['p2']}"
                                item['txt'] = re.sub(pattern, r'\1', item['txt'])
                        except: pass
            
            # 中间件保存1
            pd.DataFrame(raw_items).to_excel(os.path.join(self.out_dir, "1_正则清洗后语料.xlsx"), index=False)
            self.log("已生成中间件: 1_正则清洗后语料.xlsx", 20)

            # ---------------- 替换后的阶段 3：符号锁定进阶解构与清洗 ----------------
            self.log("[阶段3] 执行符号文本深度解构：拆分组合词、剔除UI模板...")
            raw_sym_texts = [] 
            s_start, s_end = self.sym_start.get().strip(), self.sym_end.get().strip()
            
            if s_start and s_end:
                pattern = f"{re.escape(s_start)}(.*?){re.escape(s_end)}"
                for item in raw_items:
                    matches = re.findall(pattern, item['txt'])
                    for m in matches:
                        if m.strip():
                            # 记录原文以及它所在的句子上下文
                            raw_sym_texts.append({"id": item['id'], "txt": m.strip(), "ctx": item['txt']})
                    # 【关键策略改变】：不再用 __SYM_LOCK__ 掩盖文本，而是替换为句号切断边界。
                    # 这样被释放出来的纯净术语，依然可以参与全局的 NLP 频次与熵的计算！
                    item['masked_txt'] = re.sub(pattern, '。', item['txt'])
            else:
                for item in raw_items: item['masked_txt'] = item['txt']

            # 核心函数：正则暴力破解 UI 模板与废话
            def clean_sym_text(text):
                # 1. 清理代码残留、通配符变量 (如 '+this._data.lev+', %%, %s)
                text = re.sub(r'[\'\+a-zA-Z_\.]{3,}', '', text)
                text = re.sub(r'%+', '', text)
                
                # 2. 清理典型的 UI 状态前缀/后缀与非名词废话
                text = re.sub(r'\d+[级阶星]\s*(激活|解锁|开启)?', '', text) # 斩杀 100级激活
                text = re.sub(r'(激活|解锁|开启)\d+[级阶星]?', '', text) # 斩杀 激活3星, 1阶激活
                text = re.sub(r'升至.*?解锁', '', text)
                text = re.sub(r'至\d+[级阶星](激活|解锁)?', '', text)
                text = re.sub(r'(点击|查看|一键|自动|保卫).*', '', text) # 斩杀 点击播放, 一键派遣
                text = re.sub(r'\d+倍速', '', text)
                text = re.sub(r'\d+品质', '', text)
                text = re.sub(r'玩家.*名字', '', text)
                text = re.sub(r'下一星级.*', '', text)
                text = re.sub(r'军团名称', '', text)
                
                return text.strip()

            cleaned_sym_pool = {}
            for sym_item in raw_sym_texts:
                # 1. 拆分复合词汇 (按 : ： - — 分割)
                sub_chunks = re.split(r'[:：\-\—]', sym_item['txt'])
                
                for chunk in sub_chunks:
                    # 2. 扔进清洗机
                    cleaned_word = clean_sym_text(chunk)
                    # 清理后去除头尾残留的标点符号
                    cleaned_word = re.sub(r'^[^\w\u4e00-\u9fa5]+|[^\w\u4e00-\u9fa5]+$', '', cleaned_word)
                    
                    # 纯数字、纯字母或太短的，视为废弃物丢弃
                    if len(cleaned_word) < 2 or re.match(r'^[\d\s\.\+\-\*\/%><=a-zA-Z]+$', cleaned_word):
                        continue
                        
                    if cleaned_word not in cleaned_sym_pool:
                        cleaned_sym_pool[cleaned_word] = {"freq": 1, "best_id": sym_item['id'], "best_ctx": sym_item['ctx']}
                    else:
                        cleaned_sym_pool[cleaned_word]["freq"] += 1

            # 【审判时刻】将清洗后的符号词分流
            pre_extracted_terms = {}
            pending_long_syms = {} # 暂存过长的符号词，发配给 NLP 重审
            
            for term, info in cleaned_sym_pool.items():
                if len(term) <= 5: # 提纯后长度在5及以内的，大概率是干练的术语，直接发金牌
                    pre_extracted_terms[term] = info
                else:
                    pending_long_syms[term] = info

            self.log(f"符号清理完成！锁定 {len(pre_extracted_terms)} 个纯净短术语，发配 {len(pending_long_syms)} 个可疑长文本进行NLP重审。", 35)

            # ---------------- 替换后的阶段 4：黑洞吸收与双规决斗 ----------------
            self.log("[阶段4] 启动 NLP 新词发现与强力层级去重...")
            nlp_extractor = EntropyTermExtractor(min_freq=2, min_pmi=1.5, min_entropy=0.8)
            local_terms = nlp_extractor.extract(raw_items)
            
            # --- NLP 捞回机制 ---
            # 刚才发配的超长符号文本，如果 NLP 引擎也独立证明了它们凝固度很高（即在 local_terms 里），则平反捞回。
            for l_term, info in pending_long_syms.items():
                if l_term in local_terms:
                    pre_extracted_terms[l_term] = info # 平反，重新加入高优锁定池
            
            # --- 核心重叠去重算法 ---
            # 1. 符号黑洞吸收：NLP提取的词如果包含了绝对锁定的词，说明是粘连的废话，直接剔除
            surviving_local = {}
            for n_term, n_info in local_terms.items():
                is_absorbed = False
                for s_term in pre_extracted_terms:
                    if s_term in n_term and s_term != n_term:
                        is_absorbed = True
                        break
                if not is_absorbed:
                    surviving_local[n_term] = n_info

            # 2. NLP内部决斗 (子串与父串的较量)
            sorted_nlp = sorted(surviving_local.items(), key=lambda x: len(x[0]), reverse=True)
            suppressed = set()
            
            for i, (longer_w, l_info) in enumerate(sorted_nlp):
                if longer_w in suppressed: continue
                for j in range(i+1, len(sorted_nlp)):
                    shorter_w, s_info = sorted_nlp[j]
                    if shorter_w in suppressed: continue
                    
                    if shorter_w in longer_w:
                        # 短词频次是长词的 1.5 倍以上 -> 杀长词；反之 -> 杀短词
                        if s_info['freq'] >= l_info['freq'] * 1.5:
                            suppressed.add(longer_w)
                            break 
                        else:
                            suppressed.add(shorter_w)

            # 组装最终列表
            final_local_terms = {k: v for k, v in surviving_local.items() if k not in suppressed}
            
            merged_candidates = pre_extracted_terms.copy()
            for w, info in final_local_terms.items():
                if w not in merged_candidates:
                    merged_candidates[w] = info

            # 中间件保存2
            df_local = pd.DataFrame([
                {"术语": w, "频次": i["freq"], 
                 "PMI凝固度": local_terms.get(w, {}).get("pmi", "-"), 
                 "边界熵": local_terms.get(w, {}).get("entropy", "-"), 
                 "来源": "🎯精炼锁定" if w in pre_extracted_terms else "⚙️算法提纯"} 
                for w, i in merged_candidates.items()
            ])
            df_local.to_excel(os.path.join(self.out_dir, "2_初筛术语集.xlsx"), index=False)
            self.log(f"去重完成！压缩至 {len(merged_candidates)} 个。已生成: 2_初筛术语集.xlsx", 50)

            # 5. AI 打标 (只发给 AI 那些非符号锁定的词)
            final_glossary = pre_extracted_terms.copy()
            words_to_ai = {w: info for w, info in local_terms.items() if w not in pre_extracted_terms}
            
            if self.use_ai.get() and self.api_key.get() and words_to_ai:
                self.log(f"[阶段5] 启动 AI 批处理甄别，共 {len(words_to_ai)} 个待判定词...", 60)
                client = OpenAI(api_key=self.api_key.get(), base_url=self.base_url.get())
                
                items_list = list(words_to_ai.items())
                batch_size = 20 # 加大批次
                batches = [items_list[i:i + batch_size] for i in range(0, len(items_list), batch_size)]
                
                completed = 0
                for batch in batches:
                    batch_payload = {w: str(info['best_ctx'])[:40] for w, info in batch}
                    try:
                        prompt = f"分析以下JSON字典中的【候选词】是否为游戏核心术语。\n{json.dumps(batch_payload, ensure_ascii=False)}\n返回JSON，如果是返回{{\"is_term\": true}}，如果包含废话不完整返回{{\"is_term\": false}}。"
                        resp = client.chat.completions.create(
                            model=self.model_name.get(),
                            messages=[{"role": "user", "content": prompt}], temperature=0, timeout=30
                        )
                        res_json = json.loads(re.sub(r'^```json\s*|\s*```$', '', resp.choices[0].message.content.strip(), flags=re.MULTILINE))
                        
                        for w, info in batch:
                            if res_json.get(w, {}).get("is_term") is True:
                                final_glossary[w] = info
                                final_glossary[w]['status'] = "AI确认"
                    except:
                        # 失败则默认保留
                        for w, info in batch: 
                            final_glossary[w] = info
                            final_glossary[w]['status'] = "AI判定失败/超时"

                    completed += 1
                    self.log(f"AI 批处理进度: {completed}/{len(batches)} 批次完成。", 60 + int(completed/len(batches)*30))
            else:
                self.log("跳过 AI 校验，全量合并数据。", 90)
                for w, info in local_terms.items(): 
                    if w not in final_glossary:
                        final_glossary[w] = info
                        final_glossary[w]['status'] = "本地提纯"

            # 为符号锁定的词补齐状态
            for w in pre_extracted_terms:
                final_glossary[w]['status'] = "🎯符号锁定"

            # 6. 最终导出
            self.log("[阶段6] 生成最终矩阵...", 95)
            output_list = [{"术语": w, "频次": i['freq'], "代表ID": i['best_id'], "代表例文": i['best_ctx'], "来源类型": i['status']} for w, i in sorted(final_glossary.items(), key=lambda x: x[1]['freq'], reverse=True)]
            
            save_path = os.path.join(self.out_dir, "3_最终精炼术语矩阵_Pro.xlsx")
            pd.DataFrame(output_list).to_excel(save_path, index=False)
            self.log(f"✅ 流水线执行完毕！共输出 {len(output_list)} 条精炼术语。\n最终文件: {save_path}", 100)

        except Exception as e:
            self.log(f"❌ 运行中断: {str(e)}\n{traceback.format_exc()}")
        finally:
            self.root.after(0, lambda: self.btn_run.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = TermMatrixApp(root)
    root.mainloop()