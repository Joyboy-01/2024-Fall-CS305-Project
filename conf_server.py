from typing import Dict
import uuid
import socketio
from aiohttp import web
from protocol import Conference
from AudioMixer import AudioMixer

# 创建三个不同的socket服务器
sio = socketio.AsyncServer(async_mode='aiohttp', ping_timeout=3, ping_interval=25)
video_sio = socketio.AsyncServer(async_mode='aiohttp', ping_timeout=3, ping_interval=25)
screen_sio = socketio.AsyncServer(async_mode='aiohttp', ping_timeout=3, ping_interval=25)

# 创建应用程序并附加socket服务器
app = web.Application()
sio.attach(app, socketio_path='socket.io')
video_sio.attach(app, socketio_path='video/socket.io')
screen_sio.attach(app, socketio_path='screen/socket.io')

# 存储数据
conferences: Dict[str, Conference] = {}
user_connections = {}  # {user_id: {'main': sid, 'video': sid, 'screen': sid}}

audio_mixers = {}
# 连接事件处理
@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected to main channel")

@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected from main channel")
    # 查找并清理用户连接信息
    for user_id, connections in user_connections.items():
        if connections.get('main') == sid:
            print(f"Cleaning up connections for user {user_id}")
            # 检查并清理会议参与者信息
            for conf in conferences.values():
                if user_id in conf.participants:
                    client_name = conf.participants[user_id]
                    del conf.participants[user_id]
                    await sio.emit('participant_left', {
                        'conference_id': conf.id,
                        'user_id': user_id,
                        'client_name': client_name
                    }, room=conf.id)
            break

@video_sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected to video channel")

@video_sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected from video channel")

@screen_sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected to screen channel")

@screen_sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected from screen channel")

# 注册连接
@sio.on('register_connection')
async def register_main_connection(sid, data):
    user_id = data.get('user_id')
    if user_id:
        if user_id not in user_connections:
            user_connections[user_id] = {}
        user_connections[user_id]['main'] = sid
        print(f"Registered main connection for user {user_id}: {sid}")

@video_sio.on('register_connection')
async def register_video_connection(sid, data):
    user_id = data.get('user_id')
    if user_id:
        if user_id not in user_connections:
            user_connections[user_id] = {}
        user_connections[user_id]['video'] = sid
        print(f"Registered video connection for user {user_id}: {sid}")

@screen_sio.on('register_connection')
async def register_screen_connection(sid, data):
    user_id = data.get('user_id')
    if user_id:
        if user_id not in user_connections:
            user_connections[user_id] = {}
        user_connections[user_id]['screen'] = sid
        print(f"Registered screen connection for user {user_id}: {sid}")

# 会议管理
@sio.on('create_conference')
async def on_create_conference(sid, data):
    user_id = data.get('user_id')
    if not user_id:
        print("No user_id provided in create_conference")
        return
        
    new_conf = Conference(
        id=str(uuid.uuid4()),
        name=data['name'],
        creator_id=user_id,
        participants={user_id: data['username']}
    )
    conferences[new_conf.id] = new_conf
    await sio.enter_room(sid, new_conf.id)
    
    # 创建后直接发送加入成功事件
    await sio.emit('conference_joined', new_conf.to_dict(), room=sid)
    # 向其他客户端广播新会议创建事件
    await sio.emit('conference_created', new_conf.to_dict(), skip_sid=sid)

@sio.on('join_conference')
async def on_join_conference(sid, data):
    user_id = data.get('user_id')
    if not user_id:
        print("No user_id provided in join_conference")
        return

    conf_id = data['conference_id']
    username = data['username']
    conf = conferences.get(conf_id)

    if conf and len(conf.participants) < conf.max_participants:
        # 使用user_id而不是sid
        conf.participants[user_id] = username
        # 仍然使用sid加入房间，因为这是Socket.IO的要求
        await sio.enter_room(sid, conf_id)
        video_sid = user_connections.get(user_id, {}).get('video')
        if video_sid:
            await video_sio.enter_room(video_sid, conf_id)
            print(f"Video socket {video_sid} joined room {conf_id}")
        # 屏幕共享socket加入房间    
        screen_sid = user_connections.get(user_id, {}).get('screen')
        if screen_sid:
            await screen_sio.enter_room(screen_sid, conf_id)
            print(f"Screen socket {screen_sid} joined room {conf_id}")
        await sio.emit('conference_joined', conf.to_dict(), room=sid)
        # 广播时使用user_id
        await sio.emit('participant_joined', {
            'conference_id': conf_id,
            'user_id': user_id,
            'client_name': username
        }, room=conf_id, skip_sid=sid)
    else:
        await sio.emit('join_conference_failed', room=sid)

@sio.on('leave_conference')
async def on_leave_conference(sid, data):
    user_id = data.get('user_id')
    if not user_id:
        print("No user_id provided in leave_conference")
        return

    conf_id = data['conference_id']
    conf = conferences.get(conf_id)

    if conf_id in audio_mixers:
        audio_mixers[conf_id].remove_audio_stream(user_id)

    if conf and user_id in conf.participants:
        client_name = conf.participants[user_id]
        del conf.participants[user_id]
        await sio.leave_room(sid, conf_id)
        
        # 广播时使用user_id
        await sio.emit('participant_left', {
            'conference_id': conf_id,
            'user_id': user_id,
            'client_name': client_name
        }, room=conf_id)

        # 如果房间为空，立即删除会议
        if not conf.participants:
            if conf_id in conferences:
                del conferences[conf_id]
            await sio.emit('conference_closed', {'conference_id': conf_id})


