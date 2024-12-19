import asyncio
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk
from av import VideoFrame
from util import *
from conf_client import ConferenceClient
from VideoManager import VideoGridManager
from Controlbar import ControlBar
import time
class LoginFrame(ttk.Frame):
    pass

class ConferenceListFrame(ttk.Frame):
    pass

class ConferenceFrame(ttk.Frame):
    pass
class ConferenceGUI(tk.Tk):
    def __init__(self, server_url, loop):
        super().__init__()
        self.title("视频会议")
        self.minsize(800, 600)
        
        # 配置主窗口网格
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.server_url = server_url
        self.loop = loop
        self.client = ConferenceClient(server_url)
        self.current_frame = None
        
        self.switch_frame(LoginFrame)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 定期运行asyncio事件循环
        self._schedule_asyncio_poll()
        self._asyncio_poll_id = None

    def switch_frame(self, frame_class):
        new_frame = frame_class(self, self.client)
        if self.current_frame is not None:
            self.current_frame.destroy()
        self.current_frame = new_frame
        self.current_frame.grid(row=0, column=0, sticky='nsew')  # 使用grid而不是pack

    def _schedule_asyncio_poll(self):
        # print("Polling asyncio event loop...")
        self.loop.call_soon(self.loop.stop)
        self.loop.run_forever()
        self.after(10, self._schedule_asyncio_poll)

    def on_closing(self):
        # 取消定时的 asyncio 轮询
        if self._asyncio_poll_id is not None:
            self.after_cancel(self._asyncio_poll_id)

        # 创建一个任务来执行关闭操作
        self.loop.create_task(self.shutdown())

    async def shutdown(self):
        # 先退出当前会议
        if self.client.conference:
            await self.client.leave_conference()

        # 然后断开连接
        await self.client.disconnect()

        # 取消所有挂起的任务
        tasks = [task for task in asyncio.all_tasks(self.loop) if task is not asyncio.current_task(self.loop)]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # 停止事件循环并销毁GUI
        self.loop.stop()
        self.destroy()
    async def on_conference_closed(self):
        """当会议被创建者关闭时的处理"""
        message_box = tk.messagebox.showinfo(
            "会议已关闭",
            "会议已被创建者关闭"
        )
        self.switch_frame(ConferenceListFrame)
class LoginFrame(ttk.Frame):
    def __init__(self, master, client):
        super().__init__(master)
        self.client = client
        
        # 配置框架网格
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # 创建居中的登录面板
        login_frame = ttk.Frame(self)
        login_frame.grid(row=1, column=0)
        
        # 登录面板内的组件
        ttk.Label(login_frame, text="用户名:").grid(row=0, column=0, pady=10)
        
        self.username_entry = ttk.Entry(login_frame, width=30)
        self.username_entry.grid(row=1, column=0, pady=5)
        
        login_button = ttk.Button(login_frame, text="登录", command=self.login_clicked)
        login_button.grid(row=2, column=0, pady=20)

    def login_clicked(self):
        self.master.loop.create_task(self.login())
    
    async def login(self):
        username = self.username_entry.get()
        if username:
            self.client.username = username
            print("Connecting to server...")
            await self.client.connect()
            print("Switching to conference list frame")
            self.master.switch_frame(ConferenceListFrame)

class ConferenceListFrame(ttk.Frame):
    def __init__(self, master, client):
        super().__init__(master)
        self.client = client
        
        # 配置框架网格
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # 列表和滚动条
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=0, column=0, sticky='nsew')
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        self.conference_list = tk.Listbox(list_frame)
        self.conference_list.grid(row=0, column=0, sticky='nsew')
        self.conference_list.bind('<Double-Button-1>', self.join_conference)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.conference_list.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.conference_list.configure(yscrollcommand=scrollbar.set)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky='ew', pady=(10,0))
        button_frame.grid_columnconfigure(1, weight=1)
        
        create_button = ttk.Button(button_frame, text="创建会议", command=self.create_conference)
        create_button.grid(row=0, column=0, padx=5)
        
        refresh_button = ttk.Button(button_frame, text="刷新列表", command=self.refresh_conferences)
        refresh_button.grid(row=0, column=1, padx=5)
        
        self.master.loop.create_task(self.refresh_conferences_async())

    def create_conference(self):
        dialog = CreateConferenceDialog(self.master, self.client)
        self.master.wait_window(dialog)
        if dialog.result:
            self.master.loop.create_task(self._create_conference(dialog.result))

    async def _create_conference(self, conf_name):
        await self.client.create_conference(conf_name, self.client.username)
        await self.refresh_conferences_async()

    def join_conference(self, event):
        self.master.loop.create_task(self._join_selected_conference())

    async def _join_selected_conference(self):
        selected_index = self.conference_list.curselection()
        if selected_index:
            conference_name = self.conference_list.get(selected_index)
            conferences = await self.client.get_conferences()
            conference = next(conf for conf in conferences if conf.name == conference_name)
            await self.client.join_conference(conference.id, self.client.username)
            self.master.switch_frame(ConferenceFrame)

    async def refresh_conferences_async(self):
        conferences = await self.client.get_conferences()
        self.conference_list.delete(0, tk.END)
        for conference in conferences:
            self.conference_list.insert(tk.END, conference.name)

    def refresh_conferences(self):
        self.master.loop.create_task(self.refresh_conferences_async())


