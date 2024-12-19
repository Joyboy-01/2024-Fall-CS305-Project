import numpy as np
from typing import Dict

class AudioMixer:
    def __init__(self):
        self.audio_buffers: Dict[str, bytes] = {}
        
    def add_audio_stream(self, user_id: str, audio_data: bytes):
        """添加用户的音频流到缓冲区"""
        self.audio_buffers[user_id] = audio_data
        
    def remove_audio_stream(self, user_id: str):
        """移除用户的音频流"""
        if user_id in self.audio_buffers:
            del self.audio_buffers[user_id]
            
    def mix_audio(self) -> bytes:
        """混合所有音频流"""
        if not self.audio_buffers:
            return b''
            
        # 转换所有音频数据为numpy数组
        audio_arrays = []
        for audio_data in self.audio_buffers.values():
            # 将字节转换为16位整数数组
            array = np.frombuffer(audio_data, dtype=np.int16)
            audio_arrays.append(array)
            
        # 确保所有数组长度相同
        min_length = min(len(arr) for arr in audio_arrays)
        audio_arrays = [arr[:min_length] for arr in audio_arrays]
        
        # 混合音频
        mixed = np.mean(audio_arrays, axis=0, dtype=np.float32)
        
        # 正则化以防止溢出
        if len(audio_arrays) > 1:
            mixed = mixed * (0.7 / len(audio_arrays))
            
        # 转换回16位整数
        mixed = np.clip(mixed, np.iinfo(np.int16).min, np.iinfo(np.int16).max)
        mixed = mixed.astype(np.int16)
        
        return mixed.tobytes()