import asyncio
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk,ImageDraw
from av import VideoFrame
from util import *
from conf_client import ConferenceClient
from VideoManager import VideoGridManager
from time import time
class LoginFrame(ttk.Frame):
    pass

class ConferenceListFrame(ttk.Frame):
    pass

class ConferenceFrame(ttk.Frame):
    pass

def create_empty_frame():
        """创建空的视频框架"""
        # 创建一个灰色背景的图像
        img = Image.new('RGB', (320, 240), color='gray')
        # 在图像上添加文本
        draw = ImageDraw.Draw(img)
        draw.text((160, 120), "无视频", fill='white', anchor='mm')
        return img
class ConferenceGUI(tk.Tk):
    def __init__(self, server_url, loop):
        super().__init__()
        self.title("视频会议")
        self.geometry("800x600")
        self.resizable(width=False, height=False)

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
        self.current_frame.pack(fill=tk.BOTH, expand=True)

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

class LoginFrame(ttk.Frame):
    def __init__(self, master, client):
        super().__init__(master)
        self.client = client

        self.master.title("登录")
        self.master.geometry("300x150")

        ttk.Label(self, text="用户名:").pack(pady=10)
        self.username_entry = ttk.Entry(self)
        self.username_entry.pack()

        login_button = ttk.Button(self, text="登录", command=self.login_clicked)
        login_button.pack(pady=20)

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
        self.master.title("会议列表")
        self.master.geometry("400x300")

        self.conference_list = tk.Listbox(self)
        self.conference_list.pack(fill=tk.BOTH, expand=True)
        self.conference_list.bind('<Double-Button-1>', self.join_conference)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X)

        create_button = ttk.Button(button_frame, text="创建会议", command=self.create_conference)
        create_button.pack(side=tk.LEFT, padx=5)

        refresh_button = ttk.Button(button_frame, text="刷新列表", command=self.refresh_conferences)
        refresh_button.pack(side=tk.LEFT)

        # self.client.sio.on('conference_created', self.on_conference_created)
        # self.client.sio.on('conference_list', self.on_conference_list)

        self.master.loop.create_task(self.refresh_conferences_async())
    def on_conference_created(self, data):
        self.master.loop.create_task(self.refresh_conferences_async())

    def on_conference_list(self, data):
        self.master.loop.create_task(self.refresh_conferences_async())

    async def refresh_conferences_async(self):
        print("Refreshing conference list...")
        if not self.client.sio.connected:
            print("Client is not connected to the server during refresh")
            return
        try:
            self.conference_list.delete(0, tk.END)
            conferences = await self.client.get_conferences()
            print(f"Conferences retrieved: {[conf.name for conf in conferences]}")
            for conference in conferences:
                self.conference_list.insert(tk.END, conference.name)
        except Exception as e:
            print(f"Error refreshing conferences: {e}")


    def refresh_conferences(self):
        # 如果不想使用asyncio，这里也可以直接refresh，但假设get_conferences是异步必须异步调用
        self.master.loop.create_task(self.refresh_conferences_async())

    def create_conference(self):
        print("Creating conference...")
        dialog = CreateConferenceDialog(self.master, self.client)
        self.master.wait_window(dialog)
        if dialog.result:
            print(f"Conference name entered: {dialog.result}")
            self.master.loop.create_task(self._create_conference(dialog.result, self.client.username))

    async def _create_conference(self, conf_name, username):
        print(f"Attempting to create conference: {conf_name} by {username}")
        try:
            await self.client.create_conference(conf_name, username)
            print("Conference creation request sent successfully")
            await self.refresh_conferences_async()
        except Exception as e:
            print(f"Error in _create_conference: {e}")

    def join_conference(self, event):
        self.master.loop.create_task(self._join_selected_conference())

    async def _join_selected_conference(self):
        selected_index = self.conference_list.curselection()
        if selected_index:
            try:
                conference_name = self.conference_list.get(selected_index)
                conferences = await self.client.get_conferences()
                conference = next(conf for conf in conferences if conf.name == conference_name)

                # 等待加入会议完成
                await self.client.join_conference(conference.id, self.client.username)

                # 现在可以安全地切换到会议界面
                self.master.switch_frame(ConferenceFrame)
            except asyncio.TimeoutError:
                print("Timeout waiting to join conference")
            except Exception as e:
                print(f"Error joining conference: {e}")


