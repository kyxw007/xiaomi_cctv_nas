from flask import Flask, jsonify, Response, request, send_file, stream_with_context, g
from flask_cors import CORS
import os
from .webdav_client import WebDAVClient
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
import signal
import threading


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
cameras = []
with open('/app/backend/cfg.json', 'r', encoding='utf-8') as file:
    data = json.load(file)
    cameras = data['cameras']
 

# 全局变量来跟踪活动的流进程
active_streams = {}
stream_lock = threading.Lock()

# 简化的停止标志
stop_flags = {}
stop_lock = threading.Lock()

def should_stop_stream(stream_id):
    """检查流是否应该停止"""
    with stop_lock:
        return stop_flags.get(stream_id, False)

def set_stop_flag(stream_id):
    """设置停止标志"""
    with stop_lock:
        stop_flags[stream_id] = True

def clear_stop_flag(stream_id):
    """清除停止标志"""
    with stop_lock:
        if stream_id in stop_flags:
            del stop_flags[stream_id]

def check_client_connection():
    """检查客户端连接是否还活跃"""
    try:
        # 尝试访问请求上下文
        if hasattr(g, 'connection_id'):
            connection_id = g.connection_id
            with connection_lock:
                return client_connections.get(connection_id, False)
        return True
    except:
        return False

@app.route('/api/cameras', methods=['GET'])
def get_cameras():
    """获取摄像头列表"""
    return jsonify({'cameras': cameras})

