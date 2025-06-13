import React from 'react';
import { Box, AppBar, Toolbar, Typography, Container } from '@mui/material';
import { useTheme, useMediaQuery } from '@mui/material';

const Layout = ({ children }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant={isMobile ? "h6" : "h4"} component="div" sx={{ flexGrow: 1 }}>
            监控视频查看系统
          </Typography>
        </Toolbar>
      </AppBar>
      <Container 
        component="main" 
        maxWidth="xl" 
        sx={{ 
          flexGrow: 1, 
          py: 3,
          px: { xs: 2, sm: 3, md: 4 }
        }}
      >
        {children}
      </Container>
    </Box>
  );
};

export default Layout; 