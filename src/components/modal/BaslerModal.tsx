import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { AlertTriangle } from 'lucide-react';

interface BaslerModalProps {
    onClose: () => void;
}

const BaslerModal: React.FC<BaslerModalProps> = ({ onClose }) => {
    const [image, setImage] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState<boolean | null>(null);
    const resetTransformRef = useRef<(() => void) | null>(null);
    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const hasInitializedRef = useRef(false);
    const droppedRef = useRef(false);
    const [droppedFrame, setDroppedFrame] = useState(false);

    const fetchImage = async () => {
        try {
            const res = await axios.get('http://localhost:8000/api/camera/snapshot');
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
                return;
            } else {
                console.error('fetchImage失敗:', err);
            }
        }
    };

    useEffect(() => {
        if (hasInitializedRef.current) return;
        hasInitializedRef.current = true;

        const init = async () => {
            try {
                // 残っている場合は停止して切断する
                await axios.post('http://localhost:8000/api/camera/stop', {}).catch(() => { });
                await axios.post('http://localhost:8000/api/camera/disconnect', {}).catch(() => { });

                // カメラに接続する
                await axios.post('http://localhost:8000/api/camera/connect');

                // 接続を確認する
                const res = await axios.get('http://localhost:8000/api/camera/is_connected');
                const connected = res.data.connected === true;
                setIsConnected(connected);

                if (!connected) return;

                // 接続が成功した場合は画像の取得を開始する
                await axios.post('http://localhost:8000/api/camera/start');
                await fetchImage();
                intervalRef.current = setInterval(fetchImage, 100);

            } catch (err) {
                console.error('カメラ初期化失敗:', err);
                setIsConnected(false);
            }
        };


        init();

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
            axios.post('http://localhost:8000/api/camera/stop', {}).catch(() => { });
            axios.post('http://localhost:8000/api/camera/disconnect', {}).catch(() => { });
        };
    }, []);

    const handleClose = () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        axios.post('http://localhost:8000/api/camera/stop', {}).catch(() => { });
        axios.post('http://localhost:8000/api/camera/disconnect', {}).catch(() => { });
        onClose();
    };

    return (
        <div className="fixed top-[5%] left-[5%] w-[90%] h-[90%] bg-white rounded flex flex-col p-5 overflow-hidden">
            <h2 className="text-xl mb-2 text-left">Basler カメラ画像</h2>

            <div className="flex-1 overflow-hidden mb-4 relative">
                <TransformWrapper>
                    {({ resetTransform }) => {
                        resetTransformRef.current = resetTransform;

                        return (
                            <>
                                <TransformComponent>
                                    {image ? (
                                        <>
                                            <img
                                                src={image}
                                                alt="Basler Snapshot"
                                                className="w-full h-full object-contain"
                                            />
                                            {droppedFrame && (
                                                <div className="absolute top-2 right-2 bg-yellow-100 border border-yellow-400 text-yellow-800 text-xs px-2 py-1 rounded flex items-center gap-1 z-20 shadow">
                                                    <AlertTriangle className="w-4 h-4" />
                                                    フレーム落ち
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <p>画像を取得中...</p>
                                    )}
                                </TransformComponent>

                                {isConnected === false && (
                                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-white z-10 text-gray-600">
                                        <img
                                            src="/no-image.png"
                                            alt="no-image"
                                            className="w-[50%] max-w-[600px] h-auto object-contain mb-6"
                                        />
                                        <p className="text-xl font-medium">カメラ画像が取得できません</p>
                                    </div>
                                )}
                            </>
                        );
                    }}
                </TransformWrapper>
            </div>

            <div className="flex justify-end gap-2">
                <button
                    onClick={() => resetTransformRef.current?.()}
                    className="bg-blue-200 border border-gray-500 rounded px-4 py-2"
                >
                    拡大リセット
                </button>
                <button
                    onClick={handleClose}
                    className="bg-orange-200 border border-gray-500 rounded px-4 py-2"
                >
                    閉じる
                </button>
            </div>
        </div>
    );
};

export default BaslerModal;
