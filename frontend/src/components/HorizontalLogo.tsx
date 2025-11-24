// Horizontal Logo Component - Logo icon + text side by side
import { InfinityLogo } from './InfinityLogo';

interface HorizontalLogoProps {
  logoSize?: number;
  textSize?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  showText?: boolean;
}

export function HorizontalLogo({ 
  logoSize = 32, 
  textSize = 'lg',
  className = '',
  showText = true 
}: HorizontalLogoProps) {
  const textSizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
    xl: 'text-xl'
  };

  return (
    <div className={`flex items-center space-x-3 ${className}`}>
      <div className="flex-shrink-0">
        <InfinityLogo size={logoSize} />
      </div>
      {showText && (
        <span className={`font-semibold ${textSizeClasses[textSize]} text-gray-800`}>
          Eightfold AI
        </span>
      )}
    </div>
  );
}

