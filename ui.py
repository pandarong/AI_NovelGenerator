# ui.py
# -*- coding: utf-8 -*-

import logging
import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
import traceback
from config_manager import load_config, save_config
from utils import read_file, save_string_to_txt
from novel_generator import (
    Novel_novel_directory_generate,
    generate_chapter_draft,
    finalize_chapter,
    import_knowledge_file,
    clear_vector_store,
    get_last_n_chapters_text,
    summarize_recent_chapters
)
from consistency_checker import check_consistency

def log_error(message: str):
    """
    用于打印详细的错误信息和堆栈信息。
    """
    logging.error(f"{message}\n{traceback.format_exc()}")

# 设置全局主题和颜色
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class NovelGeneratorGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Novel Generator GUI (CustomTkinter)")
        self.master.iconbitmap("icon.ico")
        # 窗口最大化
        self.master.state("zoomed")
        # 配置窗口大小
        self.master.geometry("1428x960")

        # 配置持久化
        self.config_file = "config.json"
        self.loaded_config = load_config(self.config_file)

        # ========== 主要的属性变量 ==========
        self.api_key_var = ctk.StringVar(value=self.loaded_config.get("api_key", ""))
        self.base_url_var = ctk.StringVar(value=self.loaded_config.get("base_url", "https://api.agicto.cn/v1"))
        self.interface_format_var = ctk.StringVar(value=self.loaded_config.get("interface_format", "OpenAI"))
        self.model_name_var = ctk.StringVar(value=self.loaded_config.get("model_name", "gpt-4o-mini"))

        self.embedding_url_var = ctk.StringVar(value=self.loaded_config.get("embedding_url", "")) 
        self.embedding_model_name_var = ctk.StringVar(value=self.loaded_config.get("embedding_model_name", ""))

        self.temperature_var = ctk.DoubleVar(value=self.loaded_config.get("temperature", 0.7))
        self.topic_default = self.loaded_config.get("topic", "")
        self.genre_var = ctk.StringVar(value=self.loaded_config.get("genre", "玄幻"))
        self.num_chapters_var = ctk.IntVar(value=self.loaded_config.get("num_chapters", 10))
        self.word_number_var = ctk.IntVar(value=self.loaded_config.get("word_number", 3000))
        self.filepath_var = ctk.StringVar(value=self.loaded_config.get("filepath", ""))

        self.chapter_num_var = ctk.IntVar(value=1)

        # ========== 主容器使用 TabView ==========
        self.tabview = ctk.CTkTabview(self.master, width=1200, height=800)
        self.tabview.pack(fill="both", expand=True)

        # 创建各个Tab
        self.main_tab = self.tabview.add("Main Functions")
        self.setting_tab = self.tabview.add("Novel Settings")
        self.directory_tab = self.tabview.add("Novel Directory")
        self.character_tab = self.tabview.add("Character State")
        self.summary_tab = self.tabview.add("Global Summary")

        # 构建主功能Tab的布局
        self.build_main_tab()

        # 构建“Novel Settings”编辑Tab
        self.build_setting_tab()

        # 构建“Novel Directory”编辑Tab
        self.build_directory_tab()

        # 角色状态 Tab
        self.build_character_tab()

        # 全局摘要 Tab
        self.build_summary_tab()

    # ------------------ 主功能 Tab ------------------
    def build_main_tab(self):
        """
        主Tab: 左侧显示章节草稿/日志, 右侧是功能区 & 配置区
        """
        self.main_tab.rowconfigure(0, weight=1)
        self.main_tab.columnconfigure(0, weight=1)
        self.main_tab.columnconfigure(1, weight=0)

        # 左侧Frame
        self.left_frame = ctk.CTkFrame(self.main_tab)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        # 右侧Frame
        self.right_frame = ctk.CTkFrame(self.main_tab)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

        # 左侧布局
        self.build_left_layout()
        # 右侧布局
        self.build_right_layout()

    def build_left_layout(self):
        """
        左侧包含两个区域：
        1. 本章草稿内容（可编辑）
        2. 输出日志（只读）
        """
        self.left_frame.grid_rowconfigure(0, weight=3)
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        # 本章内容
        chapter_label = ctk.CTkLabel(self.left_frame, text="本章内容", font=("Microsoft YaHei", 14))
        chapter_label.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="w")

        # 章节草稿：可编辑
        self.chapter_result = ctk.CTkTextbox(self.left_frame, wrap="word", font=("Microsoft YaHei", 14))
        self.chapter_result.grid(row=0, column=0, sticky="nsew", padx=5, pady=(0, 5))

        # 输出日志
        log_label = ctk.CTkLabel(self.left_frame, text="输出日志 (只读)", font=("Microsoft YaHei", 14))
        log_label.grid(row=1, column=0, padx=5, pady=(5, 0), sticky="w")

        # 日志：只读
        self.log_text = ctk.CTkTextbox(self.left_frame, wrap="word", font=("Microsoft YaHei", 12))
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.log_text.configure(state="disabled")

    def build_right_layout(self):
        """
        右侧用于显示配置与功能按钮。
        其中配置被拆分到一个子 TabView：AI接口配置 和 Embedding配置。
        下面再放与小说相关的输入(主题/类型/章节数等)与功能按钮。
        """
        self.right_frame.grid_rowconfigure(0, weight=0)
        self.right_frame.grid_rowconfigure(1, weight=0)
        self.right_frame.grid_rowconfigure(2, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=0)
        self.right_frame.grid_columnconfigure(1, weight=1)

        # ========== 1. 配置项 TabView（AI接口配置 & Embedding配置） ==========
        self.config_tabview = ctk.CTkTabview(self.right_frame)
        self.config_tabview.grid(row=0, column=0, columnspan=2, sticky="we", padx=5, pady=5)

        self.ai_config_tab = self.config_tabview.add("LLM Model settings")
        self.embeddings_config_tab = self.config_tabview.add("Embedding settings")

        # 构建这两个 Tab 的布局
        self.build_ai_config_tab()
        self.build_embeddings_config_tab()

        # ========== 2. 与小说相关的参数区 ==========
        self.build_novel_params_area(start_row=1)

        # ========== 3. 放主要功能按钮 & “保存/加载配置”按钮区 ==========
        self.build_main_buttons_area(start_row=10)

    def build_ai_config_tab(self):
        """
        在 AI接口配置 子Tab 上放置：
        - API Key
        - Base URL
        - 接口格式
        - 模型名称
        - Temperature
        """
        for i in range(5):
            self.ai_config_tab.grid_rowconfigure(i, weight=0)
        self.ai_config_tab.grid_columnconfigure(0, weight=0)
        self.ai_config_tab.grid_columnconfigure(1, weight=1)

        def on_interface_format_changed(new_value):
            # 如果用户切换接口格式，可根据需要修改BaseURL为默认值
            if new_value == "Ollama":
                self.base_url_var.set("http://localhost:11434/v1")
            elif new_value == "ML Studio":
                self.base_url_var.set("http://localhost:1234/v1")
            elif new_value == "OpenAI":
                self.base_url_var.set("https://api.agicto.cn/v1")

        # 1. API Key
        api_key_label = ctk.CTkLabel(self.ai_config_tab, text="API Key:", font=("Microsoft YaHei", 12))
        api_key_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        api_key_entry = ctk.CTkEntry(self.ai_config_tab, textvariable=self.api_key_var, font=("Microsoft YaHei", 12))
        api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # 2. Base URL
        base_url_label = ctk.CTkLabel(self.ai_config_tab, text="Base URL:", font=("Microsoft YaHei", 12))
        base_url_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        base_url_entry = ctk.CTkEntry(self.ai_config_tab, textvariable=self.base_url_var, font=("Microsoft YaHei", 12))
        base_url_entry.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        # 3. 接口格式
        interface_label = ctk.CTkLabel(self.ai_config_tab, text="接口格式:", font=("Microsoft YaHei", 12))
        interface_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        interface_options = ["OpenAI", "Ollama", "ML Studio", "Local"]
        interface_dropdown = ctk.CTkOptionMenu(
            self.ai_config_tab, 
            values=interface_options, 
            variable=self.interface_format_var,
            command=on_interface_format_changed,
            font=("Microsoft YaHei", 12)
        )
        interface_dropdown.grid(row=2, column=1, padx=5, pady=5, sticky="nsew")

        # 4. 模型名称
        model_name_label = ctk.CTkLabel(self.ai_config_tab, text="Model Name:", font=("Microsoft YaHei", 12))
        model_name_label.grid(row=3, column=0, padx=5, pady=5, sticky="e")
        model_name_entry = ctk.CTkEntry(self.ai_config_tab, textvariable=self.model_name_var, font=("Microsoft YaHei", 12))
        model_name_entry.grid(row=3, column=1, padx=5, pady=5, sticky="nsew")

        # 5. Temperature
        temp_label = ctk.CTkLabel(self.ai_config_tab, text="Temperature:", font=("Microsoft YaHei", 12))
        temp_label.grid(row=4, column=0, padx=5, pady=5, sticky="e")

        def update_temp_label(value):
            self.temp_value_label.configure(text=f"{float(value):.2f}")

        temp_scale = ctk.CTkSlider(
            self.ai_config_tab, 
            from_=0.0, to=1.0, 
            number_of_steps=100,
            command=update_temp_label, 
            variable=self.temperature_var
        )
        temp_scale.grid(row=4, column=1, padx=5, pady=5, sticky="we")
        
        self.temp_value_label = ctk.CTkLabel(self.ai_config_tab, text=f"{self.temperature_var.get():.2f}", font=("Microsoft YaHei", 12))
        self.temp_value_label.grid(row=4, column=2, padx=1, pady=1, sticky="w")

    def build_embeddings_config_tab(self):
        """
        在 Embedding配置 子Tab 上放置：
        - Embedding URL
        - Embedding 模型名称
        """
        for i in range(2):
            self.embeddings_config_tab.grid_rowconfigure(i, weight=0)
        self.embeddings_config_tab.grid_columnconfigure(0, weight=0)
        self.embeddings_config_tab.grid_columnconfigure(1, weight=1)

        # 1. Embedding URL
        embedding_url_label = ctk.CTkLabel(self.embeddings_config_tab, text="Embedding URL:", font=("Microsoft YaHei", 12))
        embedding_url_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        embedding_url_entry = ctk.CTkEntry(self.embeddings_config_tab, textvariable=self.embedding_url_var, font=("Microsoft YaHei", 12))
        embedding_url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        # 2. Embedding 模型名称
        emb_model_name_label = ctk.CTkLabel(self.embeddings_config_tab, text="Embedding Model Name:", font=("Microsoft YaHei", 12))
        emb_model_name_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        emb_model_name_entry = ctk.CTkEntry(self.embeddings_config_tab, textvariable=self.embedding_model_name_var, font=("Microsoft YaHei", 12))
        emb_model_name_entry.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

    def build_novel_params_area(self, start_row=2):
        """
        放置与小说本身相关的一些配置：主题、类型、章节数、文件路径等
        """
        # 主题(Topic)
        topic_label = ctk.CTkLabel(self.right_frame, text="主题(Topic):", font=("Microsoft YaHei", 12))
        topic_label.grid(row=start_row, column=0, padx=5, pady=5, sticky="e")
        self.topic_text = ctk.CTkTextbox(self.right_frame, width=200, height=80, wrap="word", font=("Microsoft YaHei", 12))
        self.topic_text.grid(row=start_row, column=1, padx=5, pady=5, sticky="nsew")
        if self.topic_default:
            self.topic_text.insert("0.0", self.topic_default)

        # 类型(Genre)
        genre_label = ctk.CTkLabel(self.right_frame, text="类型(Genre):", font=("Microsoft YaHei", 12))
        genre_label.grid(row=start_row+1, column=0, padx=5, pady=5, sticky="e")
        genre_entry = ctk.CTkEntry(self.right_frame, textvariable=self.genre_var, font=("Microsoft YaHei", 12))
        genre_entry.grid(row=start_row+1, column=1, padx=5, pady=5, sticky="ew")

        # 章节数
        num_chapters_label = ctk.CTkLabel(self.right_frame, text="章节数:", font=("Microsoft YaHei", 12))
        num_chapters_label.grid(row=start_row+2, column=0, padx=5, pady=5, sticky="e")
        num_chapters_entry = ctk.CTkEntry(self.right_frame, textvariable=self.num_chapters_var, width=80, font=("Microsoft YaHei", 12))
        num_chapters_entry.grid(row=start_row+2, column=1, padx=5, pady=5, sticky="w")

        # 每章字数
        word_number_label = ctk.CTkLabel(self.right_frame, text="每章字数:", font=("Microsoft YaHei", 12))
        word_number_label.grid(row=start_row+3, column=0, padx=5, pady=5, sticky="e")
        word_number_entry = ctk.CTkEntry(self.right_frame, textvariable=self.word_number_var, width=80, font=("Microsoft YaHei", 12))
        word_number_entry.grid(row=start_row+3, column=1, padx=5, pady=5, sticky="w")

        # 保存路径
        filepath_label = ctk.CTkLabel(self.right_frame, text="保存路径:", font=("Microsoft YaHei", 12))
        filepath_label.grid(row=start_row+4, column=0, padx=5, pady=5, sticky="e")
        
        self.filepath_frame = ctk.CTkFrame(self.right_frame)
        self.filepath_frame.grid(row=start_row+4, column=1, padx=5, pady=5, sticky="nsew")
        self.filepath_frame.columnconfigure(0, weight=1)

        filepath_entry = ctk.CTkEntry(self.filepath_frame, textvariable=self.filepath_var, font=("Microsoft YaHei", 12))
        filepath_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        browse_btn = ctk.CTkButton(self.filepath_frame, text="浏览...", command=self.browse_folder, width=60, font=("Microsoft YaHei", 12))
        browse_btn.grid(row=0, column=1, padx=5, pady=5, sticky="e")

        # 章节号
        chapter_num_label = ctk.CTkLabel(self.right_frame, text="章节号:", font=("Microsoft YaHei", 12))
        chapter_num_label.grid(row=start_row+5, column=0, padx=5, pady=5, sticky="e")
        chapter_num_entry = ctk.CTkEntry(self.right_frame, textvariable=self.chapter_num_var, width=80, font=("Microsoft YaHei", 12))
        chapter_num_entry.grid(row=start_row+5, column=1, padx=5, pady=5, sticky="w")

        # 用户指导
        guide_label = ctk.CTkLabel(self.right_frame, text="本章指导:", font=("Microsoft YaHei", 12))
        guide_label.grid(row=start_row+6, column=0, padx=5, pady=5, sticky="ne")
        self.user_guide_text = ctk.CTkTextbox(self.right_frame, width=200, height=80, wrap="word", font=("Microsoft YaHei", 12))
        self.user_guide_text.grid(row=start_row+6, column=1, padx=5, pady=5, sticky="nsew")

    def build_main_buttons_area(self, start_row=10):
        """
        主要功能按钮 + 配置保存/加载 按钮
        """
        self.right_frame.grid_rowconfigure(start_row, weight=0)

        self.btn_frame_config = ctk.CTkFrame(self.right_frame)
        self.btn_frame_config.grid(row=start_row, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        self.btn_frame_config.columnconfigure(0, weight=1)
        self.btn_frame_config.columnconfigure(1, weight=1)

        save_config_btn = ctk.CTkButton(self.btn_frame_config, text="保存配置", command=self.save_config_btn, font=("Microsoft YaHei", 12))
        save_config_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        load_config_btn = ctk.CTkButton(self.btn_frame_config, text="加载配置", command=self.load_config_btn, font=("Microsoft YaHei", 12))
        load_config_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.btn_generate_full = ctk.CTkButton(
            self.right_frame, text="Step1. 生成设定 & 目录",
            command=self.generate_full_novel,
            font=("Microsoft YaHei", 12)
        )
        self.btn_generate_full.grid(row=start_row+1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        self.btn_generate_chapter = ctk.CTkButton(
            self.right_frame, text="Step2. 生成章节草稿",
            command=self.generate_chapter_draft_ui,
            font=("Microsoft YaHei", 12)
        )
        self.btn_generate_chapter.grid(row=start_row+2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        self.btn_finalize_chapter = ctk.CTkButton(
            self.right_frame, text="Step3. 定稿当前章节",
            command=self.finalize_chapter_ui,
            font=("Microsoft YaHei", 12)
        )
        self.btn_finalize_chapter.grid(row=start_row+3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        self.btn_check_consistency = ctk.CTkButton(
            self.right_frame, text="[可选]一致性审校",
            command=self.do_consistency_check,
            font=("Microsoft YaHei", 12)
        )
        self.btn_check_consistency.grid(row=start_row+4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        self.btn_import_knowledge = ctk.CTkButton(
            self.right_frame, text="[可选]导入知识库",
            command=self.import_knowledge_handler,
            font=("Microsoft YaHei", 12)
        )
        self.btn_import_knowledge.grid(row=start_row+5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        self.btn_clear_vectorstore = ctk.CTkButton(
            self.right_frame, text="清空向量库",
            fg_color="red",
            command=self.clear_vectorstore_handler,
            font=("Microsoft YaHei", 12)
        )
        self.btn_clear_vectorstore.grid(row=start_row+6, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        plot_arcs_btn = ctk.CTkButton(
            self.right_frame, text="[查看] 剧情要点",
            command=self.show_plot_arcs_ui,
            font=("Microsoft YaHei", 12)
        )
        plot_arcs_btn.grid(row=start_row+7, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

    # ------------------ Novel Settings Tab ------------------
    def build_setting_tab(self):
        self.setting_tab.rowconfigure(0, weight=0)
        self.setting_tab.rowconfigure(1, weight=1)
        self.setting_tab.columnconfigure(0, weight=1)

        load_btn = ctk.CTkButton(self.setting_tab, text="加载 Novel_setting.txt", command=self.load_novel_setting, font=("Microsoft YaHei", 12))
        load_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        save_btn = ctk.CTkButton(self.setting_tab, text="保存修改", command=self.save_novel_setting, font=("Microsoft YaHei", 12))
        save_btn.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.setting_text = ctk.CTkTextbox(self.setting_tab, wrap="word", font=("Microsoft YaHei", 12))
        self.setting_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    def load_novel_setting(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        setting_file = os.path.join(filepath, "Novel_setting.txt")
        content = read_file(setting_file)
        self.setting_text.delete("0.0", "end")
        self.setting_text.insert("0.0", content)
        self.log("已加载 Novel_setting.txt 内容到编辑区。")

    def save_novel_setting(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        content = self.setting_text.get("0.0", "end").strip()
        setting_file = os.path.join(filepath, "Novel_setting.txt")
        save_string_to_txt(content, setting_file)
        self.log("已保存对 Novel_setting.txt 的修改。")

    # ------------------ Novel Directory Tab ------------------
    def build_directory_tab(self):
        self.directory_tab.rowconfigure(0, weight=0)
        self.directory_tab.rowconfigure(1, weight=1)
        self.directory_tab.columnconfigure(0, weight=1)

        load_btn = ctk.CTkButton(self.directory_tab, text="加载 Novel_directory.txt", command=self.load_novel_directory, font=("Microsoft YaHei", 12))
        load_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        save_btn = ctk.CTkButton(self.directory_tab, text="保存修改", command=self.save_novel_directory, font=("Microsoft YaHei", 12))
        save_btn.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.directory_text = ctk.CTkTextbox(self.directory_tab, wrap="word", font=("Microsoft YaHei", 12))
        self.directory_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    def load_novel_directory(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        directory_file = os.path.join(filepath, "Novel_directory.txt")
        content = read_file(directory_file)
        self.directory_text.delete("0.0", "end")
        self.directory_text.insert("0.0", content)
        self.log("已加载 Novel_directory.txt 内容到编辑区。")

    def save_novel_directory(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        content = self.directory_text.get("0.0", "end").strip()
        directory_file = os.path.join(filepath, "Novel_directory.txt")
        save_string_to_txt(content, directory_file)
        self.log("已保存对 Novel_directory.txt 的修改。")

    # ------------------ Character State Tab ------------------
    def build_character_tab(self):
        self.character_tab.rowconfigure(0, weight=0)
        self.character_tab.rowconfigure(1, weight=1)
        self.character_tab.columnconfigure(0, weight=1)

        load_btn = ctk.CTkButton(self.character_tab, text="加载 character_state.txt", command=self.load_character_state, font=("Microsoft YaHei", 12))
        load_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        save_btn = ctk.CTkButton(self.character_tab, text="保存修改", command=self.save_character_state, font=("Microsoft YaHei", 12))
        save_btn.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.character_text = ctk.CTkTextbox(self.character_tab, wrap="word", font=("Microsoft YaHei", 12))
        self.character_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    def load_character_state(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        char_file = os.path.join(filepath, "character_state.txt")
        content = read_file(char_file)
        self.character_text.delete("0.0", "end")
        self.character_text.insert("0.0", content)
        self.log("已加载 character_state.txt 内容到编辑区。")

    def save_character_state(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        content = self.character_text.get("0.0", "end").strip()
        char_file = os.path.join(filepath, "character_state.txt")
        save_string_to_txt(content, char_file)
        self.log("已保存对 character_state.txt 的修改。")

    # ------------------ Global Summary Tab ------------------
    def build_summary_tab(self):
        self.summary_tab.rowconfigure(0, weight=0)
        self.summary_tab.rowconfigure(1, weight=1)
        self.summary_tab.columnconfigure(0, weight=1)

        load_btn = ctk.CTkButton(self.summary_tab, text="加载 global_summary.txt", command=self.load_global_summary, font=("Microsoft YaHei", 12))
        load_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        save_btn = ctk.CTkButton(self.summary_tab, text="保存修改", command=self.save_global_summary, font=("Microsoft YaHei", 12))
        save_btn.grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.summary_text = ctk.CTkTextbox(self.summary_tab, wrap="word", font=("Microsoft YaHei", 12))
        self.summary_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    def load_global_summary(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        summary_file = os.path.join(filepath, "global_summary.txt")
        content = read_file(summary_file)
        self.summary_text.delete("0.0", "end")
        self.summary_text.insert("0.0", content)
        self.log("已加载 global_summary.txt 内容到编辑区。")

    def save_global_summary(self):
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        content = self.summary_text.get("0.0", "end").strip()
        summary_file = os.path.join(filepath, "global_summary.txt")
        save_string_to_txt(content, summary_file)
        self.log("已保存对 global_summary.txt 的修改。")

    # ------------------ 配置管理 ------------------
    def load_config_btn(self):
        cfg = load_config(self.config_file)
        if cfg:
            self.api_key_var.set(cfg.get("api_key", ""))
            self.base_url_var.set(cfg.get("base_url", ""))
            self.interface_format_var.set(cfg.get("interface_format", "OpenAI"))
            self.model_name_var.set(cfg.get("model_name", ""))
            self.embedding_url_var.set(cfg.get("embedding_url", ""))
            self.embedding_model_name_var.set(cfg.get("embedding_model_name", ""))
            self.temperature_var.set(cfg.get("temperature", 0.7))
            self.genre_var.set(cfg.get("genre", ""))
            self.num_chapters_var.set(cfg.get("num_chapters", 10))
            self.word_number_var.set(cfg.get("word_number", 3000))
            self.filepath_var.set(cfg.get("filepath", ""))

            # 主题
            self.topic_text.delete("0.0", "end")
            self.topic_text.insert("0.0", cfg.get("topic", ""))

            self.log("已加载配置。")
        else:
            messagebox.showwarning("提示", "未找到或无法读取配置文件。")

    def save_config_btn(self):
        config_data = {
            "api_key": self.api_key_var.get(),
            "base_url": self.base_url_var.get(),
            "interface_format": self.interface_format_var.get(),
            "model_name": self.model_name_var.get(),
            "embedding_url": self.embedding_url_var.get(),
            "embedding_model_name": self.embedding_model_name_var.get(),
            "temperature": self.temperature_var.get(),
            "topic": self.topic_text.get("0.0", "end").strip(),
            "genre": self.genre_var.get(),
            "num_chapters": self.num_chapters_var.get(),
            "word_number": self.word_number_var.get(),
            "filepath": self.filepath_var.get()
        }
        if save_config(config_data, self.config_file):
            messagebox.showinfo("提示", "配置已保存至 config.json")
            self.log("配置已保存。")
        else:
            messagebox.showerror("错误", "保存配置失败。")

    def browse_folder(self):
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            self.filepath_var.set(selected_dir)

    # ------------------ 日志输出 ------------------
    def log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ------------------ 功能区 --------------------
    def disable_button(self, btn):
        btn.configure(state="disabled")

    def enable_button(self, btn):
        btn.configure(state="normal")

    def generate_full_novel(self):
        """生成小说设定 & 目录"""
        def task():
            self.disable_button(self.btn_generate_full)
            try:
                api_key = self.api_key_var.get().strip()
                base_url = self.base_url_var.get().strip()
                model_name = self.model_name_var.get().strip()
                topic = self.topic_text.get("0.0", "end").strip()
                genre = self.genre_var.get().strip()
                num_chapters = self.num_chapters_var.get()
                word_number = self.word_number_var.get()
                filepath = self.filepath_var.get().strip()
                temperature = self.temperature_var.get()

                if not filepath:
                    messagebox.showwarning("警告", "请先选择保存文件路径")
                    return

                self.log("开始生成小说设定和目录...")
                Novel_novel_directory_generate(
                    api_key=api_key,
                    base_url=base_url,
                    llm_model=model_name,
                    topic=topic,
                    genre=genre,
                    number_of_chapters=num_chapters,
                    word_number=word_number,
                    filepath=filepath,
                    temperature=temperature
                )
                self.log("✅ 小说设定和目录生成完成。查看 Novel_setting.txt 和 Novel_directory.txt。")
            except Exception as e:
                logging.error(f"生成小说设定 & 目录时出错: {e}")
                self.log(f"❌ 生成小说设定 & 目录时出错: {e}")
            finally:
                self.enable_button(self.btn_generate_full)

        thread = threading.Thread(target=task)
        thread.start()

    def generate_chapter_draft_ui(self):
        """生成当前章节的草稿"""
        def task():
            self.disable_button(self.btn_generate_chapter)
            try:
                api_key = self.api_key_var.get().strip()
                base_url = self.base_url_var.get().strip()
                model_name = self.model_name_var.get().strip()
                temperature = self.temperature_var.get()
                filepath = self.filepath_var.get().strip()

                if not filepath:
                    self.log("请先配置保存文件路径。")
                    return

                novel_settings_file = os.path.join(filepath, "Novel_setting.txt")
                novel_settings = read_file(novel_settings_file)
                if not novel_settings.strip():
                    self.log("⚠️ 未找到 Novel_setting.txt，请先生成设定。")
                    return

                character_state_file = os.path.join(filepath, "character_state.txt")
                character_state = read_file(character_state_file)
                global_summary_file = os.path.join(filepath, "global_summary.txt")
                global_summary = read_file(global_summary_file)
                novel_directory_file = os.path.join(filepath, "Novel_directory.txt")
                novel_directory = read_file(novel_directory_file)

                chap_num = self.chapter_num_var.get()
                word_number = self.word_number_var.get()
                user_guidance = self.user_guide_text.get("0.0", "end").strip()

                # 获取最近3章文本
                chapters_dir = os.path.join(filepath, "chapters")
                recent_3_texts = get_last_n_chapters_text(chapters_dir, chap_num, n=3)

                # 生成最近章节摘要
                recent_chapters_summary = summarize_recent_chapters(
                    llm_model=model_name,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=temperature,
                    chapters_text_list=recent_3_texts
                )

                self.log(f"开始生成第{chap_num}章草稿...")
                draft_text = generate_chapter_draft(
                    novel_settings=novel_settings,
                    global_summary=global_summary,
                    character_state=character_state,
                    recent_chapters_summary=recent_chapters_summary,
                    user_guidance=user_guidance,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name,
                    novel_number=chap_num,
                    word_number=word_number,
                    temperature=temperature,
                    novel_novel_directory=novel_directory,
                    filepath=filepath,
                    interface_format=self.interface_format_var.get().strip(),
                    embedding_model_name=self.embedding_model_name_var.get().strip(),
                    embedding_base_url=self.embedding_url_var.get().strip()
                )
                if draft_text:
                    self.log(f"✅ 第{chap_num}章草稿生成完成。请在左侧查看或编辑。")
                    self.chapter_result.delete("0.0", "end")
                    self.chapter_result.insert("0.0", draft_text)
                    self.chapter_result.see("end")
                else:
                    self.log("⚠️ 本章草稿生成失败或无内容。")

            except Exception as e:
                logging.error(f"生成章节草稿时出错: {e}")
                self.log(f"❌ 生成章节草稿时出错: {e}")
            finally:
                self.enable_button(self.btn_generate_chapter)

        thread = threading.Thread(target=task)
        thread.start()

    def finalize_chapter_ui(self):
        """定稿当前章节：更新全局摘要、角色状态、向量库等"""
        def task():
            self.disable_button(self.btn_finalize_chapter)
            try:
                api_key = self.api_key_var.get().strip()
                base_url = self.base_url_var.get().strip()
                model_name = self.model_name_var.get().strip()
                temperature = self.temperature_var.get()
                filepath = self.filepath_var.get().strip()
                interface_format = self.interface_format_var.get().strip()
                embedding_model_name = self.embedding_model_name_var.get().strip()

                if not filepath:
                    self.log("请先配置保存文件路径。")
                    return

                chap_num = self.chapter_num_var.get()
                word_number = self.word_number_var.get()

                self.log(f"开始定稿第{chap_num}章...")
                finalize_chapter(
                    novel_number=chap_num,
                    word_number=word_number,
                    api_key=api_key,
                    base_url=base_url,
                    interface_format=interface_format,
                    embedding_model_name=embedding_model_name,
                    model_name=model_name,
                    temperature=temperature,
                    filepath=filepath
                )
                self.log(f"✅ 第{chap_num}章定稿完成（已更新全局摘要、角色状态、剧情要点、向量库）。")

                # 读取定稿后的文本显示
                chap_file = os.path.join(filepath, "chapters", f"chapter_{chap_num}.txt")
                final_text = read_file(chap_file)
                self.chapter_result.delete("0.0", "end")
                self.chapter_result.insert("0.0", final_text)
                self.chapter_result.see("end")

            except Exception as e:
                logging.error(f"定稿章节时出错: {e}")
                self.log(f"❌ 定稿章节时出错: {e}")
            finally:
                self.enable_button(self.btn_finalize_chapter)

        thread = threading.Thread(target=task)
        thread.start()

    def do_consistency_check(self):
        """使用审校Agent对最新章节进行简单一致性或冲突检查"""
        def task():
            self.disable_button(self.btn_check_consistency)
            try:
                api_key = self.api_key_var.get().strip()
                base_url = self.base_url_var.get().strip()
                model_name = self.model_name_var.get().strip()
                temperature = self.temperature_var.get()
                filepath = self.filepath_var.get().strip()

                if not filepath:
                    self.log("请先配置保存文件路径。")
                    return

                novel_settings_file = os.path.join(filepath, "Novel_setting.txt")
                character_state_file = os.path.join(filepath, "character_state.txt")
                global_summary_file = os.path.join(filepath, "global_summary.txt")
                plot_arcs_file = os.path.join(filepath, "plot_arcs.txt")

                novel_setting = read_file(novel_settings_file)
                character_state = read_file(character_state_file)
                global_summary = read_file(global_summary_file)
                plot_arcs = read_file(plot_arcs_file)

                chap_num = self.chapter_num_var.get()
                chap_file = os.path.join(filepath, "chapters", f"chapter_{chap_num}.txt")
                chapter_text = read_file(chap_file)

                if not chapter_text.strip():
                    self.log("⚠️ 当前章节文件为空或不存在，无法审校。")
                    return

                self.log("开始一致性审校...")
                result = check_consistency(
                    novel_setting=novel_setting,
                    character_state=character_state,
                    global_summary=global_summary,
                    chapter_text=chapter_text,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name,
                    temperature=temperature,
                    plot_arcs=plot_arcs
                )
                self.log("审校结果：")
                self.log(result)

            except Exception as e:
                logging.error(f"审校时出错: {e}")
                self.log(f"❌ 审校时出错: {e}")
            finally:
                self.enable_button(self.btn_check_consistency)

        thread = threading.Thread(target=task)
        thread.start()

    def import_knowledge_handler(self):
        """处理导入知识库文件。"""
        selected_file = filedialog.askopenfilename(
            title="选择要导入的知识库文件",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if selected_file:
            def task():
                self.disable_button(self.btn_import_knowledge)
                try:
                    self.log(f"开始导入知识库文件: {selected_file}")
                    import_knowledge_file(
                        api_key=self.api_key_var.get().strip(),
                        base_url=self.base_url_var.get().strip(),
                        interface_format=self.interface_format_var.get().strip(),
                        embedding_model_name=self.embedding_model_name_var.get().strip(),
                        file_path=selected_file,
                        embedding_base_url=self.embedding_url_var.get().strip()
                    )
                    self.log("✅ 知识库文件导入完成。")
                except Exception as e:
                    logging.error(f"导入知识库时出错: {e}")
                    self.log(f"❌ 导入知识库时出错: {e}")
                finally:
                    self.enable_button(self.btn_import_knowledge)

            thread = threading.Thread(target=task)
            thread.start()

    def clear_vectorstore_handler(self):
        """清空向量库按钮：弹出二次确认。"""
        first_confirm = messagebox.askyesno("警告", "确定要清空本地向量库吗？此操作不可恢复！")
        if first_confirm:
            second_confirm = messagebox.askyesno("二次确认", "你确定真的要删除所有向量数据吗？此操作不可恢复！")
            if second_confirm:
                clear_vector_store()
                self.log("已清空向量库。")

    def show_plot_arcs_ui(self):
        """[查看]当前剧情要点"""
        filepath = self.filepath_var.get().strip()
        if not filepath:
            messagebox.showwarning("警告", "请先在主Tab中设置保存文件路径")
            return

        plot_arcs_file = os.path.join(filepath, "plot_arcs.txt")
        if not os.path.exists(plot_arcs_file):
            messagebox.showinfo("剧情要点", "当前还未生成任何剧情要点或未解决冲突。")
            return

        arcs_text = read_file(plot_arcs_file).strip()
        if not arcs_text:
            arcs_text = "当前没有记录的剧情要点或冲突。"

        top = ctk.CTkToplevel(self.master)
        top.title("剧情要点/未解决冲突")
        top.geometry("600x400")

        text_area = ctk.CTkTextbox(top, wrap="word", font=("Microsoft YaHei", 12))
        text_area.pack(fill="both", expand=True, padx=10, pady=10)

        text_area.insert("0.0", arcs_text)
        text_area.configure(state="disabled")


if __name__ == "__main__":
    app = ctk.CTk()
    gui = NovelGeneratorGUI(app)
    app.mainloop()
