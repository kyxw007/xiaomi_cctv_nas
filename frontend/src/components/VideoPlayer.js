import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  Box, 
  IconButton, 
  Typography, 
  Paper,
  CircularProgress,
  Slider,
  Button,
  Stack, 
  FormControl,
  Select,
  MenuItem
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack'; 
import config from '../config';
import {
  PlayArrow,
  Pause, 
  NavigateNext,
  NavigateBefore, 
  CalendarMonth
} from '@mui/icons-material';
import dayjs from 'dayjs';

const VideoPlayer = () => { 
  const navigate = useNavigate();
  const location = useLocation();
  const camera = location.state?.camera;

  // 所有 hooks 必须在组件顶层调用
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentTime, setCurrentTime] = useState(() => {
    const now = dayjs();
    const oneHourAgo = now.subtract(1, 'hour');
    
    console.log('Current system time:', now.format('YYYY-MM-DD HH:mm:ss'));
    console.log('One hour ago:', oneHourAgo.format('YYYY-MM-DD HH:mm:ss'));
    
    return oneHourAgo;
  });
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [videoUrl, setVideoUrl] = useState(null);
  
  // Refs
  const videoRef = useRef(null);
  const abortControllerRef = useRef(null);
  const isMountedRef = useRef(true);
  const requestInProgressRef = useRef(false);
  const videoUrlRef = useRef(null);

  // 存储事件监听器引用
  const eventListenersRef = useRef({});

  // 停止视频流
  const stopVideoStream = useCallback(() => {
    try {
      console.log('Stopping video stream...');
      // 使用 fetch 但不等待响应，避免阻塞
      fetch(`${config.API_BASE_URL}/api/video/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
      }).then(response => {
        if (response.ok) {
          console.log('Video stream stopped successfully');
        } else {
          console.warn('Failed to stop video stream:', response.status);
        }
      }).catch(error => {
        console.warn('Error stopping video stream:', error);
      });
    } catch (error) {
      console.warn('Error stopping video stream:', error);
    }
  }, []);

  // 清理函数
  const cleanup = useCallback(() => {
    console.log('Cleaning up resources...');
    
    // 停止后端流
    stopVideoStream();
    
    if (abortControllerRef.current) {
      console.log('Aborting previous request...');
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    
    if (videoRef.current) {
      console.log('Cleaning up video element...');
      // 暂停视频
      videoRef.current.pause();
      
      // 移除所有事件监听器
      Object.entries(eventListenersRef.current).forEach(([event, handler]) => {
        if (handler) {
          videoRef.current.removeEventListener(event, handler);
        }
      });
      eventListenersRef.current = {};
      
      // 清空视频源
      videoRef.current.removeAttribute('src');
      videoRef.current.srcObject = null;
      
      // 强制重新加载以释放资源
      videoRef.current.load();
    }
    
    // 清理 URL 引用
    if (videoUrlRef.current) {
      if (videoUrlRef.current.startsWith('blob:')) {
        console.log('Revoking blob URL...');
        URL.revokeObjectURL(videoUrlRef.current);
      } else {
        console.log('Clearing stream URL...');
      }
      videoUrlRef.current = null;
    }
    
    setVideoUrl(null);
    setLoading(false);
    setError(null);
    setIsPlaying(false);
    requestInProgressRef.current = false;
  }, [stopVideoStream]);

  // 组件卸载时清理
  useEffect(() => {
    isMountedRef.current = true;
    
    // 页面卸载时的清理
    const handleBeforeUnload = () => {
      console.log('Page unloading, cleaning up...');
      cleanup();
    };
    
    const handleVisibilityChange = () => {
      if (document.hidden) {
        console.log('Page hidden, pausing video...');
        // 页面隐藏时暂停视频并清理流
        if (videoRef.current && !videoRef.current.paused) {
          videoRef.current.pause();
          setIsPlaying(false);
        }
        // 页面隐藏时也清理流
        stopVideoStream();
      }
    };
    
    // 监听路由变化（如果使用 React Router）
    const handlePopState = () => {
      console.log('Route changing, cleaning up...');
      cleanup();
    };
    
    // 监听页面焦点变化
    const handleBlur = () => {
      console.log('Window lost focus, cleaning up...');
      cleanup();
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('unload', handleBeforeUnload);
    window.addEventListener('pagehide', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('blur', handleBlur);
    
    return () => {
      console.log('VideoPlayer component unmounting...');
      isMountedRef.current = false;
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('unload', handleBeforeUnload);
      window.removeEventListener('pagehide', handleBeforeUnload);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('blur', handleBlur);
      cleanup();
    };
  }, [cleanup, stopVideoStream]);

  // 加载视频
  const loadVideo = useCallback(async (url) => {
    if (requestInProgressRef.current) {
      console.log('Request already in progress, aborting previous request');
      cleanup();
    }

    console.log('Starting video load:', url);
    requestInProgressRef.current = true;
    setLoading(true);
    setError(null);

    try {
      // 直接使用流式 URL，不等待整个文件下载
      if (videoRef.current && isMountedRef.current) {
        videoRef.current.pause();
        
        // 清理旧的 URL
        if (videoUrlRef.current && videoUrlRef.current.startsWith('blob:')) {
          URL.revokeObjectURL(videoUrlRef.current);
        }
        
        // 直接设置流式 URL
        videoRef.current.src = url;
        videoUrlRef.current = url;
        setVideoUrl(url);
        
        // 添加事件监听器
        const handleLoadStart = () => {
          console.log('Video loadstart event');
        };
        
        const handleLoadedMetadata = () => {
          console.log('Video metadata loaded:', {
            duration: videoRef.current.duration,
            videoWidth: videoRef.current.videoWidth,
            videoHeight: videoRef.current.videoHeight
          });
          setLoading(false); // 元数据加载完成就可以停止加载动画
        };
        
        const handleCanPlay = () => {
          console.log('Video can play');
          setLoading(false);
        };
        
        const handleCanPlayThrough = () => {
          console.log('Video can play through');
        };
        
        const handleError = (e) => {
          console.error('Video error:', e);
          const error = videoRef.current.error;
          if (error) {
            console.error('Video error code:', error.code);
            console.error('Video error message:', error.message);
            
            // 根据错误代码提供更具体的错误信息
            let errorMessage = '视频播放错误';
            switch (error.code) {
              case 1:
                errorMessage = '视频加载被中断';
                break;
              case 2:
                errorMessage = '网络错误';
                break;
              case 3:
                errorMessage = '视频解码错误';
                break;
              case 4:
                errorMessage = '视频格式不支持';
                break;
              default:
                errorMessage = '未知视频错误';
                break;
            }
            setError(errorMessage);
            setLoading(false);
          }
        };
        
        const handleProgress = () => {
          if (videoRef.current && videoRef.current.buffered.length > 0) {
            const buffered = videoRef.current.buffered.end(0);
            console.log('Video buffered:', buffered, 'seconds');
          }
        };
        
        // 移除旧的事件监听器
        Object.entries(eventListenersRef.current).forEach(([event, handler]) => {
          if (handler) {
            videoRef.current.removeEventListener(event, handler);
          }
        });
        eventListenersRef.current = {};
        
                 // 添加新的事件监听器
         eventListenersRef.current = {
           loadstart: handleLoadStart,
           loadedmetadata: handleLoadedMetadata,
           canplay: handleCanPlay,
           canplaythrough: handleCanPlayThrough,
           error: handleError,
           progress: handleProgress
         };
         
         Object.entries(eventListenersRef.current).forEach(([event, handler]) => {
           videoRef.current.addEventListener(event, handler);
         });
         
         // 设置视频属性
        videoRef.current.preload = 'metadata'; // 只预加载元数据
        videoRef.current.crossOrigin = 'anonymous';
        
        // 加载视频
        videoRef.current.load();
        console.log('Video loading started with streaming URL');
      }

      if (isMountedRef.current) {
        setError(null);
        requestInProgressRef.current = false;
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      console.error('Video loading error:', err);
      setError(err.message);
      setVideoUrl(null);
      setIsPlaying(false);
      setLoading(false);
      requestInProgressRef.current = false;
    }
  }, [cleanup]);

  // 处理播放/暂停
  const handlePlayPause = useCallback(() => {
    if (!videoRef.current || !camera?.video_dir) return;

    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      if (!videoUrl) {
        const startTime = currentTime.format('YYYY-MM-DD HH:mm:ss');
        console.log('Current time object:', currentTime);
        console.log('Formatted start time:', startTime);
        
        const url = `${config.API_BASE_URL}/api/video/stream?start_time=${encodeURIComponent(startTime)}&video_dir=${encodeURIComponent(camera.video_dir)}&playback_rate=${playbackRate}`;
        console.log('Generated URL:', url);
        
        loadVideo(url);
      } else {
        videoRef.current.play().catch(err => {
          console.error('Error playing video:', err);
          setError('视频播放失败');
          setIsPlaying(false);
        });
        setIsPlaying(true);
      }
    }
  }, [isPlaying, videoUrl, currentTime, camera, playbackRate, loadVideo]);

  // 加载新视频的函数
  const loadNewVideo = useCallback(() => {
    if (!camera?.video_dir) return;
    
    const startTime = currentTime.format('YYYY-MM-DD HH:mm:ss');
    console.log('loadNewVideo - Current time object:', currentTime);
    console.log('loadNewVideo - Formatted start time:', startTime);
    
    const url = `${config.API_BASE_URL}/api/video/stream?start_time=${encodeURIComponent(startTime)}&video_dir=${encodeURIComponent(camera.video_dir)}&playback_rate=${playbackRate}`;
    console.log('loadNewVideo - Generated URL:', url);
    
    loadVideo(url);
  }, [camera?.video_dir, currentTime, playbackRate, loadVideo]);

  // 只在时间或播放速率变化时加载新视频
  useEffect(() => {
    if (!isMountedRef.current || !camera?.video_dir) return;
    
    // 延迟加载，避免频繁请求
    const timeoutId = setTimeout(() => {
      if (isMountedRef.current) {
        loadNewVideo();
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [currentTime.format('YYYY-MM-DD HH:mm'), playbackRate, camera?.video_dir, loadNewVideo]);

  // 处理视频事件
  const handleVideoError = useCallback((e) => {
    console.error('Video error:', e.target.error);
    if (isMountedRef.current) {
      setError('视频播放错误');
      setLoading(false);
      setIsPlaying(false);
    }
  }, []);

  const handleVideoLoadStart = useCallback(() => {
    if (isMountedRef.current) {
      setLoading(true);
    }
  }, []);

  const handleVideoCanPlay = useCallback(() => {
    if (isMountedRef.current) {
      setLoading(false);
    }
  }, []);

  // 处理播放速度变化
  const handlePlaybackRateChange = useCallback((rate) => {
    setPlaybackRate(rate);
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
  }, []);

  // 处理日期导航
  const handleDateNavigation = useCallback((unit, direction) => {
    const newTime = direction === 'next' 
      ? currentTime.add(1, unit)
      : currentTime.subtract(1, unit);
    setCurrentTime(newTime);
  }, [currentTime]);

  // 添加临时时间状态用于拖拽过程中的显示
  const [tempCurrentTime, setTempCurrentTime] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // 处理时间轴拖拽过程中的变化（只更新显示，不加载视频）
  const handleTimelineChange = useCallback((event, value) => {
    if (!camera?.video_dir) return;
    
    // 将百分比转换为当天的具体时间
    const startOfDay = currentTime.startOf('day');
    const secondsInDay = (value / 100) * 86400; // 86400秒 = 24小时
    const newTime = startOfDay.add(secondsInDay, 'second');
    
    // 只在拖拽过程中更新临时时间，不加载视频
    setTempCurrentTime(newTime);
    setIsDragging(true);
  }, [camera?.video_dir, currentTime]);

  // 处理时间轴拖拽结束（实际加载视频）
  const handleTimelineChangeCommitted = useCallback((event, value) => {
    if (!camera?.video_dir) return;
    
    // 将百分比转换为当天的具体时间
    const startOfDay = currentTime.startOf('day');
    const secondsInDay = (value / 100) * 86400; // 86400秒 = 24小时
    const newTime = startOfDay.add(secondsInDay, 'second');
    
    // 更新实际时间并加载视频
    setCurrentTime(newTime);
    setTempCurrentTime(null);
    setIsDragging(false);
    setIsPlaying(false);
    
    // 清理当前视频
    cleanup();
    
    // 加载新视频
    const startTime = newTime.format('YYYY-MM-DD HH:mm:ss');
    console.log('Timeline change committed - New time:', startTime);
    
    const url = `${config.API_BASE_URL}/api/video/stream?start_time=${encodeURIComponent(startTime)}&video_dir=${encodeURIComponent(camera.video_dir)}&playback_rate=${playbackRate}`;
    console.log('Timeline change committed - Generated URL:', url);
    
    loadVideo(url);
  }, [camera?.video_dir, playbackRate, loadVideo, cleanup, currentTime]);

  // 计算时间轴位置
  const calculateTimelinePosition = useCallback(() => {
    const timeToUse = tempCurrentTime || currentTime;
    const startOfDay = timeToUse.startOf('day');
    const seconds = timeToUse.diff(startOfDay, 'second');
    return (seconds / 86400) * 100;
  }, [currentTime, tempCurrentTime]);

  // 如果没有camera对象，显示错误并返回
  if (!camera?.video_dir) {
    return (
      <Paper elevation={3} sx={{ p: 2, height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <Typography color="error" variant="h6">未找到摄像头信息</Typography>
        <Button 
          variant="contained" 
          startIcon={<ArrowBackIcon />} 
          onClick={() => navigate('/')}
          sx={{ mt: 2 }}
        >
          返回首页
        </Button>
      </Paper>
    );
  }

  return (
    <Paper elevation={3} sx={{ p: 2, height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Box display="flex" alignItems="center" mb={2}>
        <IconButton onClick={() => navigate('/')} sx={{ mr: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5">{camera?.name || '视频播放'}</Typography>
      </Box>

      {/* 视频播放区域 */}
      <Box sx={{ width: '100%', aspectRatio: '16/9', bgcolor: 'black', mb: 2, position: 'relative' }}>
        <video
          ref={videoRef}
          style={{ width: '100%', height: '100%', opacity: error ? 0 : 1 }}
          controls={false}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onError={handleVideoError}
          onLoadStart={handleVideoLoadStart}
          onCanPlay={handleVideoCanPlay}
          onWaiting={() => setLoading(true)}
          playsInline
          crossOrigin="anonymous"
          preload="metadata"
        />
        {loading && (
          <Box sx={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}>
            <CircularProgress size={64} thickness={5} />
          </Box>
        )}
        {error && (
          <Box sx={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2 }}>
            <Typography color="error" variant="h6">{error}</Typography>
          </Box>
        )}
      </Box>

      {/* 播放控制区域 */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <IconButton onClick={handlePlayPause} disabled={loading || !!error}>
          {isPlaying ? <Pause /> : <PlayArrow />}
        </IconButton>
        <Typography variant="body1">
          {(tempCurrentTime || currentTime).format('YYYY-MM-DD HH:mm:ss')}
        </Typography>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <Select
            value={playbackRate}
            onChange={(e) => handlePlaybackRateChange(e.target.value)}
            disabled={loading || !!error}
          >
            <MenuItem value={0.5}>0.5x</MenuItem>
            <MenuItem value={1}>1x</MenuItem>
            <MenuItem value={2}>2x</MenuItem>
            <MenuItem value={4}>4x</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* 日期导航 */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} justifyContent="center">
        <IconButton onClick={() => handleDateNavigation('month', 'prev')}>
          <CalendarMonth />
        </IconButton>
        <IconButton onClick={() => handleDateNavigation('day', 'prev')}>
          <NavigateBefore />
        </IconButton>
        <Typography variant="h6" sx={{ minWidth: 200, textAlign: 'center' }}>
          {(tempCurrentTime || currentTime).format('YYYY-MM-DD HH:mm:ss')}
        </Typography>
        <IconButton onClick={() => handleDateNavigation('day', 'next')}>
          <NavigateNext />
        </IconButton>
        <IconButton onClick={() => handleDateNavigation('month', 'next')}>
          <CalendarMonth />
        </IconButton>
      </Stack>

      {/* 时间轴 */}
      <Box sx={{ width: '100%', px: 2 }}>
        <Slider
          value={calculateTimelinePosition()}
          onChange={handleTimelineChange}
          onChangeCommitted={handleTimelineChangeCommitted}
          disabled={loading || !!error}
          sx={{
            '& .MuiSlider-thumb': {
              width: 12,
              height: 12,
            },
            '& .MuiSlider-track': {
              height: 4,
            },
            '& .MuiSlider-rail': {
              height: 4,
            },
          }}
        />
      </Box>
    </Paper>
  );
};

export default VideoPlayer; 