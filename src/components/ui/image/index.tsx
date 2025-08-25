import React, { useState } from 'react';
import { CircularProgress } from '@mui/material';

const Image: React.FC<{ src: string; alt: string; className: string }> = ({
  src,
  alt,
  className,
}) => {
  const [isLoading, setLoading] = useState(true);

  const handleImageLoaded = () => {
    setLoading(false);
  };

  const handleImageError = () => {
    setLoading(false);
  };

  return (
    <div>
      {isLoading && (
        <div className="flex justify-center">
          <CircularProgress />
        </div>
      )}
      <img
        src={src}
        alt={alt}
        onLoad={handleImageLoaded}
        onError={handleImageError}
        className={`${isLoading ? 'hidden' : 'block'} ${className}`}
      />
    </div>
  );
};

export default Image;
