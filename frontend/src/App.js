import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Container, CssBaseline, ThemeProvider, createTheme } from '@mui/material';
import CameraList from './components/CameraList';
import VideoPlayer from './components/VideoPlayer';

const theme = createTheme({
  palette: {
    mode: 'light',
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Container maxWidth="lg">
          <Routes>
            <Route path="/" element={<CameraList />} />
            <Route path="/camera/:id" element={<VideoPlayer />} />
          </Routes>
        </Container>
      </Router>
    </ThemeProvider>
  );
}

export default App; 