import asyncio
from typing import Optional
import socketio
import uuid
from protocol import Conference
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCIceServer, RTCConfiguration
from aiortc.mediastreams import MediaStreamTrack
from util import *
from typing import Dict, Optional
import pickle
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
        self.conference_frame = None
        # 生成唯一用户ID
        self.user_id = str(uuid.uuid4())

        # P2P相关属性定义：
        self.peer_connection = None
        self.p2p_channels: Dict[str, Optional[RTCDataChannel]] = {
            'message_channel': None,
            'audio_channel': None,
            'video_channel': None,
            'screen_channel': None
        }
        self.peer_id = None
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



        @self.sio.on('p2p_offer')
        async def on_p2p_offer(data):
            source_sid = data['source_sid']
            offer = data['offer']
            conf_id = data['conference_id']
            await self.handle_p2p_offer(source_sid, offer, conf_id)

        @self.sio.on('p2p_answer')
        async def on_p2p_answer(data):
            answer = data['answer']
            await self.handle_p2p_answer(answer)

        # @self.sio.on('p2p_ice_candidate')
        # async def on_p2p_ice_candidate(data):
        #     candidate = data['candidate']
        #     await self.handle_ice_candidate(candidate)

        @self.sio.on("ice_candidate")
        async def on_ice_candidate(data):
            candidate = data["candidate"]
            await self.peer_connection.addIceCandidate(candidate)
            print(f"Added ICE candidate: {candidate}")
        @self.sio.on('mode_change')
        async def on_mode_change(data):
            new_mode = data['mode']
            if new_mode == 'P2P':

                conf_id = data['conference_id']
                target_sid = data['target_sid']
                print(target_sid)
                print(self.username)
                if target_sid == self.username:
                    return
                print("Switching to P2P mode")
                await self.create_p2p_offer(target_sid, conf_id)
            elif new_mode == 'CS':
                print("Switching to Client-Server mode")
                await self.cleanup_p2p_resources()





    async def handle_p2p_offer(self, source_sid, offer, conf_id):
        self.conference.mode = "P2P"
        self.create_connection(source_sid)
        await self.peer_connection.setRemoteDescription(RTCSessionDescription(offer, "offer"))
        answer = await self.peer_connection.createAnswer()
        await self.peer_connection.setLocalDescription(answer)
        while self.peer_connection.iceGatheringState != 'complete':
            await asyncio.sleep(0.1)
        await self.sio.emit('p2p_answer', {
            'target_sid': source_sid,
            'answer': self.peer_connection.localDescription.sdp,
            'conference_id': conf_id
        })

    async def handle_p2p_answer(self, answer):
        await self.peer_connection.setRemoteDescription(RTCSessionDescription(answer, "answer"))
        await self.conference_frame.insert_message("系统：连接成功。")


    async def handle_ice_candidate(self, candidate):
        self.peer_connection.addIceCandidate(candidate)

    async def create_p2p_offer(self, target_sid, conf_id):
        self.create_connection(target_sid)
        self.create_channels()
        self.conference_frame.setup_p2p_event_handlers()
        offer = await self.peer_connection.createOffer()
        await self.peer_connection.setLocalDescription(offer)
        while self.peer_connection.iceGatheringState != 'complete':
            await asyncio.sleep(0.1)
        await self.sio.emit('p2p_offer', {
            'target_sid': target_sid,
            'offer': self.peer_connection.localDescription.sdp,
            'conference_id': conf_id
        })


    def create_channels(self):
        self.p2p_channels["message_channel"] = self.peer_connection.createDataChannel("message_channel")
        video = self.p2p_channels["audio_channel"] = self.peer_connection.createDataChannel("audio_channel")
        self.p2p_channels["video_channel"] = self.peer_connection.createDataChannel("video_channel")
        self.p2p_channels["screen_channel"] = self.peer_connection.createDataChannel("screen_channel")
        # self.peer_connection.addTrack(SilentAudioTrack())
    def create_connection(self, target_sid):
        peer_connection = self.peer_connection = RTCPeerConnection()
        self.peer_id = target_sid
        self.conference.mode = "P2P"
        self.conference_frame.insert_message("系统：连接建立中。")

        @peer_connection.on("icecandidate")
        async def on_ice_candidate(candidate):
            if candidate:
                # 将候选通过信令服务器发送给对端
                await self.sio.emit("ice_candidate", {"candidate": candidate.to_dict(), 'conference_id': self.conference.id})
            else:
                print("ICE candidate gathering complete.")


        @peer_connection.on("datachannel")
        async def on_datachannel(channel):
            print(f"Data channel received: {channel.label}")
            print(f"Data channel state: {channel.readyState}")
            self.p2p_channels[str(channel.label)] = channel
            if None not in self.p2p_channels.values():
                print("4 channels are all ready")
                self.conference_frame.setup_p2p_event_handlers()
                self.conference_frame.insert_message("系统：连接成功")



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
            if self.conference.mode == "CS":
                await self.sio.emit('send_message', {
                    'conference_id': self.conference.id,
                    'message': message,
                    'user_id': self.user_id
                })
            elif self.conference.mode == "P2P":
                data = {
                    'message': message,
                    'sender': self.username
                }
                data = pickle.dumps(data)
                self.p2p_channels['message_channel'].send(data)
                self.conference_frame.insert_message(f"{self.username}: {message}")


    async def send_video(self, video_data):
        """发送视频数据"""
        if self.conference:
            if self.conference.mode == "CS":

                await self.video_sio.emit('video', {
                    'conference_id': self.conference.id,
                    'data': video_data['data'] if isinstance(video_data, dict) else video_data,
                    'user_id': self.user_id
                })
            elif self.conference.mode == "P2P":
                data = {
                    'conference_id': self.conference.id,
                    'data': video_data['data'] if isinstance(video_data, dict) else video_data,
                    'user_id': self.user_id
                }
                data = pickle.dumps(data)
                self.p2p_channels['video_channel'].send(data)

    async def send_screen_share(self, screen_data):
        """发送屏幕共享数据"""
        if self.conference:
            if self.conference.mode == "CS":
                print("send_screen_share")
                await self.screen_sio.emit('screen_share', {
                    'conference_id': self.conference.id,
                    'data': screen_data['data'] if isinstance(screen_data, dict) else screen_data,
                    'user_id': self.user_id
                })
                # 修改data格式
            elif self.conference.mode == "P2P":
                data = {
                    'conference_id': self.conference.id,
                    'data': screen_data['data'] if isinstance(screen_data, dict) else screen_data,
                    'user_id': self.user_id
                }
                data = pickle.dumps(data)
                self.p2p_channels['screen_channel'].send(data)

    async def send_audio(self, audio_data):
        """发送音频数据"""
        if self.conference:
            if self.conference.mode == "CS":
                await self.sio.emit('audio', {
                    'conference_id': self.conference.id,
                    'data': audio_data['data'] if isinstance(audio_data, dict) else audio_data,
                    'user_id': self.user_id
                })
            elif self.conference.mode == "P2P":
                data = {
                    'data': audio_data['data'] if isinstance(audio_data, dict) else audio_data,
                    'user_id': self.user_id
                }
                data = pickle.dumps(data)
                self.p2p_channels['audio_channel'].send(data)

    async def notify_video_stopped(self):
        """通知其他用户视频已停止"""
        if self.conference:
            if self.conference.mode == "CS":
                # 通过video_sio发送停止信号
                await self.video_sio.emit('video_stopped', {
                    'conference_id': self.conference.id,
                    'user_id': self.user_id
                })
            elif self.conference.mode == "P2P":
                data = {
                    'conference_id': self.conference.id,
                    'user_id': self.user_id,
                    'message': "stop_video:oediv_pots"
                }
                data = pickle.dumps(data)
                self.p2p_channels['message_channel'].send(data)
    
    async def notify_screen_share_stopped(self):
        """通知其他用户屏幕共享已停止"""
        if self.conference:
            # 通过screen_sio发送停止信号
            if self.conference.mode == "CS":
                await self.screen_sio.emit('screen_share_stopped', {
                    'conference_id': self.conference.id,
                    'user_id': self.user_id
                })
            elif self.conference.mode == "P2P":
                data = {
                    'conference_id': self.conference.id,
                    'user_id': self.user_id,
                    'message': "stop_screen:neercs_pots"
                }
                data = pickle.dumps(data)
                self.p2p_channels['message_channel'].send(data)

    async def cleanup_p2p_resources(self):
        """
        清理所有 P2P 连接的资源，包括 PeerConnection 和数据通道。
        """
        print("Cleaning up P2P resources...")

        # 关闭所有数据通道
        for channel_name, channel in self.p2p_channels.items():
            if channel and channel.readyState != "closed":
                channel.close()
                print(f"DataChannel '{channel_name}' closed.")

        # 清空数据通道字典
        self.p2p_channels.clear()

        # 关闭 PeerConnection
        if self.peer_connection:
            await self.peer_connection.close()
            print("PeerConnection closed.")
            self.peer_connection = None

        # 清空本地其他资源
        self.peer_id = None
        self.conference.mode = "CS"
        print("All P2P resources cleaned.")