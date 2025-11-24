// Infinity Logo Component - Uses uploaded infinity symbol image
import React, { useState } from 'react';

interface InfinityLogoProps {
  size?: number;
  className?: string;
}

export function InfinityLogo({ size = 24, className = '' }: InfinityLogoProps) {
  const [imageError, setImageError] = useState(false);
  const logoSrc = '/assets/infinity-logo.png';
  const gradientId = `infinityGradient-${size}-${Math.random()}`;
  
  // If image fails to load, show SVG fallback
  if (imageError) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        className={className}
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#00BCD4" />
            <stop offset="25%" stopColor="#2196F3" />
            <stop offset="50%" stopColor="#9C27B0" />
            <stop offset="75%" stopColor="#FF4081" />
            <stop offset="100%" stopColor="#FF7043" />
          </linearGradient>
        </defs>
        <path
          d="M12 12C14.7614 12 17 9.76142 17 7C17 4.23858 14.7614 2 12 2C9.23858 2 7 4.23858 7 7C7 9.76142 9.23858 12 12 12ZM12 12C9.23858 12 7 14.2386 7 17C7 19.7614 9.23858 22 12 22C14.7614 22 17 19.7614 17 17C17 14.2386 14.7614 12 12 12Z"
          stroke={`url(#${gradientId})`}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    );
  }
  
  return (
    <img
      src={logoSrc}
      alt="Infinity Logo"
      width={size}
      height={size}
      className={className}
      style={{
        objectFit: 'contain',
        imageRendering: 'high-quality'
      }}
      onError={() => setImageError(true)}
    />
  );
}