@app.route('/api/cameras/<int:camera_id>/videos', methods=['GET'])
def get_camera_videos(camera_id):
    """获取指定摄像头的视频列表"""
    try:
        camera = next((cam for cam in cameras if cam['id'] == camera_id), None)
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
        filename: 视频文件名（格式：00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4 或 YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4）
    
    Returns:
        (start_time, end_time) 元组，如果解析失败返回 None
    """
    try:
        # 分割文件名
        parts = filename.split('_')
        
        # 支持两种格式：
        # 1. 00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4 (3个部分)
        # 2. YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4 (2个部分)
        if len(parts) == 3:
            # 格式1: 00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4
            start_str = parts[1]
            end_str = parts[2].split('.')[0]  # 移除 .mp4 后缀
        elif len(parts) == 2:
            # 格式2: YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4
            start_str = parts[0]
            end_str = parts[1].split('.')[0]  # 移除 .mp4 后缀
        else:
            # 不支持的格式
            print(f"Unsupported filename format: {filename}")
            return None
            
        # 解析时间字符串
        start_time = datetime.strptime(start_str, "%Y%m%d%H%M%S")
        end_time = datetime.strptime(end_str, "%Y%m%d%H%M%S")
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
                
            # 从文件名中提取时间戳 (格式: 00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4 或 YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4)
            parts = file_name.split('_')
            
            # 支持两种格式：
            # 1. 00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4 (3个部分)
            # 2. YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4 (2个部分)
            if len(parts) == 3:
                # 格式1: 00_YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4
                start_time_str = parts[1]
                end_time_str = parts[2].split('.')[0]  # 移除 .mp4 后缀
            elif len(parts) == 2:
                # 格式2: YYYYMMDDHHMMSS_YYYYMMDDHHMMSS.mp4
                start_time_str = parts[0]
                end_time_str = parts[1].split('.')[0]  # 移除 .mp4 后缀
            else:
                # 不支持的格式，跳过
                continue
                
            try:
                # 解析时间字符串
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

@app.route('/api/video/stream', methods=['GET', 'OPTIONS'])
def stream_video():
    # 处理 OPTIONS 预检请求
    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Range,Accept,Origin,Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    
    try:
        start_time = request.args.get('start_time')
        video_dir = request.args.get('video_dir')
        playback_rate = float(request.args.get('playback_rate', 1))
        
        if not start_time or not video_dir:
            logging.error("Missing required parameters")
            return jsonify({'error': 'MISSING_PARAMS', 'message': '缺少必要参数'}), 400
            
        # 查找视频文件
        video_path, video_info = find_video_chunk(start_time, video_dir)
        if not video_path or not video_info:
            logging.error(f"No video found for time {start_time} in directory {video_dir}")
            return jsonify({'error': 'NO_VIDEO', 'message': '该时段无视频记录'}), 404
            
        # 计算视频内的偏移时间
        target_time_obj = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        offset_seconds = calculate_video_offset(video_info, target_time_obj)
        
        logging.info(f"Streaming video: {video_path}")
        logging.info(f"Target time: {target_time_obj}")
        logging.info(f"Offset seconds: {offset_seconds}")
        
        def generate_video_stream():
            process = None
            stream_id = f"{video_dir.replace('/', '_')}_{id(threading.current_thread())}"
            
            try:
                webdav_url = f"https://kyxw007:nb061617@home.kyxw007.wang:5008{video_path}"
                logging.info(f"WebDAV URL: {webdav_url}")
                logging.info(f"Starting stream with ID: {stream_id}")
                
                # 优化流式播放启动时间
                cmd = [
                    'ffmpeg',
                    '-timeout', '30000000',  # 30秒连接超时（微秒）
                    '-headers', 'User-Agent: FFmpeg',
                    '-i', webdav_url,
                    '-c:v', 'libx264',  # 转换为 H.264 以确保浏览器兼容性
                    '-preset', 'ultrafast',  # 最快编码速度
                    '-tune', 'zerolatency',  # 零延迟调优
                    '-c:a', 'aac',  # 转换为 AAC 音频
                    '-b:a', '128k',  # 音频比特率
                    '-f', 'mp4',  # 输出格式为 MP4
                    '-movflags', 'frag_keyframe+empty_moov+default_base_moof',  # 优化流式传输
                    '-frag_duration', '1000000',  # 1秒片段
                    '-min_frag_duration', '1000000',  # 最小片段时长
                    '-y',  # 覆盖输出文件
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
                
                # 注册活动流
                with stream_lock:
                    active_streams[stream_id] = process
                
                chunk_count = 0
                total_bytes = 0
                first_chunk_received = False
                
                # 设置一个超时机制，如果10秒内没有收到数据就认为失败
                import select
                import time
                
                start_time = time.time()
                timeout = 10
                
                try:
                    while True:
                        # 检查是否超时
                        if time.time() - start_time > timeout and not first_chunk_received:
                            logging.error("FFmpeg timeout: no data received within 10 seconds")
                            break
                        
                        # 检查停止标志
                        if should_stop_stream(stream_id):
                            logging.info(f"Stop flag set for stream {stream_id}, stopping")
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
                        
                        try:
                            yield chunk
                        except GeneratorExit:
                            logging.info("Client disconnected (GeneratorExit), stopping stream")
                            raise
                        except Exception as e:
                            logging.info(f"Client disconnected (Exception: {e}), stopping stream")
                            break
                        
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
                
                except GeneratorExit:
                    logging.info("Client disconnected, stopping video stream")
                    if process and process.poll() is None:
                        logging.info("Terminating FFmpeg process...")
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                            logging.info("FFmpeg process terminated gracefully")
                        except subprocess.TimeoutExpired:
                            logging.warning("FFmpeg process didn't terminate gracefully, killing...")
                            process.kill()
                            process.wait()
                            logging.info("FFmpeg process killed")
                    raise
                
                except Exception as e:
                    logging.error(f"Error during FFmpeg streaming: {str(e)}")
                    if process and process.poll() is None:
                        logging.info("Terminating FFmpeg process due to error...")
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                
            except Exception as e:
                logging.error(f"FFmpeg setup error: {str(e)}")
                if process and process.poll() is None:
                    process.terminate()
                yield b''
            
            finally:
                # 从活动流中移除
                with stream_lock:
                    if stream_id in active_streams:
                        del active_streams[stream_id]
                
                # 清理停止标志
                clear_stop_flag(stream_id)
                
                # 确保进程被清理（异步，不阻塞）
                if process and process.poll() is None:
                    def cleanup_process():
                        try:
                            logging.info(f"Cleaning up stream process: {stream_id}")
                            process.terminate()
                            process.wait(timeout=2)
                            logging.info(f"Stream process {stream_id} terminated gracefully")
                        except subprocess.TimeoutExpired:
                            logging.warning(f"Stream process {stream_id} didn't terminate gracefully, killing...")
                            try:
                                process.kill()
                                process.wait(timeout=1)
                                logging.info(f"Stream process {stream_id} killed")
                            except:
                                logging.error(f"Failed to kill process {stream_id}")
                        except Exception as e:
                            logging.error(f"Error cleaning up process {stream_id}: {e}")
                    
                    # 在后台线程中清理进程
                    cleanup_thread = threading.Thread(target=cleanup_process)
                    cleanup_thread.daemon = True
                    cleanup_thread.start()
        
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
        response.headers['Content-Type'] = 'video/mp4'
        
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

@app.route('/api/video/stop', methods=['POST'])
def stop_video_stream():
    """停止视频流"""
    try:
        # 立即返回响应，避免阻塞前端
        response_data = {'message': 'Stop request received'}
        
        # 获取请求数据（如果有的话）
        try:
            data = request.get_json() or {}
            stream_id = data.get('stream_id')
        except:
            data = {}
            stream_id = None
        
        # 异步停止流，不阻塞响应
        def stop_streams_async():
            """异步停止流"""
            try:
                with stream_lock:
                    streams_to_stop = []
                    
                    if stream_id and stream_id in active_streams:
                        streams_to_stop.append((stream_id, active_streams[stream_id]))
                        logging.info(f"Stopping specific video stream: {stream_id}")
                    else:
                        # 停止所有活动流
                        streams_to_stop = list(active_streams.items())
                        logging.info(f"Stopping all active video streams ({len(streams_to_stop)} streams)")
                    
                    # 设置停止标志并终止进程
                    for sid, process in streams_to_stop:
                        try:
                            set_stop_flag(sid)
                            if process and process.poll() is None:
                                logging.info(f"Terminating stream process: {sid}")
                                process.terminate()
                                # 给进程一个很短的时间优雅退出
                                try:
                                    process.wait(timeout=0.5)
                                    logging.info(f"Stream {sid} terminated gracefully")
                                except subprocess.TimeoutExpired:
                                    logging.warning(f"Stream {sid} didn't terminate quickly, killing...")
                                    process.kill()
                                    try:
                                        process.wait(timeout=0.5)
                                        logging.info(f"Stream {sid} killed")
                                    except:
                                        logging.error(f"Failed to kill stream {sid}")
                        except Exception as e:
                            logging.error(f"Error stopping stream {sid}: {e}")
                    
                    # 清理活动流字典
                    if stream_id and stream_id in active_streams:
                        del active_streams[stream_id]
                    else:
                        active_streams.clear()
                        # 清理所有停止标志
                        with stop_lock:
                            stop_flags.clear()
                            
            except Exception as e:
                logging.error(f"Error in async stop: {e}")
        
        # 在后台线程中执行停止操作
        import threading
        stop_thread = threading.Thread(target=stop_streams_async)
        stop_thread.daemon = True
        stop_thread.start()
        
        # 立即返回成功响应
        return jsonify(response_data), 200
                
    except Exception as e:
        logging.error(f"Error stopping video stream: {str(e)}")
        return jsonify({'error': 'STOP_ERROR', 'message': '停止视频流失败'}), 500

# 在应用启动时检查
if __name__ == '__main__':
    if not check_ffmpeg():
        print("Warning: FFmpeg not found. Video streaming may not work properly.")
    app.run(debug=True, host='0.0.0.0', port=5001) 