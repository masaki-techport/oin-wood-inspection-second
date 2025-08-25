import React from 'react';
import { PresentationImageCardProps } from '../../types';
import { getImageUrl } from '../../utils';

/**
 * Component for displaying a presentation image card
 */
const PresentationImageCard: React.FC<PresentationImageCardProps> = ({ 
  groupName, 
  imagePath,
  inspectionId,
  onImageTest 
}) => {
  return (
    <div className="bg-white border-2 border-gray-400 text-center rounded-lg shadow-md">
      <div className="bg-gray-100 text-xl font-bold py-3 border-b-2 border-gray-400">
        {groupName}
      </div>
      <div className="p-2">
        {imagePath ? (
          <div className="w-full h-20 mx-auto relative flex items-center justify-center">
            <img 
              src={getImageUrl(imagePath, inspectionId)}
              alt={`Group ${groupName}`}
              className="max-w-full max-h-full object-contain"
              loading="lazy" // Use lazy loading to improve performance
              decoding="async" // Use async decoding for better performance
              onLoad={() => {
                console.log(`✅ Image for group ${groupName} loaded successfully`);
                console.log(`✅ Loaded image path: ${imagePath}`);
              }}
              onError={(e) => {
                console.error(`❌ Failed to load image for group ${groupName}:`, imagePath);
                
                // Show the direct URL for debugging
                const url = getImageUrl(imagePath, inspectionId);
                console.error(`❌ Direct URL that failed: ${url}`);
                
                // Hide the failed image
                e.currentTarget.style.display = 'none';
                
                // Try alternative URL constructions
                console.log(`🔄 Attempting alternative image loading approaches for group ${groupName}...`);
                
                const tryAlternativeUrl = (altUrl: string, description: string, delay: number = 0) => {
                  setTimeout(() => {
                    console.log(`🔄 Trying ${description}: ${altUrl}`);
                    
                    const altImg = document.createElement('img');
                    altImg.src = altUrl;
                    altImg.className = 'max-w-full max-h-full object-contain';
                    altImg.alt = `Group ${groupName}`;
                    
                    altImg.onload = () => {
                      console.log(`✅ ${description} loaded successfully for group ${groupName}`);
                      // Remove any other failed attempts
                      const container = e.currentTarget.parentElement;
                      if (container) {
                        const existingImages = container.querySelectorAll('img');
                        existingImages.forEach((img, index) => {
                          if (index > 0 && img !== altImg) { // Keep the first (original) and the successful one
                            img.remove();
                          }
                        });
                      }
                    };
                    
                    altImg.onerror = () => {
                      console.error(`❌ ${description} also failed for group ${groupName}`);
                      altImg.remove();
                    };
                    
                    e.currentTarget.parentElement?.appendChild(altImg);
                  }, delay);
                };
                
                // Try different URL constructions with delays to avoid overwhelming the server
                let delay = 100;
                
                if (imagePath.startsWith('inspection/')) {
                  // Try with src-api prefix
                  const altUrl1 = `/api/file?path=${encodeURIComponent(`src-api/data/images/${imagePath}`)}&convert=jpg`;
                  tryAlternativeUrl(altUrl1, 'src-api prefixed path', delay);
                  delay += 200;
                }
                
                // Extract filename and try direct filename approach
                const filename = imagePath.split(/[\\/]/).pop();
                if (filename) {
                  const altUrl2 = `/api/file?path=${encodeURIComponent(filename)}&convert=jpg`;
                  tryAlternativeUrl(altUrl2, 'filename only', delay);
                  delay += 200;
                  
                  // Try with date folder if we can extract it
                  const dateMatch = imagePath.match(/(\d{8}_\d{4})/);
                  if (dateMatch) {
                    const dateFolder = dateMatch[1];
                    const altUrl3 = `/api/file?path=${encodeURIComponent(`src-api/data/images/inspection/${dateFolder}/${filename}`)}&convert=jpg`;
                    tryAlternativeUrl(altUrl3, 'date folder path', delay);
                    delay += 200;
                  }
                }
                
                // Add loading gif as final fallback after all attempts
                setTimeout(() => {
                  const container = e.currentTarget.parentElement;
                  if (container && container.children.length === 1) { // Only the hidden original image
                    console.log(`⏳ Adding loading gif fallback for group ${groupName}`);
                    const loadingImg = document.createElement('img');
                    loadingImg.src = '/image-loading.gif';
                    loadingImg.className = 'max-w-full max-h-full object-contain';
                    loadingImg.alt = 'Loading...';
                    container.appendChild(loadingImg);
                  }
                }, delay + 500);
              }}
              onClick={onImageTest && imagePath ? () => onImageTest(imagePath) : undefined}
              style={onImageTest ? { cursor: 'pointer' } : undefined}
            />
          </div>
        ) : (
          <div className="w-full h-10 bg-yellow-300 border-2 border-gray-400 mx-auto relative rounded">
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-3 h-3 bg-black rounded-full"></div>
          </div>
        )}
      </div>
    </div>
  );
};

export default React.memo(PresentationImageCard);