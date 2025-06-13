from flask import Flask, jsonify, Response, request, send_file, stream_with_context
from flask_cors import CORS
import os
from webdav_client import WebDAVClient
from datetime import datetime, timedelta
import time
import io
import requests
from urllib.parse import urljoin
import gzip
import base64
import json
import logging
import re
import subprocess
import shutil

app = Flask(__name__)

# 配置 CORS，允许所有来源的请求，并添加更多头部支持
CORS(app, 
     resources={
         r"/api/*": {
             "origins": ["http://localhost:3000"],
             "methods": ["GET", "POST", "OPTIONS"],
             "allow_headers": ["Content-Type", "Range", "Accept", "Origin", "Authorization"],
             "expose_headers": ["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"],
             "supports_credentials": True,
             "max_age": 3600
         }
     },
     supports_credentials=True)

# 配置
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
app.config['VIDEO_DIR'] = os.getenv('VIDEO_DIR', 'videos')

# 模拟摄像头数据，实际应用中应该从数据库或配置文件中读取
CAMERAS = [
    {
        'id': 1,
        'name': '前门摄像头',
        'video_dir': 'videos/front_door'
    },
    {
        'id': 2,
        'name': '后门摄像头',
        'video_dir': 'videos/back_door'
    },
    {
        'id': 3,
        'name': '车库摄像头',
        'video_dir': 'videos/garage'
    }
]

CAM_NAMES = {
'XiaomiCamera_00_78DF72F2BD91':'客卧',
'XiaomiCamera_01_78DF72F2F3CE':'机位 2',
'XiaomiCamera_02_78DF72F2EDA4':'机位 3',
'XiaomiCamera_00_78DF72F2F3CE':'客厅沙发机位',
'XiaomiCamera_00_78DF72F2EDA4':'客厅窗帘机位'
}

@app.route('/api/cameras', methods=['GET'])
def get_cameras():
    """获取摄像头列表"""
    print("get_cameras")
    client = WebDAVClient(
        username="kyxw007",
        password="nb061617"
    )
    cameras = []
    try:
        files = client.list_directory("/CCTV/")
        print(files)
        if not files:
            return jsonify({}), 404
        else:
            for item in files:
                if item['type'] == 'directory' and item['name'].startswith("XiaomiCamera_"):
                    cameras.append({
                        'id': len(cameras) + 1,
                        'name': CAM_NAMES[item['name']],
                        'video_dir': f"/CCTV/{item['name']}"
                    })

        return jsonify({'cameras': cameras})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cameras/<int:camera_id>/videos', methods=['GET'])
