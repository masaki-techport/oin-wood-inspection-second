import React, { useState, useRef, useEffect, useCallback } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { AlertTriangle, X, Maximize2, Minimize2 } from 'lucide-react';

interface ResizableCameraModalProps {
    isOpen: boolean;
    onClose: () => void;
    image: string | null;
    isConnected: boolean | null;
    selectedCameraType: string;
    droppedFrame?: boolean;
}

const ResizableCameraModal: React.FC<ResizableCameraModalProps> = ({
    isOpen,
    onClose,
    image,
    isConnected,
    selectedCameraType,
    droppedFrame = false
}) => {
    const [size, setSize] = useState({ width: 0, height: 0 });
    const [imageAspectRatio, setImageAspectRatio] = useState(16/9); // Default aspect ratio
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [isResizing, setIsResizing] = useState(false);
    const [resizeHandle, setResizeHandle] = useState('');
    const [isMaximized, setIsMaximized] = useState(false);
    const modalRef = useRef<HTMLDivElement>(null);
    const startPos = useRef({ x: 0, y: 0 });
    const startSize = useRef({ width: 0, height: 0 });
    const startMousePos = useRef({ x: 0, y: 0 });

    // Initialize modal size and position based on image aspect ratio
    useEffect(() => {
        if (isOpen && !isMaximized) {
            const screenWidth = window.innerWidth;
            const screenHeight = window.innerHeight;
            
            // Calculate dimensions that fit within 80% of screen while maintaining aspect ratio
            let initialWidth = Math.floor(screenWidth * 0.8);
            let initialHeight = Math.floor(initialWidth / imageAspectRatio);
            
            // If height exceeds 80% of screen height, recalculate based on height
            if (initialHeight > screenHeight * 0.8) {
                initialHeight = Math.floor(screenHeight * 0.8);
                initialWidth = Math.floor(initialHeight * imageAspectRatio);
            }
            
            setSize({
                width: initialWidth,
                height: initialHeight
            });
            
            setPosition({
                x: Math.floor((screenWidth - initialWidth) / 2),
                y: Math.floor((screenHeight - initialHeight) / 2)
            });
        }
    }, [isOpen, isMaximized, imageAspectRatio]);

    // Handle escape key
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onClose();
            }
        };

        if (isOpen) {
            document.addEventListener('keydown', handleEscape);
            document.body.style.overflow = 'hidden';
        }

        return () => {
            document.removeEventListener('keydown', handleEscape);
            document.body.style.overflow = 'unset';
        };
    }, [isOpen, onClose]);

    // Mouse handlers for dragging
    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        if (isMaximized) return;
        
        const rect = modalRef.current?.getBoundingClientRect();
        if (!rect) return;

        const { clientX, clientY } = e;
        const { left, top, right, bottom } = rect;
        
        // Determine if clicking on resize handles (edges)
        const edgeThreshold = 10;
        const isNearLeft = clientX - left < edgeThreshold;
        const isNearRight = right - clientX < edgeThreshold;
        const isNearTop = clientY - top < edgeThreshold;
        const isNearBottom = bottom - clientY < edgeThreshold;

        if (isNearLeft || isNearRight || isNearTop || isNearBottom) {
            // Start resizing
            setIsResizing(true);
            let handle = '';
            if (isNearTop && isNearLeft) handle = 'nw';
            else if (isNearTop && isNearRight) handle = 'ne';
            else if (isNearBottom && isNearLeft) handle = 'sw';
            else if (isNearBottom && isNearRight) handle = 'se';
            else if (isNearTop) handle = 'n';
            else if (isNearBottom) handle = 's';
            else if (isNearLeft) handle = 'w';
            else if (isNearRight) handle = 'e';
            
            setResizeHandle(handle);
            startPos.current = { x: position.x, y: position.y };
            startSize.current = { width: size.width, height: size.height };
            startMousePos.current = { x: clientX, y: clientY };
        } else {
            // Start dragging
            setIsDragging(true);
            startPos.current = { x: position.x, y: position.y };
            startMousePos.current = { x: clientX, y: clientY };
        }

        e.preventDefault();
    }, [position, size, isMaximized]);

    const handleMouseMove = useCallback((e: MouseEvent) => {
        if (isMaximized) return;

        const { clientX, clientY } = e;
        const deltaX = clientX - startMousePos.current.x;
        const deltaY = clientY - startMousePos.current.y;

        if (isDragging) {
            setPosition({
                x: Math.max(0, Math.min(window.innerWidth - size.width, startPos.current.x + deltaX)),
                y: Math.max(0, Math.min(window.innerHeight - size.height, startPos.current.y + deltaY))
            });
        } else if (isResizing) {
            const minWidth = 300;
            const minHeight = 200;
            let newWidth = startSize.current.width;
            let newHeight = startSize.current.height;
            let newX = startPos.current.x;
            let newY = startPos.current.y;
            
            // Determine if we're resizing width or height directly
            const isResizingWidth = resizeHandle.includes('e') || resizeHandle.includes('w');
            const isResizingHeight = resizeHandle.includes('n') || resizeHandle.includes('s');
            
            // Process horizontal resize
            if (isResizingWidth) {
                if (resizeHandle.includes('e')) {
                    newWidth = Math.max(minWidth, startSize.current.width + deltaX);
                }
                if (resizeHandle.includes('w')) {
                    newWidth = Math.max(minWidth, startSize.current.width - deltaX);
                    newX = startPos.current.x + (startSize.current.width - newWidth);
                }
                // Maintain aspect ratio by adjusting height
                newHeight = newWidth / imageAspectRatio;
            }
            
            // Process vertical resize
            if (isResizingHeight) {
                if (resizeHandle.includes('s')) {
                    newHeight = Math.max(minHeight, startSize.current.height + deltaY);
                }
                if (resizeHandle.includes('n')) {
                    newHeight = Math.max(minHeight, startSize.current.height - deltaY);
                    newY = startPos.current.y + (startSize.current.height - newHeight);
                }
                // Maintain aspect ratio by adjusting width
                newWidth = newHeight * imageAspectRatio;
            }

            // Ensure modal stays within screen bounds
            if (newX + newWidth > window.innerWidth) {
                newWidth = window.innerWidth - newX;
            }
            if (newY + newHeight > window.innerHeight) {
                newHeight = window.innerHeight - newY;
            }
            if (newX < 0) {
                newWidth += newX;
                newX = 0;
            }
            if (newY < 0) {
                newHeight += newY;
                newY = 0;
            }

            setSize({ width: newWidth, height: newHeight });
            setPosition({ x: newX, y: newY });
        }
    }, [isDragging, isResizing, resizeHandle, size, isMaximized]);

    const handleMouseUp = useCallback(() => {
        setIsDragging(false);
        setIsResizing(false);
        setResizeHandle('');
    }, []);

    useEffect(() => {
        if (isDragging || isResizing) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
            document.body.style.userSelect = 'none';
            document.body.style.cursor = isResizing ? 
                resizeHandle.includes('n') || resizeHandle.includes('s') ? 'ns-resize' :
                resizeHandle.includes('e') || resizeHandle.includes('w') ? 'ew-resize' :
                resizeHandle.includes('nw') || resizeHandle.includes('se') ? 'nw-resize' :
                'ne-resize' : 'move';
        }

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            document.body.style.userSelect = '';
            document.body.style.cursor = '';
        };
    }, [isDragging, isResizing, handleMouseMove, handleMouseUp, resizeHandle]);

    // Toggle maximize/restore
    const toggleMaximize = () => {
        setIsMaximized(!isMaximized);
        if (!isMaximized) {
            // Calculate maximized dimensions that maintain aspect ratio
            const screenWidth = window.innerWidth;
            const screenHeight = window.innerHeight;
            
            // Try fitting to width first
            let maxWidth = screenWidth;
            let maxHeight = Math.floor(maxWidth / imageAspectRatio);
            
            // If height exceeds screen height, fit to height instead
            if (maxHeight > screenHeight) {
                maxHeight = screenHeight;
                maxWidth = Math.floor(maxHeight * imageAspectRatio);
            }
            
            // Center the image in the screen
            const xPos = Math.max(0, Math.floor((screenWidth - maxWidth) / 2));
            const yPos = Math.max(0, Math.floor((screenHeight - maxHeight) / 2));
            
            // Update position and size
            setPosition({ x: xPos, y: yPos });
            setSize({ width: maxWidth, height: maxHeight });
        }
    };

    if (!isOpen) return null;

    const modalStyle = {
        width: `${size.width}px`,
        height: `${size.height}px`,
        left: `${position.x}px`,
        top: `${position.y}px`
    };

    return (
        <div className="fixed inset-0 z-50 bg-black bg-opacity-50">
            <div
                ref={modalRef}
                className="absolute bg-white rounded-lg shadow-2xl overflow-hidden"
                style={modalStyle}
                onMouseDown={handleMouseDown}
            >
                {/* Title Bar */}
                <div className="bg-gray-800 text-white px-4 py-2 flex justify-between items-center select-none">
                    <h3 className="text-lg font-semibold">
                        {selectedCameraType === 'webcam' ? 'ウェブカメラ' : 
                         selectedCameraType === 'usb' ? 'USBカメラ' : 'Baslerカメラ'}
                    </h3>
                    <div className="flex gap-2">
                        <button
                            onClick={toggleMaximize}
                            className="hover:bg-gray-700 p-1 rounded"
                            onMouseDown={(e) => e.stopPropagation()}
                        >
                            {isMaximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                        </button>
                        <button
                            onClick={onClose}
                            className="hover:bg-gray-700 p-1 rounded"
                            onMouseDown={(e) => e.stopPropagation()}
                        >
                            <X size={16} />
                        </button>
                    </div>
                </div>

                {/* Camera Content */}
                <div className="flex-1 h-full bg-gray-900" style={{ height: `calc(${modalStyle.height} - 48px)` }}>
                    <TransformWrapper>
                        {() => (
                            <TransformComponent>
                                {image ? (
                                    <div className="relative w-full h-full">
                                        <img
                                            src={image}
                                            alt="Camera Feed"
                                            className="w-full h-full object-contain"
                                            draggable={false}
                                            onLoad={(e) => {
                                                const img = e.target as HTMLImageElement;
                                                if (img.naturalWidth && img.naturalHeight) {
                                                    setImageAspectRatio(img.naturalWidth / img.naturalHeight);
                                                }
                                            }}
                                        />
                                        {droppedFrame && (
                                            <div className="absolute top-4 right-4 bg-yellow-100 border border-yellow-400 text-yellow-800 px-3 py-2 rounded flex items-center gap-2 z-20">
                                                <AlertTriangle className="w-4 h-4" />
                                                <span>フレームドロップ</span>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center bg-gray-800">
                                        {isConnected === false ? (
                                            <div className="text-center text-white">
                                                <p className="text-xl mb-2">
                                                    {selectedCameraType === 'webcam' ? 'ウェブカメラ' : 
                                                     selectedCameraType === 'usb' ? 'USBカメラ' : 'Baslerカメラ'}
                                                </p>
                                                <p className="text-red-400">未接続</p>
                                            </div>
                                        ) : (
                                            <div className="text-center text-white">
                                                <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-white mx-auto mb-4"></div>
                                                <p className="text-lg">取得中...</p>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </TransformComponent>
                        )}
                    </TransformWrapper>
                </div>

                {/* Resize handles (invisible but functional) */}
                {!isMaximized && (
                    <>
                        {/* Corner handles */}
                        <div className="absolute top-0 left-0 w-3 h-3 cursor-nw-resize"></div>
                        <div className="absolute top-0 right-0 w-3 h-3 cursor-ne-resize"></div>
                        <div className="absolute bottom-0 left-0 w-3 h-3 cursor-sw-resize"></div>
                        <div className="absolute bottom-0 right-0 w-3 h-3 cursor-se-resize"></div>
                        
                        {/* Edge handles */}
                        <div className="absolute top-0 left-3 right-3 h-1 cursor-n-resize"></div>
                        <div className="absolute bottom-0 left-3 right-3 h-1 cursor-s-resize"></div>
                        <div className="absolute left-0 top-3 bottom-3 w-1 cursor-w-resize"></div>
                        <div className="absolute right-0 top-3 bottom-3 w-1 cursor-e-resize"></div>
                    </>
                )}
            </div>
        </div>
    );
};

export default ResizableCameraModal;