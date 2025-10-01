import React from 'react';
import { cn } from '@/utils/cn';

interface StandardHeaderProps {
  title: string;
  subtitle?: string;
  showLogo?: boolean;
  variant?: 'primary' | 'modal' | 'page';
  className?: string;
  children?: React.ReactNode;
}

/**
 * Standardized header component for consistent styling across the application
 * 
 * Features:
 * - Consistent color scheme (cyan-800 background, white text)
 * - Responsive typography using CSS custom properties
 * - Optional OIN logo with consistent styling
 * - Multiple variants for different use cases
 * - Proper spacing and alignment
 */
const StandardHeader: React.FC<StandardHeaderProps> = ({
  title,
  subtitle,
  showLogo = true,
  variant = 'primary',
  className,
  children
}) => {
  // Base styles that apply to all variants - reduced height and improved alignment
  const baseStyles = "header-primary flex items-center min-h-12";

  // Variant-specific styles with logo on left, title centered
  const variantStyles = {
    primary: "text-responsive-2xl py-2 px-4 justify-between", // Main app header - logo left, title center
    modal: "text-responsive-xl py-2 px-4 justify-between flex-shrink-0", // Modal headers - keep between for close button
    page: "text-responsive-xl py-2 px-4 justify-center" // Page headers - centered
  };

  // Logo component with image from public folder - enhanced to remove white background
  const LogoComponent = () => (
    <img
      src="/logo-OiN.png"
      alt="OiN Logo"
      className="header-logo-enhanced"
      style={{
        // Additional inline style to help remove white background
        filter: 'drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1)) brightness(1.1) contrast(1.2)',
        background: 'transparent'
      }}
    />
  );

  // Title section with intelligent spacing between system name and view name
  const TitleSection = () => {
    // Parse title to add proper spacing between system name and view name
    const formatTitle = (titleText: string) => {
      const systemName = '木材検査システム';
      if (titleText.includes(systemName)) {
        // Remove existing spacing characters and split properly
        const cleanTitle = titleText.replace(/[\s　]+/g, ' ').trim();
        const afterSystemName = cleanTitle.substring(systemName.length).trim();

        if (afterSystemName) {
          return (
            <>
              {systemName}
              <span className="mx-4">　</span>
              {afterSystemName}
            </>
          );
        }
      }
      return titleText;
    };

    return (
      <div className="flex flex-col justify-center">
        <span className="header-title leading-tight">{formatTitle(title)}</span>
        {subtitle && (
          <span className="header-subtitle leading-tight">
            {subtitle}
          </span>
        )}
      </div>
    );
  };

  return (
    <div className={cn(baseStyles, variantStyles[variant], className)}>
      {variant === 'primary' ? (
        // Primary layout: logo on left, title centered, space for future content on right
        <>
          {/* Left: Logo */}
          <div className="flex items-center">
            {showLogo && <LogoComponent />}
          </div>

          {/* Center: Title */}
          <div className="flex-1 flex justify-center">
            <TitleSection />
          </div>

          {/* Right: Children or empty space */}
          <div className="flex items-center space-x-2 min-w-0">
            {children}
          </div>
        </>
      ) : variant === 'modal' ? (
        // Modal layout: logo + title on left, children on right
        <>
          <div className="flex items-center h-full">
            {showLogo && <LogoComponent />}
            <TitleSection />
          </div>
          {children && (
            <div className="flex items-center space-x-2">
              {children}
            </div>
          )}
        </>
      ) : (
        // Page layout: centered content
        <div className="flex items-center justify-center h-full w-full">
          {showLogo && <LogoComponent />}
          <TitleSection />
          {children && (
            <div className="flex items-center space-x-2 ml-4">
              {children}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default StandardHeader;