def get_camera_videos(camera_id):
    """获取指定摄像头的视频列表"""
    try:
        camera = next((cam for cam in CAMERAS if cam['id'] == camera_id), None)
        if not camera:
            return jsonify({'error': 'Camera not found'}), 404

        videos = []
        video_dir = camera['video_dir']
        if os.path.exists(video_dir):
            for filename in os.listdir(video_dir):
                if filename.endswith(('.mp4', '.avi', '.mkv')):
                    videos.append({
                        'id': len(videos) + 1,
                        'name': filename,
                        'path': f'/{video_dir}/{filename}',
                        'size': os.path.getsize(os.path.join(video_dir, filename)),
                        'created_at': os.path.getctime(os.path.join(video_dir, filename))
                    })
        return jsonify({'videos': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/videos', methods=['GET'])
def get_videos():
    """获取所有视频列表"""
    try:
        videos = []
        video_dir = app.config['VIDEO_DIR']
        if os.path.exists(video_dir):
            for filename in os.listdir(video_dir):
                if filename.endswith(('.mp4', '.avi', '.mkv')):
                    videos.append({
                        'id': len(videos) + 1,
                        'name': filename,
                        'path': f'/videos/{filename}',
                        'size': os.path.getsize(os.path.join(video_dir, filename)),
                        'created_at': os.path.getctime(os.path.join(video_dir, filename))
                    })
        return jsonify({'videos': videos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/videos/<video_id>', methods=['GET'])
def get_video(video_id):
    """获取单个视频信息"""
    try:
        video_dir = app.config['VIDEO_DIR']
        videos = []
        for filename in os.listdir(video_dir):
            if filename.endswith(('.mp4', '.avi', '.mkv')):
                videos.append({
                    'id': len(videos) + 1,
                    'name': filename,
                    'path': f'/videos/{filename}'
                })
        
        video = next((v for v in videos if v['id'] == int(video_id)), None)
        if video:
            return jsonify(video)
        return jsonify({'error': 'Video not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def parse_video_filename(filename):
    """解析视频文件名，提取开始和结束时间
    
    Args:
        filename: 视频文件名（格式：00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4）
    
    Returns:
        (start_time, end_time) 元组，如果解析失败返回 None
    """
    try:
        # 移除可能的00_前缀
        name = filename.split('_', 1)[-1]
        # 分割开始和结束时间
        start_str, end_str = name.split('_')
        # 解析时间字符串
        start_time = datetime.strptime(start_str, "%Y%m%d%H%M%S")
        end_time = datetime.strptime(end_str.split('.')[0], "%Y%m%d%H%M%S")
        return start_time, end_time
    except Exception as e:
        print(f"Error parsing video filename {filename}: {str(e)}")
        return None

def find_video_chunk(target_time, video_dir):
    """查找指定时间点的视频文件
    
    Args:
        target_time: 目标时间（格式：YYYY-MM-DD HH:%M:%S）
        video_dir: 视频目录路径
        
    Returns:
        tuple: (视频文件路径, 视频时间信息) 或 (None, None)
        视频时间信息包含: {'start_time': datetime, 'end_time': datetime}
    """
    try:
        # 创建WebDAV客户端
        client = WebDAVClient(
            username="kyxw007",
            password="nb061617"
        )
        
        # 解析目标时间
        target_time_obj = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        target_timestamp = target_time_obj.timestamp()
        
        # 获取视频目录下的所有文件
        files = client.list_directory(video_dir)
        if not files:
            logging.info(f"No files found in directory: {video_dir}")
            return None, None
            
        # 查找包含目标时间的视频文件
        matching_files = []
        closest_file = None
        min_time_diff = float('inf')
        
        for file in files:
            file_name = file['name']
            if not file_name.endswith('.mp4'):
                continue
                
            # 从文件名中提取时间戳 (格式: 00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4)
            parts = file_name.split('_')
            if len(parts) != 3:
                continue
                
            try:
                # 提取开始和结束时间
                start_time_str = parts[1]
                end_time_str = parts[2].split('.')[0]  # 移除 .mp4 后缀
                
                start_time = datetime.strptime(start_time_str, "%Y%m%d%H%M%S")
                end_time = datetime.strptime(end_time_str, "%Y%m%d%H%M%S")
                
                start_timestamp = start_time.timestamp()
                end_timestamp = end_time.timestamp()
                
                # 检查目标时间是否在视频时间范围内
                if start_timestamp <= target_timestamp <= end_timestamp:
                    # 找到包含目标时间的视频文件
                    video_path = os.path.join(video_dir, file_name).replace("\\", "/")
                    video_info = {
                        'start_time': start_time,
                        'end_time': end_time,
                        'filename': file_name
                    }
                    logging.info(f"Found exact match video file: {video_path}")
                    logging.info(f"Video time range: {start_time} - {end_time}")
                    logging.info(f"Target time: {target_time_obj}")
                    return video_path, video_info
                    
                # 如果不在范围内，记录为候选文件
                time_diff = min(
                    abs(start_timestamp - target_timestamp),
                    abs(end_timestamp - target_timestamp)
                )
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_file = {
                        'name': file_name,
                        'start_time': start_time,
                        'end_time': end_time,
                        'time_diff': time_diff
                    }
                    
            except ValueError as e:
                logging.warning(f"Error parsing time from filename {file_name}: {str(e)}")
                continue
        
        # 如果没有找到包含目标时间的文件，返回最接近的文件
        if closest_file:
            video_path = os.path.join(video_dir, closest_file['name']).replace("\\", "/")
            video_info = {
                'start_time': closest_file['start_time'],
                'end_time': closest_file['end_time'],
                'filename': closest_file['name']
            }
            logging.warning(f"No exact match found, using closest file: {video_path}")
            logging.warning(f"Time difference: {closest_file['time_diff']} seconds")
            return video_path, video_info
        
        logging.info(f"No matching video file found for time: {target_time_obj}")
        return None, None
        
    except Exception as e:
        logging.error(f"Error finding video chunk: {str(e)}")
        return None, None

@app.route('/api/video/stream')
def stream_video():
    try:
        start_time = request.args.get('start_time')
        video_dir = request.args.get('video_dir')
        playback_rate = float(request.args.get('playback_rate', 1))
        
        if not start_time or not video_dir:
            return jsonify({'error': 'MISSING_PARAMS', 'message': '缺少必要参数'}), 400
            
        # 查找视频文件
        video_path, video_info = find_video_chunk(start_time, video_dir)
        if not video_path or not video_info:
            return jsonify({'error': 'NO_VIDEO', 'message': '该时段无视频记录'}), 404
            
        # 计算视频内的偏移时间
        target_time_obj = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        offset_seconds = calculate_video_offset(video_info, target_time_obj)
        
        logging.info(f"Streaming video: {video_path}")
        logging.info(f"Target time: {target_time_obj}")
        logging.info(f"Offset seconds: {offset_seconds}")
        
        def generate_video_stream():
            process = None
            try:
                webdav_url = f"https://kyxw007:nb061617@home.kyxw007.wang:5008{video_path}"
                
                # 使用更保守的策略：
                # 1. 如果偏移小于60秒，从头开始播放
                # 2. 如果偏移较大，使用输入端seek但减少偏移量以确保安全
                
                if offset_seconds < 60:
                    # 小偏移：从头开始播放，让前端处理时间同步
                    logging.info(f"Small offset ({offset_seconds}s), playing from start")
                    cmd = [
                        'ffmpeg',
                        '-headers', 'User-Agent: FFmpeg',
                        '-i', webdav_url,
                        '-c:v', 'libx264',
                        '-c:a', 'aac',
                        '-preset', 'ultrafast',
                        '-crf', '23',
                        '-f', 'mp4',
                        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
                        '-avoid_negative_ts', 'make_zero',
                        '-fflags', '+genpts',
                        '-t', '300',  # 播放5分钟
                        '-loglevel', 'info',
                        'pipe:1'
                    ]
                else:
                    # 大偏移：使用保守的seek策略
                    # 向前seek到最近的可能关键帧位置（每10秒一个关键帧）
                    safe_offset = max(0, (offset_seconds // 10) * 10 - 10)  # 向下取整到10秒边界，再减10秒
                    logging.info(f"Large offset ({offset_seconds}s), using safe offset ({safe_offset}s)")
                    
                    cmd = [
                        'ffmpeg',
                        '-ss', str(safe_offset),  # 输入端seek到安全位置
                        '-headers', 'User-Agent: FFmpeg',
                        '-i', webdav_url,
                        '-c:v', 'libx264',
                        '-c:a', 'aac',
                        '-preset', 'ultrafast',
                        '-crf', '23',
                        '-f', 'mp4',
                        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
                        '-avoid_negative_ts', 'make_zero',
                        '-fflags', '+genpts',
                        '-t', '300',  # 播放5分钟
                        '-loglevel', 'info',
                        'pipe:1'
                    ]
                
                logging.info(f"FFmpeg command: {' '.join(cmd)}")
                
                # 启动 FFmpeg 进程
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                
                chunk_count = 0
                total_bytes = 0
                first_chunk_received = False
                
                # 设置一个超时机制，如果10秒内没有收到数据就认为失败
                import select
                import time
                
                start_time = time.time()
                timeout = 10  # 10秒超时
                
                try:
                    while True:
                        # 检查是否超时
                        if time.time() - start_time > timeout and not first_chunk_received:
                            logging.error("FFmpeg timeout: no data received within 10 seconds")
                            break
                        
                        # 使用非阻塞读取
                        if hasattr(select, 'select'):
                            ready, _, _ = select.select([process.stdout], [], [], 1.0)
                            if not ready:
                                # 检查进程是否还在运行
                                if process.poll() is not None:
                                    break
                                continue
                        
                        chunk = process.stdout.read(8192)
                        if not chunk:
                            break
                        
                        chunk_count += 1
                        total_bytes += len(chunk)
                        
                        if not first_chunk_received:
                            first_chunk_received = True
                            logging.info(f"First chunk received: {len(chunk)} bytes")
                        
                        yield chunk
                        
                        # 每50个chunk记录一次进度
                        if chunk_count % 50 == 0:
                            logging.info(f"Streamed {chunk_count} chunks, {total_bytes} bytes")
                    
                    # 等待进程结束
                    return_code = process.wait(timeout=5)
                    stderr_output = process.stderr.read().decode('utf-8')
                    
                    if return_code != 0:
                        logging.error(f"FFmpeg process failed with return code {return_code}")
                        logging.error(f"FFmpeg stderr: {stderr_output}")
                    else:
                        logging.info(f"FFmpeg streaming completed successfully")
                        logging.info(f"Total: {chunk_count} chunks, {total_bytes} bytes")
                    
                    # 如果没有收到任何数据，记录详细错误信息
                    if not first_chunk_received:
                        logging.error("No data received from FFmpeg")
                        logging.error(f"FFmpeg stderr: {stderr_output}")
                        # 尝试生成一个最小的有效MP4头
                        yield generate_empty_mp4_header()
                
                except GeneratorExit:
                    logging.info("Client disconnected, stopping video stream")
                    if process and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                    raise
                
                except Exception as e:
                    logging.error(f"Error during FFmpeg streaming: {str(e)}")
                    if process and process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                
            except Exception as e:
                logging.error(f"FFmpeg setup error: {str(e)}")
                if process and process.poll() is None:
                    process.terminate()
                yield b''
            
            finally:
                # 确保进程被清理
                if process and process.poll() is None:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    except:
                        pass
        
        # 创建响应
        response = Response(
            stream_with_context(generate_video_stream()),
            mimetype='video/mp4',
            direct_passthrough=True
        )
        
        # 添加必要的头部
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Range,Accept,Origin,Authorization'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Range,Accept-Ranges,Content-Length,Content-Type'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-cache'
        
        return response
        
    except Exception as e:
        logging.error(f"Video streaming error: {str(e)}")
        return jsonify({'error': 'STREAM_ERROR', 'message': '视频流传输错误'}), 500

def calculate_video_offset(video_info, target_time):
    """计算视频内的时间偏移
    
    Args:
        video_info: 视频信息字典，包含 start_time 和 end_time
        target_time: 目标时间 (datetime 对象)
        
    Returns:
        偏移秒数 (float)
    """
    try:
        video_start_time = video_info['start_time']
        video_end_time = video_info['end_time']
        
        # 计算视频总长度（秒）
        video_duration = (video_end_time - video_start_time).total_seconds()
        
        # 计算偏移
        offset_seconds = (target_time - video_start_time).total_seconds()
        
        logging.info(f"Video start time: {video_start_time}")
        logging.info(f"Video end time: {video_end_time}")
        logging.info(f"Video duration: {video_duration} seconds")
        logging.info(f"Target time: {target_time}")
        logging.info(f"Calculated offset: {offset_seconds} seconds")
        
        # 确保偏移在有效范围内
        if offset_seconds < 0:
            logging.warning(f"Target time {target_time} is before video start {video_start_time}, using offset 0")
            return 0
        elif offset_seconds >= video_duration:
            logging.warning(f"Target time {target_time} is after video end {video_end_time}, using max offset")
            # 返回视频结束前10秒的位置，避免超出范围
            return max(0, video_duration - 10)
        
        return offset_seconds
        
    except Exception as e:
        logging.error(f"Error calculating video offset: {str(e)}")
        return 0

def check_ffmpeg():
    """检查 FFmpeg 是否可用"""
    if not shutil.which('ffmpeg'):
        logging.error("FFmpeg not found. Please install FFmpeg to enable video streaming with time offset.")
        return False
    return True

def generate_empty_mp4_header():
    """生成一个最小的有效MP4头，用于错误情况"""
    # 这是一个最小的MP4文件头，包含必要的box结构
    return b'\x00\x00\x00\x20ftypiso5\x00\x00\x00\x00iso5iso6mp41\x00\x00\x00\x08free'

# 在应用启动时检查
if __name__ == '__main__':
    if not check_ffmpeg():
        print("Warning: FFmpeg not found. Video streaming may not work properly.")
    app.run(debug=True, host='0.0.0.0', port=5001) 