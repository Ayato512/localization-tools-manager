import os, threading, time, io, base64, tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import pandas as pd
from datetime import datetime
from PIL import Image
from openai import OpenAI 

class AssetProV74:
    def __init__(self, root):
        self.root = root
        self.root.title("美术资产对照专家 v7.4 (Precision OCR Edition test)")
        self.root.geometry("1000x920")
        self.root.configure(bg="#ffffff")
        
        self.target_model = "gemini-3-flash"
        # 基于用户实测数据校准单价 ($0.11/133.4K -> ~$0.825/1M)
        self.price_per_m = 0.825 
        
        self.total_count = 0
        self.total_raw_size = 0
        self.sample_token_per_img = 0 
        self.actual_tokens_total = 0
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.active_border = "#0078d7"
        self.border_color = "#d1d1d1"
        
        self.setup_ui()

    def create_outline_btn(self, parent, text, command, width=None):
        btn = tk.Button(parent, text=text, command=command, bg="#ffffff", fg="#333333",
                        relief="flat", highlightthickness=1, highlightbackground=self.border_color,
                        activebackground="#f5f5f5", font=("Segoe UI", 9), width=width)
        btn.bind("<Enter>", lambda e: btn.config(highlightbackground=self.active_border, fg=self.active_border))
        btn.bind("<Leave>", lambda e: btn.config(highlightbackground=self.border_color, fg="#333333"))
        return btn

    def setup_ui(self):
        tk.Label(self.root, text="✨ ASSET ALIGNMENT PRO 7.4", bg="#ffffff", fg=self.active_border, font=("Segoe UI", 18, "bold")).pack(pady=15)
        main_f = tk.Frame(self.root, bg="#ffffff"); main_f.pack(fill="both", expand=True, padx=40)

        # 路径设置
        self.path_cn = self.create_path_row(main_f, "📂 中文资产源 (CN Source):")
        self.path_jp = self.create_path_row(main_f, "📂 日文资产源 (JP Source):")
        self.path_save = self.create_path_row(main_f, "💾 报表保存位置 (Output Path):")

        # 预估面板
        ctrl_f = tk.LabelFrame(main_f, text=" ⚙️ 预估控制 ", bg="#ffffff", padx=15, pady=10, relief="flat", highlightthickness=1, highlightbackground=self.border_color)
        ctrl_f.pack(fill="x", pady=10)
        self.scan_btn = self.create_outline_btn(ctrl_f, "🔍 1. 扫描并采样", self.start_async_scan, width=15)
        self.scan_btn.grid(row=0, column=0)
        
        tk.Label(ctrl_f, text="🖼️ 缩放:", bg="#ffffff").grid(row=0, column=1, padx=5)
        self.scale_var = tk.IntVar(value=50)
        self.scale_slider = tk.Scale(ctrl_f, from_=10, to=100, orient="horizontal", variable=self.scale_var, bg="#ffffff", highlightthickness=0, command=lambda e: self.update_estimates())
        self.scale_slider.grid(row=0, column=2, sticky="ew")

        # API 配置
        api_f = tk.LabelFrame(main_f, text=" 🔐 API 配置 ", bg="#ffffff", padx=15, pady=10, relief="flat", highlightthickness=1, highlightbackground=self.border_color)
        api_f.pack(fill="x", pady=10)
        self.api_entry = tk.Entry(api_f, bg="#ffffff", show="*", relief="flat", highlightthickness=1, highlightbackground=self.border_color); self.api_entry.grid(row=0, column=0, padx=5, sticky="ew")
        self.url_entry = tk.Entry(api_f, bg="#ffffff", width=40); self.url_entry.grid(row=0, column=1, padx=5); self.url_entry.insert(0, "https://one-api-litellm.公司名.com/v1")

        # 实时总价 (基于实测单价)
        self.est_box = tk.Frame(main_f, bg="#f0f7ff", highlightthickness=1, highlightbackground=self.active_border)
        self.est_box.pack(fill="x", pady=10)
        self.est_label = tk.Label(self.est_box, text="等待采样数据...", bg="#f0f7ff", justify="left", font=("Segoe UI", 10))
        self.est_label.pack(padx=15, pady=12)

        # 执行
        exec_f = tk.Frame(main_f, bg="#ffffff"); exec_f.pack(fill="x")
        tk.Label(exec_f, text="⏱️ 间隔(s):", bg="#ffffff").pack(side="left")
        self.delay_spin = tk.Spinbox(exec_f, from_=0.1, to=5.0, increment=0.1, width=5); self.delay_spin.pack(side="left", padx=5)
        
        self.start_btn = self.create_outline_btn(main_f, "🚀 确认预算并执行 (任务后自动抹除Key)", self.start_task)
        self.start_btn.config(font=("Segoe UI", 12, "bold"), state="disabled"); self.start_btn.pack(fill="x", pady=10)

        self.progress_bar = ttk.Progressbar(main_f, mode="determinate"); self.progress_bar.pack(fill="x")
        self.log_area = scrolledtext.ScrolledText(main_f, height=8, bg="#fafafa", relief="flat", highlightthickness=1, highlightbackground=self.border_color)
        self.log_area.pack(fill="both", expand=True, pady=10)

    def create_path_row(self, parent, label):
        tk.Label(parent, text=label, bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(5,0))
        f = tk.Frame(parent, bg="#ffffff"); f.pack(fill="x", pady=2)
        e = tk.Entry(f, bg="#ffffff", relief="flat", highlightthickness=1, highlightbackground=self.border_color)
        e.pack(side="left", fill="x", expand=True, ipady=4)
        self.create_outline_btn(f, "📁 浏览", lambda: self.select_p(e)).pack(side="right", padx=5)
        return e

    def select_p(self, e):
        p = filedialog.askdirectory(); e.delete(0, tk.END); e.insert(0, p if p else "")

    def update_estimates(self):
        if self.total_count == 0: return
        scale = self.scale_var.get() / 100.0
        # 预估总价逻辑
        token_base = self.sample_token_per_img if self.sample_token_per_img > 0 else 1000
        est_tokens_total = self.total_count * token_base
        est_total_cost = (est_tokens_total / 1000000) * self.price_per_m
        
        info = (f"📊 资产总数: {self.total_count}\n"
                f"💵 实测预估总价: ${est_total_cost:.4f} (基于单价 ${self.price_per_m}/1M)\n"
                f"📝 采样单图消耗: {int(token_base)} Tokens | 长文本补全模式: ON")
        self.est_label.config(text=info, fg="#0078d7")

    def start_async_scan(self):
        if not self.api_entry.get(): messagebox.showwarning("提示", "采样需要 API Key"); return
        self.scan_btn.config(state="disabled", text="⌛ 采样中...")
        threading.Thread(target=self.do_scan_sample, daemon=True).start()

    def do_scan_sample(self):
        try:
            count = 0; size = 0; sample_p = None
            for p in [self.path_cn.get(), self.path_jp.get()]:
                if os.path.exists(p):
                    for r, _, fs in os.walk(p):
                        for f in fs:
                            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                                count += 1; full_p = os.path.join(r, f); size += os.path.getsize(full_p)
                                if not sample_p: sample_p = full_p
            self.total_count = count; self.total_raw_size = size
            if sample_p:
                client = OpenAI(api_key=self.api_entry.get().strip(), base_url=self.url_entry.get().strip())
                img_ai, _ = self.process_image_standard(sample_p, self.scale_var.get()/100.0)
                b64 = base64.b64encode(img_ai).decode('utf-8')
                res = client.chat.completions.create(
                    model=self.target_model,
                    messages=[{"role":"user","content":[{"type":"text","text":"ocr"},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}],
                    max_tokens=1000 # 预留给长文本
                )
                self.sample_token_per_img = res.usage.total_tokens
            self.root.after(0, self.update_estimates)
            self.scan_btn.config(state="normal", text="🔄 重新采样"); self.start_btn.config(state="normal")
        except Exception as e: self.log(f"❌ 采样失败: {e}"); self.scan_btn.config(state="normal")

    def process_image_standard(self, path, scale):
        with Image.open(path) as img:
            if img.mode in ("RGBA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
                img = bg
            else: img = img.convert("RGB")
            w, h = img.size; img.thumbnail((max(1, int(w*scale)), max(1, int(h*scale))))
            buf_ai = io.BytesIO(); img.save(buf_ai, format='JPEG', quality=85)
            buf_xl = io.BytesIO(); img.save(buf_xl, format='PNG')
            return buf_ai.getvalue(), buf_xl

    def start_task(self):
        self.actual_tokens_total = 0; self.start_btn.config(state="disabled")
        threading.Thread(target=self.run_task, daemon=True).start()

    def run_task(self):
        try:
            client = OpenAI(api_key=self.api_entry.get().strip(), base_url=self.url_entry.get().strip())
            scale = self.scale_var.get() / 100.0; delay = float(self.delay_spin.get())
            cn_map = self.scan_to_map(self.path_cn.get()); jp_map = self.scan_to_map(self.path_jp.get())
            all_files = sorted(list(set(cn_map.keys()) | set(jp_map.keys())))
            save_p = os.path.join(self.path_save.get(), f"AssetSync_{datetime.now().strftime('%m%d_%H%M')}.xlsx")
            writer = pd.ExcelWriter(save_p, engine='xlsxwriter')
            ws = writer.book.add_worksheet('OCR_Result'); ws.set_default_row(90)
            ws.set_column('D:D', 25); ws.set_column('G:G', 25)
            fmt_t = writer.book.add_format({'valign':'vcenter', 'text_wrap':True, 'border':1})
            
            for idx, fname in enumerate(all_files):
                r_idx = idx + 1; self.progress_bar['value'] = (r_idx/len(all_files))*100
                ws.write(r_idx, 0, fname, fmt_t)
                for col_off, p_list in [(1, cn_map.get(fname, [])), (4, jp_map.get(fname, []))]:
                    if p_list:
                        p = p_list[0]
                        try:
                            img_ai, img_xl = self.process_image_standard(p, scale)
                            b64 = base64.b64encode(img_ai).decode('utf-8')
                            res = client.chat.completions.create(
                                model=self.target_model,
                                messages=[{"role":"user","content":[{"type":"text","text":"请完整识别图中文案，禁止省略或截断。"},{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}],
                                max_tokens=1000, temperature=0.1 # 👈 关键修复
                            )
                            self.actual_tokens_total += res.usage.total_tokens
                            ws.write(r_idx, col_off+1, res.choices[0].message.content.strip(), fmt_t)
                            ws.insert_image(r_idx, col_off+2, p, {'image_data': img_xl, 'x_scale':0.4, 'y_scale':0.4})
                        except: ws.write(r_idx, col_off+1, "/", fmt_t)
                time.sleep(delay)
            writer.close()
            final_cost = (self.actual_tokens_total / 1000000) * self.price_per_m
            messagebox.showinfo("完成", f"✅ 处理成功！\n真实消耗: {self.actual_tokens_total} Tokens\n实结金额: ${final_cost:.4f}")
        except Exception as e: self.log(f"❌ 错误: {e}")
        finally: self.api_entry.delete(0, tk.END); self.start_btn.config(state="normal")

    def scan_to_map(self, p):
        m = {}
        if not p or not os.path.exists(p): return m
        for r, _, fs in os.walk(p):
            for f in fs:
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    if f not in m: m[f] = []
                    m[f].append(os.path.join(r, f))
        return m

    def log(self, msg):
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"); self.log_area.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk(); app = AssetProV74(root); root.mainloop()