class CreateConferenceDialog(tk.Toplevel):
    def __init__(self, parent, client):
        super().__init__(parent)
        self.client = client
        self.result = None
        
        self.title("创建会议")
        self.minsize(300, 150)
        
        # 配置对话框网格
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')
        main_frame.grid_columnconfigure(0, weight=1)
        
        # 输入区域
        ttk.Label(main_frame, text="会议名称:").grid(row=0, column=0, pady=(0,5))
        self.conf_name_entry = ttk.Entry(main_frame)
        self.conf_name_entry.grid(row=1, column=0, pady=(0,10), sticky='ew')
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0)
        
        ok_button = ttk.Button(button_frame, text="创建", command=self.on_ok)
        ok_button.grid(row=0, column=0, padx=5)
        
        cancel_button = ttk.Button(button_frame, text="取消", command=self.on_cancel)
        cancel_button.grid(row=0, column=1, padx=5)

    def on_ok(self):
        self.result = self.conf_name_entry.get()
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()



class ConferenceFrame(ttk.Frame):
    def __init__(self, master, client):
        super().__init__(master)
        self.client = client
        self.conference = client.conference
        self.master.title(f"会议: {self.conference.name}")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # 初始化状态变量和其他设置...
        
        # 使用grid而不是pack
        self.grid(row=0, column=0, sticky="nsew")
        self.main_container = ttk.Frame(self)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        # 初始化状态变量
        self.is_sending_audio = False
        self.is_sending_video = False
        self.is_sharing_screen = False
        self.frame_interval = 1/20  # 30 FPS
        self.video_quality = 60
        self.is_creator = self.conference.creator_id == self.client.sio.sid
        print(f"Creator check: conference creator_id={self.conference.creator_id}, client sid={self.client.sio.sid}")  # 添加调试信息

        # 创建队列
        self.video_queue = asyncio.Queue(maxsize=3)
        self.screen_queue = asyncio.Queue(maxsize=2)
        self.audio_queue = asyncio.Queue(maxsize=5)

        self.video_manager = VideoGridManager(self)

        # 设置事件处理和创建布局
        self.setup_event_handlers()
        self.create_layout()
        self.update_participant_list()
        # 启动处理任务
        self.start_processing_tasks()
        
    def create_layout(self):
        # 创建主框架
        main_frame = ttk.Frame(self.main_container)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 配置行列权重
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=0)  # 控制栏
        main_frame.grid_columnconfigure(0, weight=3)  # 视频区域占更多空间
        main_frame.grid_columnconfigure(1, weight=1)  # 右侧区域
        
        # 创建左右框架
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        
        # 视频显示区域
        self.video_panel = self.video_manager.container
        self.video_panel.grid(in_=left_frame, row=0, column=0, sticky="nsew")
        
        # 右侧区域
        self.create_right_panel(right_frame)
        
        # 创建底部控制栏
        self.control_bar = ControlBar(
            main_frame,
            mic_callback=self.handle_mic_toggle,
            camera_callback=self.handle_camera_toggle,
            screen_callback=self.handle_screen_toggle
        )
        self.control_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

    def create_right_panel(self, parent):
        # 配置parent的网格权重
        parent.grid_rowconfigure(0, weight=0)  # 参与者列表
        parent.grid_rowconfigure(1, weight=1)  # 聊天区域
        parent.grid_rowconfigure(2, weight=0)  # 离开按钮
        parent.grid_columnconfigure(0, weight=1)
    
        # 创建参与者列表
        participant_frame = ttk.LabelFrame(parent, text="参与者")
        participant_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        participant_frame.grid_rowconfigure(0, weight=1)
        participant_frame.grid_columnconfigure(0, weight=1)
        
        self.participant_list = tk.Listbox(participant_frame, height=6)
        self.participant_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # 创建聊天区域
        chat_frame = ttk.LabelFrame(parent, text="聊天")
        chat_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        chat_frame.grid_rowconfigure(0, weight=1)
        chat_frame.grid_columnconfigure(0, weight=1)
        
        # 聊天显示区域
        self.chat_text = tk.Text(chat_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.chat_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(chat_frame, orient=tk.VERTICAL, command=self.chat_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=5)
        self.chat_text.configure(yscrollcommand=scrollbar.set)
        
        # 聊天输入区域
        input_frame = ttk.Frame(chat_frame)
        input_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_columnconfigure(1, weight=0)
        
        self.chat_input = ttk.Entry(input_frame)
        self.chat_input.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        
        send_button = ttk.Button(input_frame, text="发送", command=self.send_message)
        send_button.grid(row=0, column=1)

        control_button_frame = ttk.Frame(parent)
        control_button_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        control_button_frame.grid_columnconfigure(0, weight=1)
        control_button_frame.grid_columnconfigure(1, weight=1)
    
        # 离开会议按钮 - 使用grid而不是pack
        leave_button = ttk.Button(parent, text="离开会议", command=self.leave_conference_clicked)
        leave_button.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        if self.is_creator:
            close_button = ttk.Button(control_button_frame, text="关闭会议", 
                                    command=self.close_conference_clicked)
            close_button.grid(row=0, column=1, sticky="ew", padx=5)
    def setup_event_handlers(self):
        """设置事件处理"""
        self.client.sio.on('audio', self.on_audio_received)
        self.client.sio.on('video', self.on_video_received)
        self.client.sio.on('screen_share', self.on_screen_share_received)
        self.client.sio.on('participant_joined', self.on_participant_joined)
        self.client.sio.on('participant_left', self.on_participant_left)
        self.client.sio.on('message_received', self.on_message_received)

    def start_processing_tasks(self):
        """启动异步处理任务"""
        self.master.loop.create_task(self.process_video_queue())
        self.master.loop.create_task(self.process_screen_queue())
        self.master.loop.create_task(self.process_audio_queue())

    async def on_audio_received(self, data):
        """处理接收到的音频"""
        try:
            if 'data' in data and 'sender_id' in data:
                streamout.write(data['data'])
        except Exception as e:
            print(f"Error playing received audio: {e}")

    async def on_video_received(self, data):
        """处理接收到的视频"""
        try:
            if 'data' in data and 'sender_id' in data:
                sender_id = data['sender_id']
                print(f"Received video from {sender_id}")
                
                # 使用视频通道的 socket ID 进行比较
                if sender_id == self.client.sio.sid or sender_id==self.client.video_sio.sid or sender_id==self.client.screen_sio.sid:
                    print("Skipping own video")
                    return
                    
                frame = decompress_image(data['data'])
                # 更新视频显示
                self.video_manager.update_video(sender_id, frame)
        except Exception as e:
            print(f"Error displaying received video: {e}")

    async def on_screen_share_received(self, data):
        """处理接收到的屏幕共享"""
        try:
            if 'data' in data and 'sender_id' in data:
                sender_id = data['sender_id']
                print(f"Received screen share from {sender_id}")
                # 不处理自己发送的屏幕共享
                if sender_id == self.client.sio.sid or sender_id==self.client.video_sio.sid or sender_id==self.client.screen_sio.sid:
                    print("Skipping own video")
                    return

                screen = decompress_image(data['data'])
                # 启动屏幕共享显示
                if not self.video_manager.is_screen_sharing:
                    self.video_manager.start_screen_share(sender_id)
                # 更新屏幕共享内容
                self.video_manager.update_screen_share(screen)
        except Exception as e:
            print(f"Error displaying received screen share: {e}")

    def on_participant_joined(self, data):
        """处理参与者加入事件"""
        if data['conference_id'] == self.conference.id:
            print(f"New participant joined: {data['client_name']}")
            self.conference.participants[data['client_id']] = data['client_name']
            self.update_participant_list()

    def on_participant_left(self, data):
        """处理参与者离开事件"""
        if data['conference_id'] == self.conference.id:
            print(f"Participant left: {data['client_name']}")
            if data['client_id'] in self.conference.participants:
                del self.conference.participants[data['client_id']]
            self.video_manager.remove_video(data['client_id'])
            self.update_participant_list()

    def close_conference_clicked(self):
        """处理关闭会议按钮点击"""
        self.master.loop.create_task(self.close_conference())

    async def close_conference(self):
        """关闭会议"""
        if self.is_creator:
            await self.client.close_conference()
            self.cleanup()
            self.master.switch_frame(ConferenceListFrame)


    def on_message_received(self, data):
        """处理接收到的消息"""
        sender = data['sender']
        message = data['message']
        self.insert_message(f"{sender}: {message}")

    # UI Updates
    def update_participant_list(self):
        """更新参与者列表"""
        self.participant_list.delete(0, tk.END)
        for participant_id, name in sorted(self.conference.participants.items()):
            display_name = f"{name} (你)" if participant_id == self.client.sio.sid else name
            self.participant_list.insert(tk.END, display_name)

    def insert_message(self, message):
        """插入新消息到聊天区域"""
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.insert(tk.END, message + "\n")
        self.chat_text.configure(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    # Message Handling
    def send_message(self):
        """发送消息"""
        message = self.chat_input.get()
        if message:
            self.master.loop.create_task(self._send_message_async(message))

    async def _send_message_async(self, message):
        """异步发送消息"""
        await self.client.send_message(message)
        self.chat_input.delete(0, tk.END)

    # Control Bar Callbacks
    def handle_mic_toggle(self, should_enable):
        try:
            if should_enable:
                print("Starting audio...")  # 添加调试信息
                self.master.loop.create_task(self.start_audio())
                self.is_sending_audio = True
            else:
                print("Stopping audio...")  # 添加调试信息
                self.stop_audio()
                self.is_sending_audio = False
            return True
        except Exception as e:
            print(f"Error toggling mic: {e}")
            return False

    def handle_camera_toggle(self, should_enable):
        """处理摄像头开关"""
        try:
            if should_enable:
                self.master.loop.create_task(self.start_video())
                self.is_sending_video = True
                self.video_manager.set_video_active('local', True)
            else:
                self.stop_video()
                self.is_sending_video = False
                self.video_manager.set_video_active('local', False)
            return True
        except Exception as e:
            print(f"Error toggling camera: {e}")
            return False

    def handle_screen_toggle(self, should_enable):
        """处理屏幕共享开关"""
        try:
            if should_enable:
                # 检查是否有人在共享屏幕
                for participant in self.conference.participants.values():
                    if isinstance(participant, dict) and participant.get('is_sharing_screen'):
                        print("Another user is already sharing their screen")
                        return False

                self.master.loop.create_task(self.start_screen_share())
                self.is_sharing_screen = True
                success = self.video_manager.start_screen_share('local')
                return success
            else:
                self.stop_screen_share()
                self.is_sharing_screen = False
                success = self.video_manager.stop_screen_share('local')
                return success
        except Exception as e:
            print(f"Error toggling screen share: {e}")
            return False
    
    async def start_audio(self):
        """开始音频流"""
        print("Starting audio stream...")
        self.is_sending_audio = True
        while self.is_sending_audio:
            try:
                audio_data = capture_voice()
                if audio_data and not self.audio_queue.full():
                    await self.audio_queue.put(audio_data)
                await asyncio.sleep(0.02)
            except asyncio.QueueFull:
                pass
            except Exception as e:
                print(f"Error in audio streaming: {e}")
                self.is_sending_audio = False   

    async def start_video(self):
        """优化后的视频流"""
        print("Starting video stream...")
        self.is_sending_video = True
        last_frame_time = 0
        
        while self.is_sending_video:
            try:
                current_time = time.time()
                if current_time - last_frame_time < self.frame_interval:
                    await asyncio.sleep(0.001)
                    continue
                    
                frame = capture_camera()
                if frame and not self.video_queue.full():
                    # 压缩质量降低以减少数据量
                    compressed_frame = compress_image(frame, quality=self.video_quality)
                    await self.video_queue.put({
                        'data': compressed_frame,
                        'participant_id': self.client.sio.sid
                    })
                    self.video_manager.update_video('local', frame)
                    last_frame_time = current_time
                    
                await asyncio.sleep(0.001)
            except Exception as e:
                print(f"Error in video streaming: {e}")

    async def start_screen_share(self):
        """开始屏幕共享"""
        print("Starting screen share...")
        self.is_sharing_screen = True
        while self.is_sharing_screen:
            try:
                screen = capture_screen()
                if screen and not self.screen_queue.full():
                    compressed_screen = compress_image(screen, quality=70)  # 降低一点质量以减少数据量
                    screen_data = {
                        'data': compressed_screen,
                        'participant_id': self.client.sio.sid
                    }
                    await self.screen_queue.put(screen_data)
                    # 更新本地预览
                    self.video_manager.update_screen_share(screen)
                await asyncio.sleep(self.frame_interval)
            except Exception as e:
                print(f"Error in screen sharing: {e}")
                break


    def stop_audio(self):
        """停止音频流"""
        print("Stopping audio stream...")
        self.is_sending_audio = False

    def stop_video(self):
        """停止视频流"""
        print("正在停止视频流...")
        self.is_sending_video = False

        try:
            # 确保视频被正确停止并清理
            if hasattr(self, 'video_manager'):
                # 停止本地视频显示
                self.video_manager.set_video_active('local', False)
                self.video_manager.remove_video('local')

            # 清空视频队列
            while not self.video_queue.empty():
                try:
                    self.video_queue.get_nowait()
                    self.video_queue.task_done()
                except asyncio.QueueEmpty:
                    break
        except Exception as e:
            print(f"停止视频时出错: {e}")

    def stop_screen_share(self):
        """停止屏幕共享"""
        print("正在停止屏幕共享...")
        self.is_sharing_screen = False
        
        try:
            # 确保屏幕共享被正确停止并清理
            if hasattr(self, 'video_manager'):
                # 停止屏幕共享并更新UI
                self.video_manager.stop_screen_share('local')
                
                # 强制更新界面
                self.video_manager.container.update_idletasks()
            
            # 清空屏幕共享队列
            while not self.screen_queue.empty():
                try:
                    self.screen_queue.get_nowait()
                    self.screen_queue.task_done()
                except asyncio.QueueEmpty:
                    break
        except Exception as e:
            print(f"停止屏幕共享时出错: {e}")

    # Queue Processing
    async def process_video_queue(self):
        """处理视频队列"""
        while True:
            try:
                video_data = await self.video_queue.get()
                if video_data is not None:
                    await self.client.send_video(video_data)
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Error processing video: {e}")
            finally:
                self.video_queue.task_done()

    async def process_screen_queue(self):
        """处理屏幕共享队列"""
        while True:
            try:
                screen_data = await self.screen_queue.get()
                if screen_data is not None:
                    print(f"Sending screen share, queue size: {self.screen_queue.qsize()}")
                    await self.client.send_screen_share(screen_data)
                await asyncio.sleep(0.05)
            except Exception as e:
                print(f"Error processing screen share: {e}")
            finally:
                self.screen_queue.task_done()

    async def process_audio_queue(self):
        """处理音频队列"""
        while True:
            try:
                data = await self.audio_queue.get()
                if data is not None:
                    await self.client.send_audio(data)
                await asyncio.sleep(0.02)
            except Exception as e:
                print(f"Error processing audio: {e}")
            finally:
                self.audio_queue.task_done()

    # Conference Control
    def leave_conference_clicked(self):
        """处理离开会议按钮点击"""
        self.master.loop.create_task(self.leave_conference())

    async def leave_conference(self):
        """离开会议"""
        self.cleanup()
        await self.client.leave_conference()
        self.master.switch_frame(ConferenceListFrame)

    def cleanup(self):
        """清理所有资源"""
        try:
            # 停止所有媒体流
            self.stop_video()
            self.stop_screen_share()
            self.stop_audio()

            # 清理所有视频帧
            if hasattr(self, 'video_manager'):
                # 先停止屏幕共享
                if self.video_manager.is_screen_sharing:
                    self.video_manager.stop_screen_share('local')

                # 清理所有视频帧
                for participant_id in list(self.video_manager.video_frames.keys()):
                    self.video_manager.remove_video(participant_id)

            # 清空所有队列
            for queue in [self.video_queue, self.screen_queue, self.audio_queue]:
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        pass
        except Exception as e:
            print(f"清理资源时出错: {e}")
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    gui = ConferenceGUI(server_url="http://127.0.0.1:8888", loop=loop)
    try:
        gui.mainloop()
    finally:
        # 主循环结束后取消所有未完成任务
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()