class CreateConferenceDialog(tk.Toplevel):
    def __init__(self, parent, client):
        super().__init__(parent)
        self.client = client
        self.result = None

        self.title("创建会议")
        self.geometry("300x100")
        self.resizable(width=False, height=False)

        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(frame, text="会议名称:").grid(row=0, column=0)
        self.conf_name_entry = ttk.Entry(frame)
        self.conf_name_entry.grid(row=0, column=1, padx=5)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)

        ok_button = ttk.Button(button_frame, text="创建", command=self.on_ok)
        ok_button.pack(side=tk.LEFT, padx=5)

        cancel_button = ttk.Button(button_frame, text="取消", command=self.on_cancel)
        cancel_button.pack(side=tk.LEFT)

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
        self.master.geometry("800x800")

        # 初始化状态变量
        self.is_sending_audio = False
        self.is_sending_video = False
        self.is_sharing_screen = False

        # 帧率控制
        self.last_frame_time = {}
        self.frame_interval = 1.0 / 30  # 30 FPS

        # 添加任务队列和控制变量
        self.video_queue = asyncio.Queue(maxsize=3)
        self.screen_queue = asyncio.Queue(maxsize=2)
        self.audio_queue = asyncio.Queue(maxsize=5)

        # 创建视频管理器
        self.video_manager = VideoGridManager(self)

        # 初始化界面和功能
        self.start_processing_tasks()
        self.setup_event_handlers()
        self.create_layout()
        self.update_participant_list()

    def setup_event_handlers(self):
        # 设置音频、视频和屏幕共享的事件处理
        self.client.sio.on('audio', self.on_audio_received)
        self.client.sio.on('video', self.on_video_received)
        self.client.sio.on('screen_share', self.on_screen_share_received)
        
        # 设置参与者和消息的事件处理
        self.client.sio.on('participant_joined', self.on_participant_joined)
        self.client.sio.on('participant_left', self.on_participant_left)
        self.client.sio.on('message_received', self.on_message_received)

    def create_layout(self):
        # 创建主框架
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建左右框架
        left_frame = self.create_left_frame(main_frame)
        right_frame = self.create_right_frame(main_frame)
        
        # 创建控制面板
        self.create_control_panel(right_frame)

    def create_left_frame(self, parent):
        left_frame = ttk.Frame(parent)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 视频画面显示区域
        self.video_panel = ttk.Frame(left_frame)
        self.video_panel.pack(fill=tk.BOTH, expand=True)
        
        return left_frame

    def create_right_frame(self, parent):
        right_frame = ttk.Frame(parent)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH)

        # 参与者列表
        self.create_participant_panel(right_frame)

        # 聊天区域
        self.create_chat_panel(right_frame)

        # 离开会议按钮
        leave_button = ttk.Button(right_frame, text="离开会议", 
                                command=self.leave_conference_clicked)
        leave_button.pack(fill=tk.X)

        return right_frame

    def create_participant_panel(self, parent):
        participant_frame = ttk.LabelFrame(parent, text="参与者")
        participant_frame.pack(fill=tk.BOTH, expand=True)

        self.participant_list = tk.Listbox(participant_frame)
        self.participant_list.pack(fill=tk.BOTH, expand=True)

    def create_chat_panel(self, parent):
        chat_frame = ttk.LabelFrame(parent, text="聊天")
        chat_frame.pack(fill=tk.BOTH, expand=True)

        # 聊天文本区域
        self.chat_text = tk.Text(chat_frame, state=tk.DISABLED)
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        # 聊天输入区域
        chat_input_frame = ttk.Frame(chat_frame)
        chat_input_frame.pack(fill=tk.X)

        self.chat_input = ttk.Entry(chat_input_frame)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)

        send_button = ttk.Button(chat_input_frame, text="发送", 
                                command=self.send_message)
        send_button.pack(side=tk.RIGHT)

    def create_control_panel(self, parent):
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)

        # 创建控制变量
        self.mic_var = tk.BooleanVar(value=False)
        self.camera_var = tk.BooleanVar(value=False)
        self.screen_share_var = tk.BooleanVar(value=False)

        # 创建控制按钮
        ttk.Checkbutton(control_frame, text="麦克风", 
                        variable=self.mic_var,
                        command=self.toggle_mic).pack(side=tk.LEFT, padx=5)

        ttk.Checkbutton(control_frame, text="摄像头", 
                        variable=self.camera_var,
                        command=self.toggle_camera).pack(side=tk.LEFT, padx=5)

        ttk.Checkbutton(control_frame, text="共享屏幕", 
                        variable=self.screen_share_var,
                        command=self.toggle_screen_share).pack(side=tk.LEFT, padx=5)

    def start_processing_tasks(self):
        # 启动异步处理任务
        self.master.loop.create_task(self.process_video_queue())
        self.master.loop.create_task(self.process_screen_queue())
        self.master.loop.create_task(self.process_audio_queue())

    # 事件处理方法
    def on_participant_joined(self, data):
        if data['conference_id'] == self.conference.id:
            print(f"New participant joined: {data['client_name']}")
            self.conference.participants[data['client_id']] = data['client_name']
            self.update_participant_list()

    def on_participant_left(self, data):
        if data['conference_id'] == self.conference.id:
            print(f"Participant left: {data['client_name']}")
            if data['client_id'] in self.conference.participants:
                del self.conference.participants[data['client_id']]
            self.video_manager.remove_video(data['client_id'])
            self.update_participant_list()

    def on_message_received(self, data):
        sender = data['sender']
        message = data['message']
        self.insert_message(f"{sender}: {message}")

    async def on_video_received(self, data):
        try:
            if 'data' in data:
                frame = decompress_image(data['data'])
                participant_id = data.get('participant_id', 'remote')
                
                # 帧率控制
                current_time = time.time()
                last_time = self.last_frame_time.get(participant_id, 0)
                if current_time - last_time >= self.frame_interval:
                    self.video_manager.update_video(participant_id, frame)
                    self.last_frame_time[participant_id] = current_time
        except Exception as e:
            print(f"Error displaying received video: {e}")

    async def on_screen_share_received(self, data):
        try:
            if 'data' in data:
                screen = decompress_image(data['data'])
                current_time = time.time()
                last_time = self.last_frame_time.get('screen', 0)
                if current_time - last_time >= self.frame_interval:
                    self.video_manager.update_screen_share(screen)
                    self.last_frame_time['screen'] = current_time
        except Exception as e:
            print(f"Error displaying received screen share: {e}")

    async def on_audio_received(self, data):
        try:
            if 'data' in data:
                streamout.write(data['data'])
        except Exception as e:
            print(f"Error playing received audio: {e}")

    # UI 更新方法
    def update_participant_list(self):
        self.participant_list.delete(0, tk.END)
        for participant_id, name in self.conference.participants.items():
            self.participant_list.insert(tk.END, name)

    def insert_message(self, message):
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.insert(tk.END, message + "\n")
        self.chat_text.configure(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    # 消息发送
    def send_message(self):
        message = self.chat_input.get()
        if message:
            self.master.loop.create_task(self._send_message_async(message))

    async def _send_message_async(self, message):
        await self.client.send_message(message)
        self.chat_input.delete(0, tk.END)

    # 音视频控制方法
    def toggle_mic(self):
        if self.mic_var.get():
            self.master.loop.create_task(self.start_audio())
        else:
            self.stop_audio()

    

    def toggle_camera(self):
        if self.camera_var.get():
            # 开启摄像头前先添加空面板
            self.video_manager.add_video('local', create_empty_frame())
            self.master.loop.create_task(self.start_video())
        else:
            self.stop_video()
            # 停止视频后显示空面板
            self.video_manager.update_video('local', create_empty_frame())


    def toggle_screen_share(self):
        if self.screen_share_var.get():
            self.master.loop.create_task(self.start_screen_share())
        else:
            self.stop_screen_share()

    # 音视频流处理
    async def start_video(self):
        print("Starting video stream...")
        self.is_sending_video = True
        while self.is_sending_video:
            try:
                frame = capture_camera()
                if frame and not self.video_queue.full():
                    # 确保图像大小合适
                    frame = frame.resize((320, 240), Image.LANCZOS)
                    compressed_frame = compress_image(frame)
                    await self.video_queue.put(compressed_frame)
                    # 更新本地预览
                    self.video_manager.update_video('local', frame)
            except asyncio.QueueFull:
                pass
            except Exception as e:
                print(f"Error in video streaming: {e}")
            await asyncio.sleep(self.frame_interval)

    async def start_screen_share(self):
        print("Starting screen share...")
        self.is_sharing_screen = True
        self.video_manager.start_screen_share()
        while self.is_sharing_screen:
            try:
                screen = capture_screen()
                if screen and not self.screen_queue.full():
                    compressed_screen = compress_image(screen)
                    await self.screen_queue.put(compressed_screen)
                    # 更新本地预览
                    self.video_manager.update_screen_share(screen)
            except asyncio.QueueFull:
                pass
            except Exception as e:
                print(f"Error in screen sharing: {e}")
            await asyncio.sleep(self.frame_interval)

    async def start_audio(self):
        print("Starting audio stream...")
        self.is_sending_audio = True
        while self.is_sending_audio:
            try:
                audio_data = capture_voice()
                if audio_data and not self.audio_queue.full():
                    await self.audio_queue.put(audio_data)
            except asyncio.QueueFull:
                pass
            except Exception as e:
                print(f"Error in audio streaming: {e}")
            await asyncio.sleep(0.02)

    def stop_audio(self):
        print("Stopping audio stream...")
        self.is_sending_audio = False

    def stop_video(self):
        print("Stopping video stream...")
        self.is_sending_video = False
        self.video_manager.remove_video('local')

    def stop_screen_share(self):
        print("Stopping screen share...")
        self.is_sharing_screen = False
        self.video_manager.stop_screen_share()

    # 队列处理
    async def process_video_queue(self):
        while True:
            try:
                frame = await self.video_queue.get()
                if frame is not None:
                    await self.client.send_video(frame)
                await asyncio.sleep(self.frame_interval)
            except Exception as e:
                print(f"Error processing video: {e}")
            finally:
                self.video_queue.task_done()
    
    async def process_screen_queue(self):
        while True:
            try:
                frame = await self.screen_queue.get()
                if frame is not None:
                    await self.client.send_screen_share(frame)
                await asyncio.sleep(self.frame_interval)
            except Exception as e:
                print(f"Error processing screen share: {e}")
            finally:
                self.screen_queue.task_done()
    
    async def process_audio_queue(self):
        while True:
            try:
                data = await self.audio_queue.get()
                if data is not None:
                    await self.client.send_audio(data)
                await asyncio.sleep(0.02)  # 50Hz
            except Exception as e:
                print(f"Error processing audio: {e}")
            finally:
                self.audio_queue.task_done()

    # 资源清理
    def cleanup(self):
        """清理所有资源"""
        self.stop_video()
        self.stop_screen_share()
        self.stop_audio()
        
        # 清理所有视频帧
        for participant_id in list(self.video_manager.video_frames.keys()):
            self.video_manager.remove_video(participant_id)
            
        # 清空队列
        while not self.video_queue.empty():
            try:
                self.video_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
                
        while not self.screen_queue.empty():
            try:
                self.screen_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

    # 会议控制相关方法
    def leave_conference_clicked(self):
        self.master.loop.create_task(self.leave_conference())

    async def leave_conference(self):
        """离开会议并清理资源"""
        # 执行清理
        self.cleanup()
        # 离开会议
        await self.client.leave_conference()
        # 切换回会议列表界面
        self.master.switch_frame(ConferenceListFrame)

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
