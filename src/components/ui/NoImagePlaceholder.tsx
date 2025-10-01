import React from 'react';

interface NoImagePlaceholderProps {
  className?: string;
  style?: React.CSSProperties;
  alt?: string;
  onClick?: () => void;
}

/**
 * Reusable component for displaying no-image placeholder with consistent styling
 * Shows the no-image.png image with grey border when no image is available
 * This component should not be clickable by default - no-image states are not interactive
 */
const NoImagePlaceholder: React.FC<NoImagePlaceholderProps> = ({
  className = '',
  style = {},
  alt = 'No Image',
  onClick
}) => {
  return (
    <div
      className={`w-full h-full flex items-center justify-center bg-gray-100 rounded no-image-placeholder ${className}`}
      style={{
        cursor: 'default', // Explicitly set to default cursor to indicate non-clickable
        ...style
      }}
      // Remove onClick handler - no-image states should not be clickable
      // onClick={onClick}
    >
      <img
        src="/no-image.png"
        alt={alt}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          maxWidth: '80%',
          maxHeight: '80%'
        }}
      />
    </div>
  );
};

export default NoImagePlaceholder;
