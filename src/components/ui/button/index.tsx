import { Button as MButton, ButtonProps } from '@mui/material';
import React from 'react';

const Button: React.FC<ButtonProps> = ({ children, sx, ...rest }) => (
  <MButton
    fullWidth
    variant="contained"
    color="primary"
    sx={{ fontSize: '25px', ...sx }}
    {...rest}
  >
    {children}
  </MButton>
);
export default Button;
