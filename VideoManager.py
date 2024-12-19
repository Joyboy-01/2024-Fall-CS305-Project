import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import math

class VideoGridManager:
    def __init__(self, parent_frame):
        """初始化视频网格管理器"""
        self.parent_frame = parent_frame
        self.video_frames = {}  # {participant_id: {'frame': frame, 'label': label, 'active': bool}}
        self.screen_share_frame = None
        self.screen_share_label = None
        self.is_screen_sharing = False
        self.screen_sharer_id = None
        
        # 设置默认的视频尺寸和容器尺寸
        self.default_video_width = 320
        self.default_video_height = 240
        self.container_width = 800
        self.container_height = 600
        
        # 创建主容器
        self.container = ttk.Frame(parent_frame)
        self.container.grid(row=0, column=0, sticky='nsew')
        self.container.grid_propagate(False)  # 防止子组件影响容器大小
        self.container.configure(width=self.container_width, height=self.container_height)
        
        # 配置主容器权重
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)
        
        # 创建视频网格容器
        self.video_grid = ttk.Frame(self.container)
        self.video_grid.grid(row=0, column=0, sticky='nsew')
        
    def add_video(self, participant_id, initial_image=None):
        """添加新的视频框"""
        if participant_id in self.video_frames:
            return
            
        # 创建固定尺寸的视频框
        frame = ttk.Frame(self.video_grid)
        frame.configure(width=self.default_video_width, height=self.default_video_height)
        frame.grid_propagate(False)
        
        # 创建标签用于显示视频
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
            self.container.update_idletasks()
            self.update_layout()
    
    def set_video_active(self, participant_id, active):
        """设置视频状态"""
        if participant_id in self.video_frames:
            self.video_frames[participant_id]['active'] = active
            if not active:
                # 显示黑屏
                label = self.video_frames[participant_id]['label']
                black_img = Image.new('RGB', (self.default_video_width, self.default_video_height), color='black')
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
        
        # 调整图像大小并更新
        resized_image = self._resize_image_for_layout(image)
        photo = ImageTk.PhotoImage(resized_image)
        frame_info['label'].configure(image=photo)
        frame_info['label'].image = photo
        
        # 强制更新布局
        self.container.update_idletasks()

    def start_screen_share(self, sharer_id):
        """开始屏幕共享"""
        print(f"Starting screen share for {sharer_id}")
        if self.is_screen_sharing and self.screen_sharer_id != sharer_id:
            print("Another user is already sharing screen")
            return False
            
        self.is_screen_sharing = True
        self.screen_sharer_id = sharer_id
        
        if not self.screen_share_frame:
            # 创建屏幕共享框架
            print("Creating new screen share frame")
            self.screen_share_frame = ttk.Frame(self.container)
            self.screen_share_frame.grid(row=0, column=0, sticky='nsew')
            
            # 创建标签
            self.screen_share_label = ttk.Label(self.screen_share_frame)
            self.screen_share_label.grid(row=0, column=0, sticky='nsew')
            
            # 配置网格权重
            self.screen_share_frame.grid_columnconfigure(0, weight=1)
            self.screen_share_frame.grid_rowconfigure(0, weight=1)
        
        # 确保屏幕共享框架可见，视频网格隐藏
        self.screen_share_frame.grid(row=0, column=0, sticky='nsew')
        self.video_grid.grid_remove()
        
        print("Screen share started successfully")
        return True
    
    def update_screen_share(self, image):
        """更新屏幕共享内容"""
        if not self.is_screen_sharing or not self.screen_share_frame:
            print("Cannot update screen share: not active or no frame")
            return
            
        try:
            # 获取容器的实际尺寸
            container_width = self.container.winfo_width() or self.container_width
            container_height = self.container.winfo_height() or self.container_height
            
            # 计算最佳显示尺寸
            w, h = image.size
            aspect_ratio = w / h
            
            if container_width / container_height > aspect_ratio:
                new_height = container_height
                new_width = int(container_height * aspect_ratio)
            else:
                new_width = container_width
                new_height = int(container_width / aspect_ratio)
            
            # 调整图像大小
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(resized_image)
            
            # 更新标签图像
            if self.screen_share_label:
                self.screen_share_label.configure(image=photo)
                self.screen_share_label.image = photo
            
            # 确保屏幕共享框架可见
            self.screen_share_frame.grid(row=0, column=0, sticky='nsew')
            self.video_grid.grid_remove()
            
        except Exception as e:
            print(f"Error updating screen share: {e}")
    
    def stop_screen_share(self, sharer_id):
        """停止屏幕共享"""
        print(f"Stopping screen share for {sharer_id}")
        if self.screen_sharer_id == sharer_id:
            self.is_screen_sharing = False
            self.screen_sharer_id = None
            
            # 清理屏幕共享资源
            if self.screen_share_frame:
                if self.screen_share_label:
                    self.screen_share_label.configure(image='')
                    self.screen_share_label.image = None
                self.screen_share_frame.grid_remove()
            
            # 恢复视频网格
            self.video_grid.grid(row=0, column=0, sticky='nsew')
            self.update_layout()
            print("Screen share stopped successfully")
            return True
            
        print("Cannot stop screen share: wrong sharer")
        return False
    
    def update_layout(self):
        """更新视频网格布局"""
        if self.is_screen_sharing:
            self.video_grid.grid_remove()
            if self.screen_share_frame:
                self.screen_share_frame.grid(row=0, column=0, sticky='nsew')
            return
            
        # 显示视频网格
        self.video_grid.grid(row=0, column=0, sticky='nsew')
        if self.screen_share_frame:
            self.screen_share_frame.grid_remove()
            
        # 获取活跃的视频
        active_videos = {pid: info for pid, info in self.video_frames.items() 
                       if info.get('active', False)}
        
        if not active_videos:
            return
            
        # 计算网格布局
        n = len(active_videos)
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        
        # 计算单个视频的尺寸
        grid_width = self.container.winfo_width() or self.container_width
        grid_height = self.container.winfo_height() or self.container_height
        
        cell_width = max(self.default_video_width, grid_width // cols)
        cell_height = max(self.default_video_height, grid_height // rows)
        
        # 配置网格
        for i in range(cols):
            self.video_grid.grid_columnconfigure(i, weight=1)
        for i in range(rows):
            self.video_grid.grid_rowconfigure(i, weight=1)
        
        # 放置视频框
        for idx, (pid, info) in enumerate(active_videos.items()):
            row = idx // cols
            col = idx % cols
            frame = info['frame']
            frame.configure(width=cell_width, height=cell_height)
            frame.grid(row=row, column=col, sticky='nsew', padx=2, pady=2)

    def _resize_image_for_layout(self, image):
        """调整图像大小以适应布局"""
        # 获取容器的实际大小
        grid_width = self.video_grid.winfo_width() or self.container_width
        grid_height = self.video_grid.winfo_height() or self.container_height
        
        # 计算活跃视频数量和网格布局
        active_count = sum(1 for info in self.video_frames.values() 
                         if info.get('active', False)) or 1
        cols = math.ceil(math.sqrt(active_count))
        rows = math.ceil(active_count / cols)
        
        # 计算单个视频的目标尺寸
        target_width = max(self.default_video_width, grid_width // cols)
        target_height = max(self.default_video_height, grid_height // rows)
        
        # 保持16:9的宽高比
        aspect_ratio = 16/9
        if target_width / target_height > aspect_ratio:
            target_width = int(target_height * aspect_ratio)
        else:
            target_height = int(target_width / aspect_ratio)
        
        return image.resize((target_width, target_height), Image.Resampling.LANCZOS)