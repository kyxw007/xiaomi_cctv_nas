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

  // 清理函数
  const cleanup = useCallback(() => {
    console.log('Cleaning up resources...');
    
    if (abortControllerRef.current) {
      console.log('Aborting previous request...');
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    
    if (videoRef.current) {
      console.log('Cleaning up video element...');
      videoRef.current.pause();
      videoRef.current.removeAttribute('src');
      videoRef.current.load();
    }
    
    if (videoUrlRef.current) {
      console.log('Revoking blob URL...');
      URL.revokeObjectURL(videoUrlRef.current);
      videoUrlRef.current = null;
    }
    
    setVideoUrl(null);
    setLoading(false);
    setError(null);
    requestInProgressRef.current = false;
  }, []);

  // 组件卸载时清理
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, [cleanup]);

  // 加载视频
  const loadVideo = useCallback(async (url) => {
    if (!isMountedRef.current) {
      console.log('Component is unmounted, skipping video load');
      return;
    }

    if (requestInProgressRef.current) {
      console.log('Request already in progress, aborting previous request');
      cleanup();
    }

    console.log('Starting video load:', url);
    requestInProgressRef.current = true;
    setLoading(true);
    setError(null);

    try {
      // 创建新的 AbortController
      abortControllerRef.current = new AbortController();
      
      const response = await fetch(url, {
        signal: abortControllerRef.current.signal,
        headers: {
          'Range': 'bytes=0-',
          'Accept': 'video/mp4,video/*;q=0.9,*/*;q=0.8'
        }
      });

      if (!isMountedRef.current) {
        console.log('Component unmounted during fetch');
        return;
      }

      if (!response.ok) {
        let errorMessage = '加载视频失败';
        try {
          const data = await response.json();
          errorMessage = data.message || errorMessage;
        } catch (e) {
          // 如果响应不是 JSON，使用默认错误消息
        }
        throw new Error(errorMessage);
      }

      // 直接获取视频数据
      const blob = await response.blob();
      console.log('Received video blob:', blob.size, 'bytes, type:', blob.type);
      
      // 检查 blob 大小
      if (blob.size < 10000) {  // 小于10KB可能是错误
        console.warn('Video blob size is very small, might be an error response');
        const text = await blob.text();
        console.log('Blob content:', text);
        
        if (text.includes('error') || text.includes('Error')) {
          throw new Error('服务器返回错误：' + text);
        }
      }

      if (!isMountedRef.current) {
        console.log('Component unmounted after blob received');
        return;
      }

      // 清理旧的 blob URL
      if (videoUrlRef.current) {
        URL.revokeObjectURL(videoUrlRef.current);
      }

      const blobUrl = URL.createObjectURL(blob);
      videoUrlRef.current = blobUrl;
      setVideoUrl(blobUrl);

      // 设置视频源，但不自动播放
      if (videoRef.current && isMountedRef.current) {
        videoRef.current.pause();
        videoRef.current.src = blobUrl;
        
        // 添加更多事件监听器
        videoRef.current.addEventListener('loadstart', () => {
          console.log('Video loadstart event');
        });
        
        videoRef.current.addEventListener('loadedmetadata', () => {
          console.log('Video metadata loaded:', {
            duration: videoRef.current.duration,
            videoWidth: videoRef.current.videoWidth,
            videoHeight: videoRef.current.videoHeight
          });
        });
        
        videoRef.current.addEventListener('canplay', () => {
          console.log('Video can play');
        });
        
        videoRef.current.addEventListener('canplaythrough', () => {
          console.log('Video can play through');
        });
        
        videoRef.current.load();
        console.log('Video loaded, ready to play');
      }

      if (isMountedRef.current) {
        setError(null);
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      if (err.name === 'AbortError') {
        console.log('Request was aborted');
        return;
      }
      console.error('Video loading error:', err);
      setError(err.message);
      setVideoUrl(null);
      setIsPlaying(false);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        requestInProgressRef.current = false;
      }
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
  }, [currentTime.format('YYYY-MM-DD HH:mm'), playbackRate, camera?.video_dir]);

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

  // 处理时间轴变化
  const handleTimelineChange = useCallback((event, newValue) => {
    const startOfDay = currentTime.startOf('day');
    const seconds = Math.floor((newValue / 100) * 86400);
    const newTime = startOfDay.add(seconds, 'second');
    setCurrentTime(newTime);
  }, [currentTime]);

  // 计算时间轴位置
  const calculateTimelinePosition = useCallback(() => {
    const startOfDay = currentTime.startOf('day');
    const seconds = currentTime.diff(startOfDay, 'second');
    return (seconds / 86400) * 100;
  }, [currentTime]);

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
          autoPlay
          playsInline
          crossOrigin="anonymous"
          preload="auto"
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
          {currentTime.format('YYYY-MM-DD HH:mm:ss')}
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
          {currentTime.format('YYYY-MM-DD HH:mm:ss')}
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