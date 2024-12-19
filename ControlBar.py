from tkinter import ttk
import tkinter as tk
class ControlBar(ttk.Frame):
    def __init__(self, parent, mic_callback=None, camera_callback=None, screen_callback=None):
        super().__init__(parent)
        
        # 保存回调函数
        self.mic_callback = mic_callback
        self.camera_callback = camera_callback
        self.screen_callback = screen_callback
        
        # 创建风格
        style = ttk.Style()
        style.configure('Active.TButton', background='green')
        style.configure('Inactive.TButton', background='red')
        
        # 使用Grid布局管理器
        self.grid_columnconfigure(0, weight=1)
        
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 创建左侧控制按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.LEFT)
        
        # 创建右侧聊天框架
        chat_frame = ttk.Frame(main_frame)
        chat_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # 创建控制按钮
        self.create_buttons(button_frame)
        
        # 创建聊天输入区域
        self.create_chat_input(chat_frame)
        
        # 初始状态为未激活
        self.mic_active = False
        self.camera_active = False
        self.screen_active = False
        
        # 固定在底部
        self.pack(side=tk.BOTTOM, fill=tk.X)
        
    def create_buttons(self, parent):
        # 麦克风按钮
        self.mic_btn = ttk.Button(
            parent, 
            text="🎤", 
            width=3,
            command=self.toggle_mic,
            style='Inactive.TButton'
        )
        self.mic_btn.pack(side=tk.LEFT, padx=5)
        
        # 摄像头按钮
        self.camera_btn = ttk.Button(
            parent, 
            text="📷", 
            width=3,
            command=self.toggle_camera,
            style='Inactive.TButton'
        )
        self.camera_btn.pack(side=tk.LEFT, padx=5)
        
        # 屏幕共享按钮
        self.screen_btn = ttk.Button(
            parent, 
            text="🖥️", 
            width=3,
            command=self.toggle_screen,
            style='Inactive.TButton'
        )
        self.screen_btn.pack(side=tk.LEFT, padx=5)
        
    def create_chat_input(self, parent):
        # 创建聊天输入框和发送按钮
        self.chat_input = ttk.Entry(parent)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        self.send_btn = ttk.Button(
            parent,
            text="发送",
            command=self.send_message
        )
        self.send_btn.pack(side=tk.RIGHT, padx=5)
        
    def toggle_mic(self):
        if self.mic_callback:
            success = self.mic_callback(not self.mic_active)
            if success:
                self.mic_active = not self.mic_active
                self.mic_btn.configure(
                    style='Active.TButton' if self.mic_active else 'Inactive.TButton'
                )
                
    def toggle_camera(self):
        if self.camera_callback:
            success = self.camera_callback(not self.camera_active)
            if success:
                self.camera_active = not self.camera_active
                self.camera_btn.configure(
                    style='Active.TButton' if self.camera_active else 'Inactive.TButton'
                )
                
    def toggle_screen(self):
        if self.screen_callback:
            success = self.screen_callback(not self.screen_active)
            if success:
                self.screen_active = not self.screen_active
                self.screen_btn.configure(
                    style='Active.TButton' if self.screen_active else 'Inactive.TButton'
                )
                
    def send_message(self):
        message = self.chat_input.get()
        if message and hasattr(self.master, 'send_message'):
            self.master.send_message(message)
            self.chat_input.delete(0, tk.END)
            
    def get_message(self):
        """获取输入框中的消息"""
        return self.chat_input.get()
        
    def clear_input(self):
        """清空输入框"""
        self.chat_input.delete(0, tk.END)