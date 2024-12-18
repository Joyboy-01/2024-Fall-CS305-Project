import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import math

class VideoGridManager:
    def __init__(self, parent_frame):
        self.parent_frame = parent_frame
        self.video_frames = {}
        self.screen_share_frame = None
        self.is_screen_sharing = False
        
        # 主容器框架
        self.main_container = ttk.Frame(parent_frame)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # 视频容器框架 - 固定高度留出控制按钮空间
        self.container_frame = ttk.Frame(self.main_container)
        self.container_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 50))  # 底部留出50像素给控制按钮
        
        # 设置基础网格
        self.container_frame.columnconfigure(0, weight=1)
        self.container_frame.rowconfigure(0, weight=1)
        
        # 创建布局框架
        self.layout_frame = ttk.Frame(self.container_frame)
        self.layout_frame.grid(row=0, column=0, sticky='nsew')
        
    def add_video(self, participant_id, initial_image=None):
        """添加新的固定大小的视频框"""
        if participant_id in self.video_frames:
            return
            
        # 创建固定大小的框架
        frame = ttk.Frame(self.layout_frame, width=320, height=240)
        frame.grid_propagate(False)  # 防止内容改变框架大小
        
        label = ttk.Label(frame)
        label.pack(fill=tk.BOTH, expand=True)
        
        self.video_frames[participant_id] = {
            'frame': frame,
            'label': label
        }
        
        if initial_image:
            self.update_video(participant_id, initial_image)
            
        self._update_layout()

        
    def remove_video(self, participant_id):
        """移除视频框"""
        if participant_id in self.video_frames:
            self.video_frames[participant_id]['frame'].destroy()
            del self.video_frames[participant_id]
            self._update_layout()
            
    def update_video(self, participant_id, image):
        """更新视频帧"""
        if participant_id not in self.video_frames:
            self.add_video(participant_id)
            
        frame_info = self.video_frames[participant_id]
        # 根据当前布局调整图像大小
        resized_image = self._resize_image_for_layout(image)
        photo = ImageTk.PhotoImage(resized_image)
        frame_info['label'].configure(image=photo)
        frame_info['label'].image = photo  # 保持引用
        
    def start_screen_share(self):
        """开始屏幕共享"""
        self.is_screen_sharing = True
        if not self.screen_share_frame:
            self.screen_share_frame = ttk.Frame(self.layout_frame)
            self.screen_share_label = ttk.Label(self.screen_share_frame)
            self.screen_share_label.pack(fill=tk.BOTH, expand=True)
        self._update_layout()
        
    def stop_screen_share(self):
        """停止屏幕共享"""
        self.is_screen_sharing = False
        if self.screen_share_frame:
            self.screen_share_frame.pack_forget()
        self._update_layout()
        
    def update_screen_share(self, image):
        """更新屏幕共享图像"""
        if not self.is_screen_sharing:
            return
            
        if not self.screen_share_frame:
            self.start_screen_share()
            
        # 调整屏幕共享图像大小
        resized_image = self._resize_image_for_screen_share(image)
        photo = ImageTk.PhotoImage(resized_image)
        self.screen_share_label.configure(image=photo)
        self.screen_share_label.image = photo
        
    def _update_layout(self):
        """更新整体布局"""
        # 清除现有布局
        for frame_info in self.video_frames.values():
            frame_info['frame'].grid_forget()
        if self.screen_share_frame:
            self.screen_share_frame.grid_forget()

        if self.is_screen_sharing:
            # 屏幕共享模式 - 只显示屏幕共享内容
            self.layout_frame.grid_columnconfigure(0, weight=1)
            self.layout_frame.grid_rowconfigure(0, weight=1)
            
            if not self.screen_share_frame:
                self.screen_share_frame = ttk.Frame(self.layout_frame)
                self.screen_share_label = ttk.Label(self.screen_share_frame)
                self.screen_share_label.pack(fill=tk.BOTH, expand=True)
            
            self.screen_share_frame.grid(row=0, column=0, sticky='nsew', padx=2, pady=2)
        else:
            # 视频模式 - 均分空间
            self._arrange_videos_in_grid(self.layout_frame)
            
    def _arrange_videos_in_grid(self, container):
        """在网格中均匀排列视频"""
        if not self.video_frames:
            return
            
        n = len(self.video_frames)
        if n <= 2:
            cols = n
            rows = 1
        else:
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            
        # 重置网格配置
        for i in range(cols):
            container.grid_columnconfigure(i, weight=1)
        for i in range(rows):
            container.grid_rowconfigure(i, weight=1)
        
        # 计算每个视频框的固定大小
        base_width = 320  # 基础宽度
        base_height = 240  # 基础高度
        
        # 排列视频框
        for idx, frame_info in enumerate(self.video_frames.values()):
            row = idx // cols
            col = idx % cols
            frame = frame_info['frame']
            frame.grid(row=row, column=col, sticky='nsew', padx=2, pady=2)
            
            # 设置固定大小
            frame.configure(width=base_width, height=base_height)
            frame.grid_propagate(False)  # 防止内容改变框架大小


    def _resize_image_for_layout(self, image):
        """根据布局调整图像大小"""
        base_width = 320  # 基础宽度
        base_height = 240  # 基础高度
        
        # 获取当前容器大小
        container_width = self.container_frame.winfo_width() or base_width
        container_height = self.container_frame.winfo_height() or base_height
        
        # 计算目标大小
        n = len(self.video_frames)
        if self.is_screen_sharing:
            # 如果是屏幕共享模式，视频窗口占25%宽度
            target_width = container_width // 4
        else:
            # 普通模式，根据网格划分
            cols = math.ceil(math.sqrt(n))
            target_width = container_width // cols

        # 保持宽高比
        aspect_ratio = base_width / base_height
        target_height = int(target_width / aspect_ratio)
        
        # 确保最小尺寸
        target_width = max(160, target_width)
        target_height = max(120, target_height)
            
        return image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
    def _resize_image_for_screen_share(self, image):
        """调整屏幕共享图像大小"""
        # 获取父容器大小
        container_width = self.layout_frame.winfo_width()
        container_height = self.layout_frame.winfo_height()
        
        # 如果有视频，则预留空间
        if self.video_frames:
            container_width = int(container_width * 0.8)  # 预留20%给视频
            
        # 保持宽高比
        w, h = image.size
        aspect_ratio = w / h
        
        if container_width / container_height > aspect_ratio:
            new_height = container_height
            new_width = int(container_height * aspect_ratio)
        else:
            new_width = container_width
            new_height = int(container_width / aspect_ratio)
            
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)