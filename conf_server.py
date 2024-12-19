from typing import Dict
import uuid
import socketio
from aiohttp import web
from protocol import Conference
sio = socketio.AsyncServer(async_mode='aiohttp', ping_timeout=3, ping_interval=25)
app = web.Application()
sio.attach(app)

conferences: Dict[str, Conference] = {}

@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")

@sio.event
async def disconnect(sid):
    print(f"Client {sid} disconnected")
    for conf in conferences.values():
        if sid in conf.participants:
            client_name = conf.participants[sid]
            del conf.participants[sid]
            await sio.emit('participant_left', 
                           {'conference_id': conf.id, 'client_id': sid, 'client_name': client_name}, 
                           room=conf.id)
            break
@sio.on('some_event')
async def handle_some_event(sid, data):
    print(f"Received event from sid: {sid}")
    await sio.emit('some_response', {'message': 'Hello'}, room=sid)

# @sio.on('create_conference')
# async def on_create_conference(sid, data):
#     print(f"Create conference request received from {sid}: {data}")
#     try:
#         new_conf = Conference(
#             id=str(uuid.uuid4()),
#             name=data['name'],
#             creator_id=sid,
#             participants={sid: data['username']}
#         )
#         conferences[new_conf.id] = new_conf
#         print(conferences)
#         print(f"Conference created successfully: {new_conf}")
#         await sio.enter_room(sid, new_conf.id)
#         print(f"Sending conference_created event to {sid}")
#         await sio.emit('conference_created', new_conf.to_dict(), room=sid)
#         # await sio.emit('message', {'text': 'Welcome to the conference!'}, room=new_conf.id)


#     except Exception as e:
#         print(f"Error in on_create_conference: {e}")
@sio.on('create_conference')
async def on_create_conference(sid, data):
    new_conf = Conference(
        id=str(uuid.uuid4()),
        name=data['name'],
        creator_id=sid,
        participants={sid: data['username']}
    )
    conferences[new_conf.id] = new_conf
    await sio.enter_room(sid, new_conf.id)
    # 向所有客户端广播会议创建事件
    await sio.emit('conference_created', new_conf.to_dict())

@sio.on('join_conference')
async def on_join_conference(sid, data):
    conf_id = data['conference_id']
    username = data['username']
    conf = conferences.get(conf_id)

    if conf and len(conf.participants) < conf.max_participants:
        conf.participants[sid] = username
        await sio.enter_room(sid, conf_id)  # 添加 await
        await sio.emit('conference_joined', conf.to_dict(), room=sid)
        await sio.emit('participant_joined', 
                       {'conference_id': conf_id, 'client_id': sid, 'client_name': username}, 
                       room=conf_id, skip_sid=sid)
    else:
        await sio.emit('join_conference_failed', room=sid)

@sio.on('close_conference')
async def on_close_conference(sid, data):
    conf_id = data['conference_id']
    conf = conferences.get(conf_id)
    
    if conf and conf.creator_id == sid:
        # 通知所有参与者会议已关闭
        await sio.emit('conference_closed', 
                      {'conference_id': conf_id}, 
                      room=conf_id)
        
        # 清理会议资源
        if conf_id in conferences:
            # 让所有参与者离开会议房间
            for participant_sid in conf.participants:
                await sio.leave_room(participant_sid, conf_id)
            del conferences[conf_id]

@sio.on('leave_conference')
async def on_leave_conference(sid, data):
    conf_id = data['conference_id']
    conf = conferences.get(conf_id)
    
    if conf and sid in conf.participants:
        client_name = conf.participants[sid]
        del conf.participants[sid]
        await sio.leave_room(sid, conf_id)
        await sio.emit('participant_left',
                      {'conference_id': conf_id, 'client_id': sid, 'client_name': client_name},
                      room=conf_id)

        # 如果没有参与者了，删除会议
        if len(conf.participants) == 0:
            del conferences[conf_id]
@sio.on('get_conferences')
async def on_get_conferences(sid):
    print(f"Received get_conferences request from {sid}")
    try:
        conf_list = [conf.to_dict() for conf in conferences.values()]
        print(f"Preparing to send conference list to {sid}")
        # 修改发送方式，确保事件名称一致
        await sio.emit('conference_list_response', {'conferences': conf_list}, to=sid)
        print(f"Sent conference list to {sid}")
    except Exception as e:
        print(f"Error in get_conferences: {e}")


@sio.on('send_message')
async def on_send_message(sid, data):
    conf_id = data['conference_id']
    message = data['message']
    conf = conferences.get(conf_id)
    if conf and sid in conf.participants:
        sender_name = conf.participants[sid]
        await sio.emit('message_received', {'sender': sender_name, 'message': message}, room=conf_id)

@sio.on('audio')
async def handle_audio(sid, data):
    conf_id = data['conference_id']
    if conf_id in conferences:
        # 广播给同一会议的其他参与者
        await sio.emit('audio', data, room=conf_id, skip_sid=sid)

# 在 conf_server.py 中
@sio.on('video')
async def handle_video(sid, data):
    conf_id = data['conference_id']
    if conf_id in conferences:
        # 在转发时包含发送者信息
        data['participant_id'] = sid
        await sio.emit('video', data, room=conf_id, skip_sid=sid)

@sio.on('screen_share')
async def handle_screen_share(sid, data):
    conf_id = data['conference_id']
    if conf_id in conferences:
        await sio.emit('screen_share', data, room=conf_id, skip_sid=sid)
        
if __name__ == '__main__':
    web.run_app(app, host='127.0.0.1', port=8888)
