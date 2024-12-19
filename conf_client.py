import asyncio
from typing import Optional
import socketio
import uuid
from protocol import Conference

class ConferenceClient:
    def __init__(self, server_url):
        # 创建socket客户端实例
        self.sio = socketio.AsyncClient()
        self.video_sio = socketio.AsyncClient()
        self.screen_sio = socketio.AsyncClient()
        
        # 基础属性
        self.server_url = server_url
        self.conference: Optional[Conference] = None
        self.username = None
        self._join_future = None
        self._conference_list_future = None
        
        # 生成唯一用户ID
        self.user_id = str(uuid.uuid4())
        
        # 设置主通道事件处理器
        @self.sio.event
        async def connect():
            print("Connected to main channel")
            await self.sio.emit('register_connection', {'user_id': self.user_id})
        
        @self.sio.event
        async def disconnect():
            print("Disconnected from main channel")
            self.conference = None

        @self.video_sio.event
        async def connect():
            print("Connected to video channel")
            await self.video_sio.emit('register_connection', {'user_id': self.user_id})

        @self.screen_sio.event
        async def connect():
            print("Connected to screen channel")
            await self.screen_sio.emit('register_connection', {'user_id': self.user_id})

        # 会议事件处理器
        @self.sio.on('conference_created')
        async def on_conference_created(data):
            print(f"Conference created: {data}")
            await self.get_conferences()

        @self.sio.on('conference_closed')
        async def on_conference_closed(data):
            if self.conference and data['conference_id'] == self.conference.id:
                print("Conference was closed by creator")
                self.conference = None
                if hasattr(self, 'master') and hasattr(self.master, 'on_conference_closed'):
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
                self.conference.participants[data['user_id']] = data['client_name']
                if hasattr(self, 'master') and hasattr(self.master, 'update_participant_list'):
                    self.master.update_participant_list()

        @self.sio.on('participant_left')
        async def on_participant_left(data):
            if self.conference and data['conference_id'] == self.conference.id:
                if data['user_id'] in self.conference.participants:
                    del self.conference.participants[data['user_id']]
                if hasattr(self, 'master') and hasattr(self.master, 'update_participant_list'):
                    self.master.update_participant_list()

        @self.sio.on('conference_list')
        async def on_conference_list(data):
            if self._conference_list_future and not self._conference_list_future.done():
                self._conference_list_future.set_result(data)

        @self.sio.on('conference_list_response')
        async def on_conference_list_response(data):
            if self._conference_list_future and not self._conference_list_future.done():
                self._conference_list_future.set_result(data)

        @self.video_sio.event
        async def connect():
            print("Connected to video channel")
            await self.video_sio.emit('register_connection', {'user_id': self.user_id})
            
        @self.video_sio.event
        async def disconnect():
            print("Disconnected from video channel")
    
        @self.video_sio.on('video')
        async def on_video(data):
            if hasattr(self, 'master') and hasattr(self.master, 'on_video_received'):
                await self.master.on_video_received(data)
    
        # 屏幕共享通道事件处理器
        @self.screen_sio.event
        async def connect():
            print("Connected to screen channel")
            await self.screen_sio.emit('register_connection', {'user_id': self.user_id})
            
        @self.screen_sio.event
        async def disconnect():
            print("Disconnected from screen channel")
    
        @self.screen_sio.on('screen_share')
        async def on_screen_share(data):
            if hasattr(self, 'master') and hasattr(self.master, 'on_screen_share_received'):
                await self.master.on_screen_share_received(data)
    
        # 音频事件处理器 (在主通道上)
        @self.sio.on('audio')
        async def on_audio(data):
            if hasattr(self, 'master') and hasattr(self.master, 'on_audio_received'):
                await self.master.on_audio_received(data)
                
    async def connect(self):
        """连接到所有通道"""
        try:
            await self.sio.connect(f"{self.server_url}")
            await self.video_sio.connect(f"{self.server_url}", socketio_path='video/socket.io')
            await self.screen_sio.connect(f"{self.server_url}", socketio_path='screen/socket.io')
        except Exception as e:
            print(f"Error connecting to server: {e}")

    async def disconnect(self):
        """断开所有连接"""
        try:
            await self.sio.disconnect()
            await self.video_sio.disconnect()
            await self.screen_sio.disconnect()
        except Exception as e:
            print(f"Error disconnecting: {e}")

    async def create_conference(self, conf_name, username):
        """创建会议"""
        await self.sio.emit('create_conference', {
            'name': conf_name,
            'username': username,
            'user_id': self.user_id
        })

    async def join_conference(self, conf_id, username):
        """加入会议"""
        loop = asyncio.get_running_loop()
        self._join_future = loop.create_future()

        await self.sio.emit('join_conference', {
            'conference_id': conf_id,
            'username': username,
            'user_id': self.user_id
        })

        try:
            await asyncio.wait_for(self._join_future, timeout=5.0)
        finally:
            self._join_future = None

    async def leave_conference(self):
        """离开会议"""
        if self.conference:
            await self.sio.emit('leave_conference', {
                'conference_id': self.conference.id,
                'user_id': self.user_id
            })
            self.conference = None

    async def close_conference(self):
        """关闭会议（仅创建者可用）"""
        if self.conference:
            await self.sio.emit('close_conference', {
                'conference_id': self.conference.id,
                'user_id': self.user_id
            })

    async def get_conferences(self):
        """获取会议列表"""
        if not self.sio.connected:
            print("Not connected to server")
            return []

        loop = asyncio.get_running_loop()
        self._conference_list_future = loop.create_future()

        try:
            await self.sio.emit('get_conferences')
            data = await asyncio.wait_for(self._conference_list_future, timeout=5)
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
        """发送聊天消息"""
        if self.conference:
            await self.sio.emit('send_message', {
                'conference_id': self.conference.id,
                'message': message,
                'user_id': self.user_id
            })

    async def send_video(self, video_data):
        """发送视频数据"""
        if self.conference:
            await self.video_sio.emit('video', {
                'conference_id': self.conference.id,
                'data': video_data['data'] if isinstance(video_data, dict) else video_data,
                'user_id': self.user_id
            })

    async def send_screen_share(self, screen_data):
        """发送屏幕共享数据"""
        if self.conference:
            await self.screen_sio.emit('screen_share', {
                'conference_id': self.conference.id,
                'data': screen_data['data'] if isinstance(screen_data, dict) else screen_data,
                'user_id': self.user_id
            })

    async def send_audio(self, audio_data):
        """发送音频数据"""
        if self.conference:
            await self.sio.emit('audio', {
                'conference_id': self.conference.id,
                'data': audio_data['data'] if isinstance(audio_data, dict) else audio_data,
                'user_id': self.user_id
            })