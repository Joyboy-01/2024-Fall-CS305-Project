import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import math
import time
class VideoGridManager:
    def __init__(self, parent_frame):
        """初始化视频网格管理器"""
        self.parent_frame = parent_frame
        self.video_frames = {}  # {participant_id: {'frame': frame, 'label': label, 'active': bool}}
        self.screen_share_frame = None
        self.is_screen_sharing = False
        self.screen_sharer_id = None
        
        # 创建主容器
        self.container = ttk.Frame(parent_frame)
        self.container.grid(row=0, column=0, sticky='nsew')
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)
        
        # 创建视频网格容器
        self.video_grid = ttk.Frame(self.container)
        self.video_grid.grid(row=0, column=0, sticky='nsew')
        self.video_grid.grid_columnconfigure(0, weight=1)
        self.video_grid.grid_rowconfigure(0, weight=1)

    def add_video(self, participant_id, initial_image=None):
        """添加新的视频框"""
        if participant_id in self.video_frames:
            return
            
        frame = ttk.Frame(self.video_grid)
        label = ttk.Label(frame)
        label.grid(row=0, column=0, sticky='nsew')
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        
        self.video_frames[participant_id] = {
            'frame': frame,
            'label': label,
            'active': False
        }
        
        if initial_image:
            self.update_video(participant_id, initial_image)
            
        self.update_layout()
        
    def remove_video(self, participant_id):
        """移除视频框"""
        if participant_id in self.video_frames:
            self.video_frames[participant_id]['frame'].destroy()
            del self.video_frames[participant_id]
            self.update_layout()
    
    def set_video_active(self, participant_id, active):
        """设置参与者视频状态"""
        if participant_id in self.video_frames:
            self.video_frames[participant_id]['active'] = active
            if not active:
                # 显示黑屏
                label = self.video_frames[participant_id]['label']
                black_img = Image.new('RGB', (320, 240), color='black')
                photo = ImageTk.PhotoImage(black_img)
                label.configure(image=photo)
                label.image = photo
            self.update_layout()
    
    def update_video(self, participant_id, image):
        """更新视频帧"""
        if participant_id not in self.video_frames:
            self.add_video(participant_id)
            
        if not self.video_frames[participant_id]['active']:
            self.set_video_active(participant_id, True)
            
        frame_info = self.video_frames[participant_id]
        resized_image = self._resize_image_for_layout(image)
        photo = ImageTk.PhotoImage(resized_image)
        frame_info['label'].configure(image=photo)
        frame_info['label'].image = photo
    
    def start_screen_share(self, sharer_id):
        """开始屏幕共享"""
        if self.is_screen_sharing and self.screen_sharer_id != sharer_id:
            return False
            
        self.is_screen_sharing = True
        self.screen_sharer_id = sharer_id
        
        if not self.screen_share_frame:
            self.screen_share_frame = ttk.Frame(self.container)
            self.screen_share_label = ttk.Label(self.screen_share_frame)
            self.screen_share_label.grid(row=0, column=0, sticky='nsew')
            self.screen_share_frame.grid_columnconfigure(0, weight=1)
            self.screen_share_frame.grid_rowconfigure(0, weight=1)
            
        self.update_layout()
        return True
    
    def stop_screen_share(self, sharer_id):
        """停止屏幕共享"""
        if self.screen_sharer_id == sharer_id:
            self.is_screen_sharing = False
            self.screen_sharer_id = None
            if self.screen_share_frame:
                self.screen_share_frame.grid_remove()
            self.update_layout()
            return True
        return False
    
    def update_screen_share(self, image):
        """更新屏幕共享图像"""
        if not self.is_screen_sharing:
            self.start_screen_share('remote')  # 确保屏幕共享视图已经启动

        if not self.screen_share_frame:
            return
        try:
            container_width = self.container.winfo_width() or 800
            container_height = self.container.winfo_height() or 600
            
            # 保持宽高比
            w, h = image.size
            aspect_ratio = w / h
            
            if container_width / container_height > aspect_ratio:
                new_height = container_height
                new_width = int(container_height * aspect_ratio)
            else:
                new_width = container_width
                new_height = int(container_width / aspect_ratio)
                
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(resized_image)
            self.screen_share_label.configure(image=photo)
            self.screen_share_label.image = photo
        except Exception as e:
            print(f"Error updating screen share: {e}")
    
    def update_layout(self):
        """更新整体布局"""
        # 重置所有frame的grid
        for frame_info in self.video_frames.values():
            frame_info['frame'].grid_remove()
            
        if self.is_screen_sharing:
            # 屏幕共享模式
            self.video_grid.grid_remove()
            if self.screen_share_frame:
                self.screen_share_frame.grid(row=0, column=0, sticky='nsew')
        else:
            # 视频网格模式
            if self.screen_share_frame:
                self.screen_share_frame.grid_remove()
            self.video_grid.grid(row=0, column=0, sticky='nsew')
            
            # 获取活跃的视频
            active_videos = {pid: info for pid, info in self.video_frames.items() 
                           if info.get('active', False)}
            
            if not active_videos:
                return
                
            # 计算网格布局
            n = len(active_videos)
            cols = math.ceil(math.sqrt(n))
            rows = math.ceil(n / cols)
            
            # 配置网格
            for i in range(cols):
                self.video_grid.grid_columnconfigure(i, weight=1)
            for i in range(rows):
                self.video_grid.grid_rowconfigure(i, weight=1)
            
            # 放置视频框
            for idx, (pid, info) in enumerate(active_videos.items()):
                row = idx // cols
                col = idx % cols
                info['frame'].grid(row=row, column=col, sticky='nsew',
                                 padx=2, pady=2)
    
    def _resize_image_for_layout(self, image):
        """调整图像大小以适应布局"""
        container_width = self.video_grid.winfo_width() or 800
        container_height = self.video_grid.winfo_height() or 600
        
        # 计算每个视频框的目标大小
        active_count = sum(1 for info in self.video_frames.values() 
                          if info.get('active', False))
        if active_count == 0:
            active_count = 1
            
        cols = math.ceil(math.sqrt(active_count))
        target_width = container_width // cols
        
        # 保持宽高比 (16:9)
        aspect_ratio = 16/9
        target_height = int(target_width / aspect_ratio)
        
        # 确保最小尺寸
        target_width = max(320, target_width)
        target_height = max(180, target_height)
        
        return image.resize((target_width, target_height), Image.Resampling.LANCZOS)