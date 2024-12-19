import asyncio
from typing import Optional
import socketio
from protocol import Conference

class ConferenceClient:
    def __init__(self, server_url):
        self.sio = socketio.AsyncClient()
        # 视频通道
        self.video_sio = socketio.AsyncClient()
        # 屏幕共享通道
        self.screen_sio = socketio.AsyncClient()
        self.server_url = server_url
        self.conference: Optional[Conference] = None
        self.username = None
        self._join_future = None 
        
        @self.sio.event
        async def connect():
            print("Connected to server")
        
        @self.sio.event
        async def disconnect():
            print("Disconnected from server")
            self.conference = None

        @self.sio.on('conference_created') 
        async def on_conference_created(data):
            print(f"Received conference_created event: {data}")
            # 添加主动获取会议列表
            await self.sio.emit('get_conferences')
        @self.sio.on('conference_closed')
        async def on_conference_closed(data):
            if self.conference and data['conference_id'] == self.conference.id:
                print("Conference was closed by creator")
                self.conference = None
                if hasattr(self.master, 'on_conference_closed'):
                    await self.master.on_conference_closed()
        @self.sio.on('conference_joined')
        async def on_conference_joined(data):
            print(f"Joined conference: {data}")
            self.conference = Conference.from_dict(data)
            if self._join_future and not self._join_future.done():
                self._join_future.set_result(True)

        @self.sio.on('participant_joined')
        async def on_participant_joined(data):
            if self.conference and data['conference_id'] == self.conference.id:
                self.conference.participants[data['client_id']] = data['client_name']

        @self.sio.on('participant_left')
        async def on_participant_left(data):
            if self.conference and data['conference_id'] == self.conference.id:
                del self.conference.participants[data['client_id']]

        # 用于在get_conferences调用中等待服务器返回的future
        self._conference_list_future = None

        @self.sio.on('conference_list')
        async def on_conference_list(data):
            print(f"Received conference list data: {data}")  # 添加调试日志
            if self._conference_list_future and not self._conference_list_future.done():
                try:
                    self._conference_list_future.set_result(data)
                except Exception as e:
                    print(f"Error setting conference list result: {e}")

        @self.sio.on('conference_list_response')
        async def on_conference_list_response(data):
            print(f"Received conference list response: {data}")
            if self._conference_list_future and not self._conference_list_future.done():
                self._conference_list_future.set_result(data)

    async def connect(self):
        try:
            # 连接主通道
            await self.sio.connect(f"{self.server_url}")
            # 连接视频通道
            await self.video_sio.connect(f"{self.server_url}/video")
            # 连接屏幕共享通道
            await self.screen_sio.connect(f"{self.server_url}/screen")
        except Exception as e:
            print(f"Error connecting to server: {e}")

    async def disconnect(self):
        await self.sio.disconnect()

    async def create_conference(self, conf_name, username):
        await self.sio.emit('create_conference', {'name': conf_name, 'username': username})

    async def join_conference(self, conf_id, username):
        # 创建Future对象
        loop = asyncio.get_running_loop()
        self._join_future = loop.create_future()

        # 发送加入请求
        await self.sio.emit('join_conference', {'conference_id': conf_id, 'username': username})

        # 等待加入成功
        try:
            await asyncio.wait_for(self._join_future, timeout=5.0)
        finally:
            self._join_future = None

    async def leave_conference(self):
        await self.sio.emit('leave_conference', {'conference_id': self.conference.id})
        self.conference = None

    async def get_conferences(self):
        if not self.sio.connected:
            print("Not connected to server")
            return []

        loop = asyncio.get_running_loop()
        self._conference_list_future = loop.create_future()

        try:
            print("Sending get_conferences request...")
            await self.sio.emit('get_conferences')
            print("Waiting for response...")
            data = await asyncio.wait_for(self._conference_list_future, timeout=5)
            print(f"Got conference list: {data}")
            return [Conference.from_dict(conf_data) for conf_data in data['conferences']]
        except asyncio.TimeoutError:
            print("Timeout waiting for conference list")
            return []
        except Exception as e:
            print(f"Error in get_conferences: {e}")
            return []
        finally:
            self._conference_list_future = None
            
    async def send_message(self, message):
       if self.conference:
           await self.sio.emit('send_message', {'conference_id': self.conference.id, 'message': message})

    async def send_audio(self, audio_data):
        if self.conference:
            await self.sio.emit('audio', {
                'conference_id': self.conference.id,
                'data': audio_data,
                'sender_id': self.sio.sid
            })
        
    async def send_video(self, video_data):
        if self.conference:
            await self.video_sio.emit('video', {
                'conference_id': self.conference.id,
                'data': video_data['data'],  # video_data已经是字典格式
                'sender_id': self.sio.sid
            })
        
    async def send_screen_share(self, screen_data):
        if self.conference:
            # screen_data 应该和 video_data 保持一致的格式
            if isinstance(screen_data, dict):
                await self.screen_sio.emit('screen_share', {
                    'conference_id': self.conference.id,
                    'data': screen_data['data'],
                    'sender_id': self.sio.sid
                })
            else:
                # 为了向后兼容，如果收到的是原始数据，自动转换为字典格式
                await self.screen_sio.emit('screen_share', {
                    'conference_id': self.conference.id,
                    'data': screen_data,
                    'sender_id': self.sio.sid
                })

    async def close_conference(self):
        """关闭会议（仅创建者可用）"""
        if self.conference:
            await self.sio.emit('close_conference', {
                'conference_id': self.conference.id
            })