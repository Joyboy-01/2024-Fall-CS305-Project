import asyncio
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk
from av import VideoFrame
from util import *
from conf_client import ConferenceClient

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
        self.master.geometry("800x650")

        # 初始化状态变量
        self.is_sending_audio = False
        self.is_sending_video = False
        self.is_sharing_screen = False
        # 添加任务队列和控制变量
        self.video_queue = asyncio.Queue(maxsize=3)  # 限制队列大小
        self.screen_queue = asyncio.Queue(maxsize=2)
        self.audio_queue = asyncio.Queue(maxsize=5)
        self.video_frames = {}

        self.start_processing_tasks()
        # 设置事件监听
        self.setup_event_handlers()

        # 创建布局
        self.create_layout()

        # 更新参与者列表
        self.update_participant_list()
    def start_processing_tasks(self):
        # 启动异步处理任务
        self.master.loop.create_task(self.process_video_queue())
        self.master.loop.create_task(self.process_screen_queue())
        self.master.loop.create_task(self.process_audio_queue())
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
    
    def on_participant_joined(self, data):
        if data['conference_id'] == self.conference.id:  # 确保是当前会议
            print(f"New participant joined: {data['client_name']}")
            # 更新会议对象中的参与者信息
            self.conference.participants[data['client_id']] = data['client_name']
            # 更新GUI
            self.update_participant_list()

    def on_participant_left(self, data):
        if data['conference_id'] == self.conference.id:
            print(f"Participant left: {data['client_name']}")
            if data['client_id'] in self.conference.participants:
                del self.conference.participants[data['client_id']]
            self.update_participant_list()

    def on_message_received(self, data):
        sender = data['sender']
        message = data['message']
        self.insert_message(f"{sender}: {message}")

    def on_video_frame(self, participant_id, video_frame: VideoFrame):
        image = video_frame.to_image()
        photo = ImageTk.PhotoImage(image)
        if participant_id not in self.video_frames:
            label = tk.Label(self.video_panel)
            label.pack()
            self.video_frames[participant_id] = label
        self.video_frames[participant_id].config(image=photo)
        self.video_frames[participant_id].image = photo

    def update_participant_list(self):
        self.participant_list.delete(0, tk.END)
        for participant_id, name in self.conference.participants.items():
            self.participant_list.insert(tk.END, name)

    def insert_message(self, message):
        self.chat_text.configure(state=tk.NORMAL)
        self.chat_text.insert(tk.END, message + "\n")
        self.chat_text.configure(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def send_message(self):
        message = self.chat_input.get()
        if message:
            # 假设 client.send_message 是异步的
            self.master.loop.create_task(self._send_message_async(message))

    async def _send_message_async(self, message):
        await self.client.send_message(message)
        self.chat_input.delete(0, tk.END)

    def leave_conference_clicked(self):
        self.master.loop.create_task(self.leave_conference())

    async def leave_conference(self):
        await self.client.leave_conference()
        self.master.switch_frame(ConferenceListFrame)

    def toggle_mic(self):
        if self.mic_var.get():
            self.master.loop.create_task(self.start_audio())
        else:
            self.stop_audio()

    def toggle_camera(self):
        if self.camera_var.get():
            self.master.loop.create_task(self.start_video())
        else:
            self.stop_video()

    def toggle_screen_share(self):
        if self.screen_share_var.get():
            self.master.loop.create_task(self.start_screen_share())
        else:
            self.stop_screen_share()
    
    def toggle_mic(self):
        print("Toggle microphone:", self.mic_var.get())  # 添加日志
        if self.mic_var.get():
            self.master.loop.create_task(self.start_audio())
        else:
            self.stop_audio()

    def toggle_camera(self):
        print("Toggle camera:", self.camera_var.get())  # 添加日志
        if self.camera_var.get():
            self.master.loop.create_task(self.start_video())
        else:
            self.stop_video()

    def toggle_screen_share(self):
        print("Toggle screen share:", self.screen_share_var.get())  # 添加日志
        if self.screen_share_var.get():
            self.master.loop.create_task(self.start_screen_share())
        else:
            self.stop_screen_share()

    # 完善音视频和屏幕共享的方法
    async def start_video(self):
        print("Starting video stream...")
        self.is_sending_video = True
        while self.is_sending_video:
            try:
                frame = capture_camera()
                if frame and not self.video_queue.full():
                    compressed_frame = compress_image(frame)
                    await self.video_queue.put(compressed_frame)
                    # 更新本地预览
                    photo = ImageTk.PhotoImage(frame)
                    if 'local' not in self.video_frames:
                        label = tk.Label(self.video_panel)
                        label.pack(side=tk.LEFT)
                        self.video_frames['local'] = label
                    self.video_frames['local'].config(image=photo)
                    self.video_frames['local'].image = photo
            except asyncio.QueueFull:
                # 队列满了，跳过这一帧
                pass
            except Exception as e:
                print(f"Error in video streaming: {e}")
            await asyncio.sleep(0.033)  # 控制捕获帧率

    async def start_screen_share(self):
        print("Starting screen share...")
        self.is_sharing_screen = True
        while self.is_sharing_screen:
            try:
                screen = capture_screen()
                if screen and not self.screen_queue.full():
                    compressed_screen = compress_image(screen)
                    await self.screen_queue.put(compressed_screen)
            except asyncio.QueueFull:
                pass
            except Exception as e:
                print(f"Error in screen sharing: {e}")
            await asyncio.sleep(0.05)

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

    # 添加接收处理方法
    async def on_video_received(self, data):
        try:
            if 'data' in data:
                frame = decompress_image(data['data'])
                participant_id = data.get('participant_id', 'remote')
                # 在GUI中显示视频
                photo = ImageTk.PhotoImage(frame)
                if participant_id not in self.video_frames:
                    label = tk.Label(self.video_panel)
                    label.pack(side=tk.LEFT)
                    self.video_frames[participant_id] = label
                self.video_frames[participant_id].config(image=photo)
                self.video_frames[participant_id].image = photo
        except Exception as e:
            print(f"Error displaying received video: {e}")

    async def on_screen_share_received(self, data):
        try:
            if 'data' in data:
                screen = decompress_image(data['data'])
                # 在GUI中显示共享屏幕
                photo = ImageTk.PhotoImage(screen)
                if 'screen' not in self.video_frames:
                    label = tk.Label(self.video_panel)
                    label.pack(fill=tk.BOTH, expand=True)
                    self.video_frames['screen'] = label
                self.video_frames['screen'].config(image=photo)
                self.video_frames['screen'].image = photo
        except Exception as e:
            print(f"Error displaying received screen share: {e}")

    async def on_audio_received(self, data):
        try:
            if 'data' in data:
                streamout.write(data['data'])  # 使用 util.py 中定义的 streamout
        except Exception as e:
            print(f"Error playing received audio: {e}")

    def stop_audio(self):
        print("Stopping audio stream...")
        self.is_sending_audio = False

    def stop_video(self):
        print("Stopping video stream...")
        self.is_sending_video = False
        # 移除本地视频预览
        if 'local' in self.video_frames:
            self.video_frames['local'].destroy()  # 使用destroy而不是pack_forget
            del self.video_frames['local']
        # 重置视频面板
        self.reset_video_panel()

    def stop_screen_share(self):
        print("Stopping screen share...")
        self.is_sharing_screen = False
        # 移除屏幕共享显示
        if 'screen' in self.video_frames:
            self.video_frames['screen'].destroy()  # 使用destroy而不是pack_forget
            del self.video_frames['screen']
        # 重置视频面板
        self.reset_video_panel()

    def reset_video_panel(self):
        # 清理视频面板
        for widget in self.video_panel.winfo_children():
            widget.destroy()
        # 可以添加默认的占位图或文字
        default_label = ttk.Label(self.video_panel, text="等待视频连接...")
        default_label.pack(expand=True)

    async def process_video_queue(self):
        while True:
            try:
                frame = await self.video_queue.get()
                if frame is not None:
                    await self.client.send_video(frame)
                await asyncio.sleep(0.033)  # 约30fps
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
                await asyncio.sleep(0.05)  # 约20fps
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

