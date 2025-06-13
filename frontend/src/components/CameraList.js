import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Paper,
  CircularProgress
} from '@mui/material';
import VideocamIcon from '@mui/icons-material/Videocam';
import axios from 'axios';
import config from '../config';

// 创建 axios 实例
const api = axios.create({
  baseURL: config.API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: false
});

const CameraList = () => {
  const navigate = useNavigate();
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchCameras = async () => {
      try {
        const response = await api.get('/api/cameras');
        setCameras(response.data.cameras);
        setError(null);
      } catch (error) {
        console.error('Error fetching cameras:', error);
        setError('获取摄像头列表失败');
      } finally {
        setLoading(false);
      }
    };

    fetchCameras();
  }, []);

  const handleCameraClick = (camera) => {
    navigate(`/camera/${camera.id}`, { state: { camera } });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" py={2}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" py={2}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Paper elevation={3} sx={{ mt: 4, mb: 4 }}>
      <Box p={2}>
        <Typography variant="h6" gutterBottom>
          摄像头列表
        </Typography>
        <List>
          {cameras.map((camera, index) => (
            <React.Fragment key={camera.id}>
              <ListItem 
                button 
                onClick={() => handleCameraClick(camera)}
                sx={{ 
                  '&:hover': { 
                    backgroundColor: 'action.hover',
                    cursor: 'pointer'
                  }
                }}
              >
                <ListItemIcon>
                  <VideocamIcon />
                </ListItemIcon>
                <ListItemText
                  primary={camera.name}
                  secondary={`存储目录: ${camera.video_dir}`}
                />
              </ListItem>
              {index < cameras.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>
      </Box>
    </Paper>
  );
};

export default CameraList; 