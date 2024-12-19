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
        if not style.theme_names(): # 如果没有主题，设置一个默认主题
            style.theme_use('default')
        style.configure('Active.TButton', background='green')
        style.configure('Inactive.TButton', background='red')
        
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 创建按钮
        self.create_buttons(main_frame)
        
        # 初始状态为未激活
        self.mic_active = False
        self.camera_active = False
        self.screen_active = False
        
    def create_buttons(self, parent):
        # 创建一个框架来容纳所有按钮
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill=tk.X, expand=True)
        
        # 使按钮均匀分布
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)
        buttons_frame.grid_columnconfigure(2, weight=1)
        
        # 麦克风按钮
        self.mic_btn = ttk.Button(
            buttons_frame, 
            text="🎤", 
            width=3,
            command=self.toggle_mic,
            style='Inactive.TButton'
        )
        self.mic_btn.grid(row=0, column=0, padx=5, sticky='ew')
        
        # 摄像头按钮
        self.camera_btn = ttk.Button(
            buttons_frame, 
            text="📷", 
            width=3,
            command=self.toggle_camera,
            style='Inactive.TButton'
        )
        self.camera_btn.grid(row=0, column=1, padx=5, sticky='ew')
        
        # 屏幕共享按钮
        self.screen_btn = ttk.Button(
            buttons_frame, 
            text="🖥️", 
            width=3,
            command=self.toggle_screen,
            style='Inactive.TButton'
        )
        self.screen_btn.grid(row=0, column=2, padx=5, sticky='ew')
            
    def toggle_mic(self):
        if self.mic_callback:
            success = self.mic_callback(not self.mic_active)
            if success:
                self.mic_active = not self.mic_active
                self.mic_btn.configure(
                    style='Active.TButton' if self.mic_active else 'Inactive.TButton'
                )
                print(f"Mic toggled: {'on' if self.mic_active else 'off'}") 
                
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