@sio.on('close_conference')
async def on_close_conference(sid, data):
    user_id = data.get('user_id')
    if not user_id:
        print("No user_id provided in close_conference")
        return

    conf_id = data['conference_id']
    conf = conferences.get(conf_id)
    
    if conf and conf.creator_id == user_id:
        # 通知所有参与者会议已关闭
        await sio.emit('conference_closed', {
            'conference_id': conf_id
        }, room=conf_id)
        
        # 清理会议资源
        if conf_id in conferences:
            if conf_id in audio_mixers:
                del audio_mixers[conf_id]
            # 让所有参与者离开会议房间
            for participant_user_id in conf.participants:
                participant_sid = user_connections.get(participant_user_id, {}).get('main')
                if participant_sid:
                    await sio.leave_room(participant_sid, conf_id)
            del conferences[conf_id]

@sio.on('get_conferences')
async def on_get_conferences(sid):
    try:
        conf_list = [conf.to_dict() for conf in conferences.values()]
        await sio.emit('conference_list_response', {'conferences': conf_list}, to=sid)
    except Exception as e:
        print(f"Error in get_conferences: {e}")

@sio.on('send_message')
async def on_send_message(sid, data):
    user_id = data.get('user_id')
    if not user_id:
        print("No user_id provided in send_message")
        return

    conf_id = data['conference_id']
    message = data['message']
    conf = conferences.get(conf_id)
    
    if conf and user_id in conf.participants:
        sender_name = conf.participants[user_id]
        await sio.emit('message_received', {
            'sender': sender_name,
            'message': message
        }, room=conf_id)

# 媒体流处理
# 修改视频处理部分
@video_sio.on('video')
async def handle_video(sid, data):
    try:
        user_id = data.get('user_id')
        conf_id = data['conference_id']
        if not user_id or conf_id not in conferences:
            print("No user_id or conf_id provided in send_message")
            return
            
        # 获取用户的video socket id
        video_sid = user_connections.get(user_id, {}).get('video')
        if video_sid:
            print(f"Broadcasting video from user {user_id}")
            await video_sio.emit('video', {
                'conference_id': conf_id,
                'data': data['data'],
                'user_id': user_id
            }, room=conf_id, skip_sid=video_sid)
    except Exception as e:
        print(f"Error broadcasting video: {e}")

# 修改屏幕共享处理部分
@screen_sio.on('screen_share')
async def handle_screen_share(sid, data):
    try:
        user_id = data.get('user_id')
        conf_id = data['conference_id']
        if not user_id or conf_id not in conferences:
            return
            
        # 获取用户的screen socket id
        screen_sid = user_connections.get(user_id, {}).get('screen')
        if screen_sid:
            print(f"Broadcasting screen share from user {user_id}")
            await screen_sio.emit('screen_share', {
                'conference_id': conf_id,
                'data': data['data'],
                'user_id': user_id
            }, room=conf_id, skip_sid=screen_sid)
    except Exception as e:
        print(f"Error broadcasting screen share: {e}")


@sio.on('audio')
async def handle_audio(sid, data):
    """处理接收到的音频数据"""
    try:
        conf_id = data['conference_id']
        user_id = data['user_id']
        if not user_id or conf_id not in conferences:
            return
            
        audio_sid = user_connections.get(user_id, {}).get('main')
        # 确保会议存在音频混音器
        if conf_id not in audio_mixers:
            audio_mixers[conf_id] = AudioMixer()
            
        # 添加音频流到混音器
        audio_mixers[conf_id].add_audio_stream(user_id, data['data'])
        
        # 混合音频
        mixed_audio = audio_mixers[conf_id].mix_audio()
        print(f"Mixed audio of {len(mixed_audio)} bytes")
        # 广播混合后的音频给所有参与者
        await sio.emit('audio', {
            'conference_id': conf_id,
            'data': mixed_audio,
            'user_id': user_id,
            'mixed': True  # 标记这是混合后的音频
        }, room=conf_id, skip_sid=audio_sid)
    except Exception as e:
        print(f"Error handling audio: {e}")

# 添加视频关闭事件处理
@video_sio.on('video_stopped')
async def handle_video_stopped(sid, data):
    try:
        user_id = data.get('user_id')
        conf_id = data['conference_id']
        if not user_id or conf_id not in conferences:
            return
            
        print(f"Broadcasting video stop from user {user_id}")
        await video_sio.emit('video_stopped', {
            'conference_id': conf_id,
            'user_id': user_id
        }, room=conf_id, skip_sid=sid)
    except Exception as e:
        print(f"Error broadcasting video stop: {e}")

# 添加屏幕共享关闭事件处理
@screen_sio.on('screen_share_stopped')
async def handle_screen_share_stopped(sid, data):
    try:
        user_id = data.get('user_id')
        conf_id = data['conference_id']
        if not user_id or conf_id not in conferences:
            return
            
        print(f"Broadcasting screen share stop from user {user_id}")
        await screen_sio.emit('screen_share_stopped', {
            'conference_id': conf_id,
            'user_id': user_id
        }, room=conf_id, skip_sid=sid)
    except Exception as e:
        print(f"Error broadcasting screen share stop: {e}")
        
if __name__ == '__main__':
    web.run_app(app, host='10.28.94.9', port=8888)
