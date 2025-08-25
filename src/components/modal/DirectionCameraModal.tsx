import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface DirectionCameraModalProps {
    onClose: () => void;
}

interface CameraStatus {
    status: string;
    save_message: string;
    save_path: string;
    buffer_size: number;
    max_buffer_size: number;
    is_recording: boolean;
    is_connected: boolean;
}

const DirectionCameraModal: React.FC<DirectionCameraModalProps> = ({ onClose }) => {
    const [image, setImage] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState<boolean | null>(null);
    const [cameraStatus, setCameraStatus] = useState<CameraStatus | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const resetTransformRef = useRef<(() => void) | null>(null);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const statusIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const hasInitializedRef = useRef(false);
    const droppedRef = useRef(false);
    const [droppedFrame, setDroppedFrame] = useState(false);

    const API_BASE = 'http://localhost:8000/api';

    const fetchImage = async () => {
        try {
            const res = await axios.get(`${API_BASE}/direction-camera/snapshot`);
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
                console.error('fetchImage失敗:', err);
            }
        }
    };

    const fetchStatus = async () => {
        try {
            const res = await axios.get(`${API_BASE}/direction-camera/status`);
            setCameraStatus(res.data);
        } catch (err) {
            console.error('ステータス取得失敗:', err);
        }
    };

    const connectCamera = async () => {
        setIsLoading(true);
        try {
            // Disconnect first
            await axios.post(`${API_BASE}/direction-camera/disconnect`).catch(() => {});
            
            // Connect to camera
            const connectRes = await axios.post(`${API_BASE}/direction-camera/connect`);
            const connected = connectRes.data.connected === true;
            setIsConnected(connected);

            if (connected) {
                // Start image fetching
                await fetchImage();
                intervalRef.current = setInterval(fetchImage, 100);
                statusIntervalRef.current = setInterval(fetchStatus, 500);
            }
        } catch (err) {
            console.error('カメラ接続失敗:', err);
            setIsConnected(false);
        } finally {
            setIsLoading(false);
        }
    };

    const disconnectCamera = async () => {
        try {
            if (intervalRef.current) clearInterval(intervalRef.current);
            if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
            await axios.post(`${API_BASE}/direction-camera/disconnect`);
            setIsConnected(false);
            setCameraStatus(null);
            setImage(null);
        } catch (err) {
            console.error('カメラ切断失敗:', err);
        }
    };

    const startRecording = async () => {
        try {
            await axios.post(`${API_BASE}/direction-camera/start_recording`);
            fetchStatus();
        } catch (err) {
            console.error('録画開始失敗:', err);
        }
    };

    const stopRecording = async () => {
        try {
            await axios.post(`${API_BASE}/direction-camera/stop_recording`);
            fetchStatus();
        } catch (err) {
            console.error('録画停止失敗:', err);
        }
    };

    const saveImages = async () => {
        try {
            const res = await axios.post(`${API_BASE}/direction-camera/save_images`);
            console.log('保存完了:', res.data);
            fetchStatus();
        } catch (err) {
            console.error('保存失敗:', err);
        }
    };

    const discardImages = async () => {
        try {
            await axios.post(`${API_BASE}/direction-camera/discard_images`);
            fetchStatus();
        } catch (err) {
            console.error('破棄失敗:', err);
        }
    };

    // Simulation functions for testing
    const simulatePassLeftToRight = async () => {
        try {
            const res = await axios.post(`${API_BASE}/direction-camera/simulate_pass_left_to_right`);
            console.log('左→右通過シミュレーション:', res.data);
            fetchStatus();
        } catch (err) {
            console.error('シミュレーション失敗:', err);
        }
    };

    const simulateReturnFromLeft = async () => {
        try {
            const res = await axios.post(`${API_BASE}/direction-camera/simulate_return_from_left`);
            console.log('左からの折り返しシミュレーション:', res.data);
            fetchStatus();
        } catch (err) {
            console.error('シミュレーション失敗:', err);
        }
    };

    const simulateError = async () => {
        try {
            const res = await axios.post(`${API_BASE}/direction-camera/simulate_error`);
            console.log('エラーシミュレーション:', res.data);
            fetchStatus();
        } catch (err) {
            console.error('シミュレーション失敗:', err);
        }
    };

    useEffect(() => {
        if (hasInitializedRef.current) return;
        hasInitializedRef.current = true;

        connectCamera();

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
            if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
            axios.post(`${API_BASE}/direction-camera/disconnect`).catch(() => {});
        };
    }, []);

    const handleClose = () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
        axios.post(`${API_BASE}/direction-camera/disconnect`).catch(() => {});
        onClose();
    };

    const getStatusIcon = () => {
        if (!cameraStatus) return null;
        
        if (cameraStatus.is_recording) {
            return <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>;
        } else if (cameraStatus.save_message === "保存しました") {
            return <div className="w-3 h-3 bg-green-500 rounded-full"></div>;
        } else if (cameraStatus.save_message === "破棄しました") {
            return <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>;
        } else {
            return <div className="w-3 h-3 bg-blue-500 rounded-full"></div>;
        }
    };

    return (
        <div className="fixed inset-4 bg-white rounded-lg flex flex-col overflow-hidden p-5 z-50">
            {/* Header */}
            <div className="flex justify-between items-center mb-5 pb-2 border-b border-gray-300">
                <h2 className="text-2xl font-bold">🎯 方向検知カメラ</h2>
                <div className="flex gap-2 items-center">
                    <div className={`w-3 h-3 rounded-full ${
                        cameraStatus?.is_recording ? 'bg-red-500 animate-pulse' :
                        cameraStatus?.save_message === "保存しました" ? 'bg-green-500' :
                        cameraStatus?.save_message === "破棄しました" ? 'bg-yellow-500' :
                        'bg-blue-500'
                    }`}></div>
                    <span className="text-sm text-gray-600">
                        {cameraStatus?.status || '未接続'}
                    </span>
                </div>
            </div>

            {/* Status Panel */}
            {cameraStatus && (
                <div className="bg-gray-50 p-4 rounded-lg mb-5 grid grid-cols-2 gap-4 text-sm">
                    <div><strong>ステータス:</strong> {cameraStatus.status}</div>
                    <div><strong>バッファ:</strong> {cameraStatus.buffer_size}/{cameraStatus.max_buffer_size}</div>
                    <div><strong>メッセージ:</strong> {cameraStatus.save_message}</div>
                    {cameraStatus.save_path && (
                        <div><strong>保存先:</strong> {cameraStatus.save_path}</div>
                    )}
                </div>
            )}

            {/* Main Content */}
            <div className="flex-1 flex gap-5">
                {/* Camera View */}
                <div className="flex-2 flex flex-col">
                    <div className="flex-1 border-2 border-gray-300 rounded-lg overflow-hidden">
                        {isConnected === false && (
                            <div className="flex items-center justify-center h-full flex-col gap-2 text-gray-600">
                                <AlertTriangle size={48} />
                                <p>カメラが接続されていません</p>
                                <button
                                    onClick={connectCamera}
                                    disabled={isLoading}
                                    className="bg-blue-500 text-white px-4 py-2 rounded cursor-pointer disabled:opacity-50"
                                >
                                    {isLoading ? '接続中...' : '再接続'}
                                </button>
                            </div>
                        )}
                        
                        {isConnected === null && (
                            <div className="flex items-center justify-center h-full text-gray-600">
                                <RefreshCw className="animate-spin" size={48} />
                                <p>カメラに接続中...</p>
                            </div>
                        )}

                        {isConnected && image && (
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
                                                alt="Direction Camera Feed"
                                                className="w-full h-full object-contain"
                                            />
                                        </TransformComponent>
                                    );
                                }}
                            </TransformWrapper>
                        )}
                    </div>
                </div>

                {/* Control Panel */}
                <div className="flex-1 flex flex-col gap-4 p-5 bg-gray-50 rounded-lg">
                    <h3 className="text-lg font-semibold mb-2">制御パネル</h3>
                    
                    {/* Recording Controls */}
                    <div>
                        <h4 className="font-medium mb-2">録画制御</h4>
                        <div className="flex flex-col gap-2">
                            <button
                                onClick={startRecording}
                                disabled={!isConnected || cameraStatus?.is_recording}
                                className="bg-green-500 text-white px-3 py-2 rounded text-sm disabled:opacity-50"
                            >
                                録画開始
                            </button>
                            <button
                                onClick={stopRecording}
                                disabled={!isConnected || !cameraStatus?.is_recording}
                                className="bg-red-500 text-white px-3 py-2 rounded text-sm disabled:opacity-50"
                            >
                                録画停止
                            </button>
                        </div>
                    </div>

                    {/* Image Management */}
                    <div>
                        <h4 className="font-medium mb-2">画像管理</h4>
                        <div className="flex flex-col gap-2">
                            <button
                                onClick={saveImages}
                                disabled={!isConnected || cameraStatus?.buffer_size === 0}
                                className="bg-blue-500 text-white px-3 py-2 rounded text-sm disabled:opacity-50"
                            >
                                画像保存
                            </button>
                            <button
                                onClick={discardImages}
                                disabled={!isConnected || cameraStatus?.buffer_size === 0}
                                className="bg-yellow-500 text-black px-3 py-2 rounded text-sm disabled:opacity-50"
                            >
                                画像破棄
                            </button>
                        </div>
                    </div>

                    {/* Simulation Controls */}
                    <div>
                        <h4 className="font-medium mb-2">シミュレーション</h4>
                        <div className="flex flex-col gap-2">
                            <button
                                onClick={simulatePassLeftToRight}
                                disabled={!isConnected}
                                className="bg-cyan-500 text-white px-3 py-2 rounded text-sm disabled:opacity-50"
                            >
                                左→右通過
                            </button>
                            <button
                                onClick={simulateReturnFromLeft}
                                disabled={!isConnected}
                                className="bg-purple-500 text-white px-3 py-2 rounded text-sm disabled:opacity-50"
                            >
                                左からの折り返し
                            </button>
                            <button
                                onClick={simulateError}
                                disabled={!isConnected}
                                className="bg-pink-500 text-white px-3 py-2 rounded text-sm disabled:opacity-50"
                            >
                                エラー状態
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 mt-5 pt-2 border-t border-gray-300">
                <button
                    onClick={() => resetTransformRef.current?.()}
                    className="bg-blue-100 border border-black rounded-lg px-6 py-3"
                >
                    拡大リセット
                </button>
                <button
                    onClick={handleClose}
                    className="bg-orange-100 border border-black rounded-lg px-6 py-3"
                >
                    閉じる
                </button>
            </div>
        </div>
    );
};

export default DirectionCameraModal; 