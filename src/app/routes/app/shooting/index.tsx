import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { AlertTriangle, Camera, Wifi, Usb, Save, Settings } from 'lucide-react';
import { useSaveImage } from '@/features/inspections/api/save-image';
import { useNotifications } from '@/components/ui/notifications';
import { getBaslerConfig } from '@/config/camera-config';

type CameraType = 'basler' | 'webcam' | 'usb';

const ShootingScreen = () => {
    const [selectedCameraType, setSelectedCameraType] = useState<CameraType>('basler');
    const [status, setStatus] = useState('待機中');
    const [image, setImage] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState<boolean | null>(null);
    const [imageCount, setImageCount] = useState(0);
    const videoRef = useRef<HTMLVideoElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const resetTransformRef = useRef<(() => void) | null>(null);
    const droppedRef = useRef(false);
    const [droppedFrame, setDroppedFrame] = useState(false);
    const { addNotification } = useNotifications();

    const { mutate: saveImage } = useSaveImage({
        mutationConfig: {
            onSuccess: (res) => {
                console.log('保存完了:', res.path);
                setImageCount(prev => prev + 1);
                addNotification({
                    type: 'success',
                    title: '画像保存完了',
                    message: `画像を保存しました (${imageCount + 1}枚目)`,
                });
            },
            onError: (err) => {
                const message =
                    (err as any)?.response?.data?.error ??
                    (err as { message?: string })?.message;

                addNotification({
                    type: 'error',
                    title: '画像保存エラー',
                    message:
                        message === 'Camera not connected'
                            ? 'カメラが接続されていません'
                            : message === 'Failed to save image'
                                ? 'カメラ画像が取得できません'
                                : '不明なエラーが発生しました',
                });
            },
        },
    });

    // Basler camera functions
    const fetchBaslerImage = async () => {
        const config = getBaslerConfig();
        try {
            const res = await axios.get(`${config.apiBaseUrl}${config.endpoints.snapshot}`);
            if (res.data.image) {
                setImage(`data:image/jpeg;base64,${res.data.image}`);
                if (droppedRef.current) {
                    droppedRef.current = false;
                    setDroppedFrame(false);
                }
            } else {
                console.warn('画像データが空です');
            }
        } catch (err: any) {
            if (err.response?.status === 400) {
                console.warn('カメラ未接続');
            } else if (err.response?.status === 500) {
                console.warn('画像取得失敗（フレームなし）');
                droppedRef.current = true;
                setDroppedFrame(true);
            } else {
                console.error('fetchBaslerImage失敗:', err);
            }
        }
    };

    // Webcam/USB camera functions
    const initWebcam = async () => {
        try {
            // Stop existing stream if any
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
            }

            const constraints: MediaStreamConstraints = {
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: 'environment'
                },
                audio: false
            };

            let stream: MediaStream;
            try {
                stream = await navigator.mediaDevices.getUserMedia(constraints);
            } catch (err) {
                console.warn('Failed with preferred constraints, trying fallback');
                stream = await navigator.mediaDevices.getUserMedia({
                    video: true,
                    audio: false
                });
            }

            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
            }
            setIsConnected(true);
        } catch (err) {
            console.error('Webcam initialization failed:', err);
            setIsConnected(false);
        }
    };

    const stopWebcam = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }
        setIsConnected(false);
    };

    const initBasler = async () => {
        const config = getBaslerConfig();
        try {
            // 残っている場合は停止して切断する
            await axios.post(`${config.apiBaseUrl}${config.endpoints.stop}`, {}).catch(() => { });
            await axios.post(`${config.apiBaseUrl}${config.endpoints.disconnect}`, {}).catch(() => { });

            // カメラに接続する
            await axios.post(`${config.apiBaseUrl}${config.endpoints.connect}`);

            // 接続を確認する
            const res = await axios.get(`${config.apiBaseUrl}${config.endpoints.isConnected}`);
            const connected = res.data.connected === true;
            setIsConnected(connected);

            if (!connected) return;

            // 接続が成功した場合は画像の取得を開始する
            await axios.post(`${config.apiBaseUrl}${config.endpoints.start}`);
            await fetchBaslerImage();
            intervalRef.current = setInterval(fetchBaslerImage, config.pollInterval);

        } catch (err) {
            console.error('Basler camera initialization failed:', err);
            setIsConnected(false);
        }
    };

    const stopBasler = async () => {
        const config = getBaslerConfig();
        if (intervalRef.current) clearInterval(intervalRef.current);
        await axios.post(`${config.apiBaseUrl}${config.endpoints.stop}`, {}).catch(() => { });
        await axios.post(`${config.apiBaseUrl}${config.endpoints.disconnect}`, {}).catch(() => { });
    };

    const initCamera = async () => {
        setStatus('接続中');
        setIsConnected(null);
        setImage(null);

        if (selectedCameraType === 'basler') {
            await initBasler();
        } else {
            await initWebcam();
        }
        setStatus('待機中');
    };

    const stopCamera = async () => {
        if (selectedCameraType === 'basler') {
            await stopBasler();
        } else {
            stopWebcam();
        }
    };

    useEffect(() => {
        initCamera();

        return () => {
            stopCamera();
        };
    }, [selectedCameraType]);

    const handleCameraTypeChange = (type: CameraType) => {
        setSelectedCameraType(type);
        setImageCount(0);
    };

    const handleCapture = () => {
        if (selectedCameraType === 'basler') {
            saveImage();
        } else {
            // For webcam/USB, capture the current video frame
            if (videoRef.current) {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    canvas.width = videoRef.current.videoWidth;
                    canvas.height = videoRef.current.videoHeight;
                    ctx.drawImage(videoRef.current, 0, 0);
                    
                    // Convert to base64 and set as image
                    const dataURL = canvas.toDataURL('image/jpeg');
                    setImage(dataURL);
                    
                    // Save the image (you could implement a separate save endpoint for webcam images)
                    saveImage();
                }
            }
        }
    };

    const handleReset = () => {
        setImageCount(0);
        resetTransformRef.current?.();
    };

    const getCameraIcon = (type: CameraType) => {
        switch (type) {
            case 'basler': return <Camera size={24} />;
            case 'webcam': return <Wifi size={24} />;
            case 'usb': return <Usb size={24} />;
        }
    };

    const getCameraName = (type: CameraType) => {
        switch (type) {
            case 'basler': return 'Baslerカメラ';
            case 'webcam': return 'Webカメラ';
            case 'usb': return 'USBカメラ';
        }
    };

    return (
        <div className="h-screen bg-white flex flex-col">
            {/* Header */}
            <div className="bg-purple-600 text-white px-6 py-3">
                <h1 className="text-2xl font-bold">木材検査システム　撮影</h1>
            </div>

            {/* Camera Type Selection */}
            <div className="bg-gray-50 p-4 border-b-2 border-gray-300">
                <div className="flex items-center justify-center gap-6">
                    <span className="text-lg font-semibold">カメラタイプ:</span>
                    {(['basler', 'webcam', 'usb'] as CameraType[]).map((type) => (
                        <button
                            key={type}
                            onClick={() => handleCameraTypeChange(type)}
                            className={`flex items-center gap-2 px-6 py-3 rounded-lg border-2 font-semibold transition-all ${
                                selectedCameraType === type
                                    ? 'bg-purple-500 text-white border-purple-600 shadow-lg'
                                    : 'bg-white text-gray-700 border-gray-300 hover:border-purple-400'
                            }`}
                        >
                            {getCameraIcon(type)}
                            {getCameraName(type)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Control Panel */}
            <div className="bg-white p-6 border-b-2 border-gray-300">
                <div className="flex items-center justify-center gap-8">
                    <div className={`px-8 py-4 rounded border-2 text-xl font-bold min-w-[120px] text-center ${
                        status === '待機中' ? 'bg-gray-100 border-gray-600 text-gray-800' : 
                        status === '接続中' ? 'bg-yellow-100 border-yellow-600 text-yellow-800' : 
                        'bg-green-100 border-green-600 text-green-800'
                    }`}>
                        {status}
                    </div>
                    
                    <button 
                        onClick={handleCapture}
                        disabled={!isConnected}
                        className="bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white px-12 py-4 rounded-lg text-xl font-bold border-2 border-green-700 shadow-lg min-w-[140px] flex items-center gap-2 justify-center"
                    >
                        <Save size={20} />
                        撮影・保存
                    </button>
                    
                    <button 
                        onClick={handleReset}
                        className="bg-blue-500 hover:bg-blue-600 text-white px-12 py-4 rounded-lg text-xl font-bold border-2 border-blue-700 shadow-lg min-w-[120px]"
                    >
                        リセット
                    </button>

                    <div className="px-6 py-4 bg-blue-100 border-2 border-blue-300 rounded-lg">
                        <span className="text-lg font-semibold">撮影枚数: </span>
                        <span className="text-xl font-bold text-blue-600">{imageCount}枚</span>
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 relative bg-gray-100">
                {/* Camera Feed - Large Display */}
                <div className="absolute inset-8 border-4 border-gray-700 bg-gray-800 rounded-lg overflow-hidden shadow-lg">
                    {selectedCameraType === 'basler' ? (
                        // Basler Camera Display
                        <div className="w-full h-full">
                            {image ? (
                                <TransformWrapper>
                                    {({ resetTransform }) => {
                                        resetTransformRef.current = resetTransform;
                                        return (
                                            <TransformComponent
                                                wrapperStyle={{ width: '100%', height: '100%' }}
                                                contentStyle={{ width: '100%', height: '100%' }}
                                            >
                                                <img
                                                    src={image}
                                                    alt="Basler Camera Feed"
                                                    className="w-full h-full object-contain"
                                                />
                                                {droppedFrame && (
                                                    <div className="absolute top-4 right-4 bg-yellow-100 border border-yellow-400 text-yellow-800 px-3 py-2 rounded flex items-center gap-2 z-20">
                                                        <AlertTriangle size={16} />
                                                        フレーム欠落
                                                    </div>
                                                )}
                                            </TransformComponent>
                                        );
                                    }}
                                </TransformWrapper>
                            ) : (
                                <div className="w-full h-full flex items-center justify-center">
                                    {isConnected === false ? (
                                        <div className="text-center text-white">
                                            <AlertTriangle size={64} className="mx-auto mb-4" />
                                            <p className="text-2xl font-bold">Baslerカメラ未接続</p>
                                            <p className="text-lg">カメラを確認してください</p>
                                        </div>
                                    ) : (
                                        <div className="text-center text-white">
                                            <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-white mx-auto mb-4"></div>
                                            <p className="text-xl">画像取得中...</p>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ) : (
                        // Webcam/USB Camera Display
                        <div className="w-full h-full relative">
                            <video
                                ref={videoRef}
                                autoPlay
                                playsInline
                                muted
                                className="w-full h-full object-contain"
                            />
                            {droppedFrame && (
                                <div className="absolute top-4 right-4 bg-yellow-100 border border-yellow-400 text-yellow-800 px-3 py-2 rounded flex items-center gap-2 z-20">
                                    <AlertTriangle size={16} />
                                    フレーム欠落
                                </div>
                            )}
                            {isConnected === false && (
                                <div className="absolute inset-0 flex items-center justify-center bg-gray-800">
                                    <div className="text-center text-white">
                                        <AlertTriangle size={64} className="mx-auto mb-4" />
                                        <p className="text-2xl font-bold">{getCameraName(selectedCameraType)}未接続</p>
                                        <p className="text-lg">カメラを確認してください</p>
                                    </div>
                                </div>
                            )}
                            {image && (
                                <div className="absolute top-4 left-4 bg-green-100 border border-green-400 text-green-800 px-3 py-2 rounded">
                                    最後の撮影画像を保存しました
                                </div>
                            )}
                        </div>
                    )}
                    
                    {/* Camera Label */}
                    <div className="absolute bottom-0 left-0 right-0 bg-purple-600 text-white text-center py-2 font-bold text-lg">
                        {getCameraName(selectedCameraType)} {isConnected ? '(接続済み)' : '(未接続)'}
                    </div>
                </div>

                {/* Settings Info */}
                <div className="absolute top-4 left-4 bg-white bg-opacity-90 p-4 rounded-lg shadow-lg">
                    <div className="flex items-center gap-2 mb-2">
                        <Settings size={20} />
                        <span className="font-semibold">カメラ設定</span>
                    </div>
                    <div className="text-sm space-y-1">
                        <p>解像度: 1280x720</p>
                        <p>フォーマット: JPEG</p>
                        {selectedCameraType === 'basler' && <p>露光時間: 自動</p>}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ShootingScreen; 