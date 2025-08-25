import React, { useEffect, useRef } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';

interface CameraModalProps {
    onClose: () => void;
}

const CameraModal: React.FC<CameraModalProps> = ({ onClose }) => {
    const videoRef = useRef<HTMLVideoElement>(null);
    const resetTransformRef = useRef<(() => void) | null>(null);

    useEffect(() => {
        const startCamera = async () => {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        };

        startCamera();
        const currentVideoRef = videoRef.current;

        return () => {
            if (currentVideoRef?.srcObject) {
                const tracks = (currentVideoRef.srcObject as MediaStream).getTracks();
                tracks.forEach((track) => track.stop());
            }
        };
    }, []);


    return (
        <div
            style={{
                position: 'fixed',
                top: '5%',
                left: '5%',
                width: '90%',
                height: '90%',
                backgroundColor: '#fff',
                borderRadius: '8px',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                boxSizing: 'border-box',
                padding: '20px',
            }}
        >
            {/* タイトル */}
            <div style={{
                position: 'absolute',
                top: '0',
                left: '0',
                fontSize: '24px',
                backgroundColor: '#fff',
                padding: '4px 8px',
                zIndex: 1,
                margin: '24px',
            }}>
                カメラ調整
            </div>

            {/* メインコンテンツ */}
            <div style={{ overflow: 'hidden', marginTop: '60px', marginBottom: '20px', flex: 1 }}>
                <TransformWrapper>
                    {({ resetTransform }) => {
                        resetTransformRef.current = resetTransform;
                        return (
                            <TransformComponent
                                wrapperStyle={{
                                    width: '100%',
                                    height: '100%',
                                }}
                                contentStyle={{
                                    width: '100%',
                                    height: '100%',
                                }}
                            >
                                <video
                                    ref={videoRef}
                                    autoPlay
                                    playsInline
                                    style={{
                                        width: '100%',
                                        height: '100%',
                                        objectFit: 'contain',
                                    }}
                                />
                            </TransformComponent>
                        );
                    }}
                </TransformWrapper>
            </div>
            {/* ボタン */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: '10px',
                }}
            >
                <button
                    onClick={() => resetTransformRef.current?.()}
                    style={{
                        backgroundColor: '#cce6ff',
                        border: '1px solid #000',
                        borderRadius: '8px',
                        padding: '12px 24px',
                        cursor: 'pointer',
                    }}
                >
                    拡大リセット
                </button>
                <button
                    onClick={() => {
                        if (videoRef.current?.srcObject) {
                            const tracks = (videoRef.current.srcObject as MediaStream).getTracks();
                            tracks.forEach((track) => track.stop());
                        }
                        window.location.reload();
                        onClose();
                    }}
                    style={{
                        backgroundColor: '#ffe6cc',
                        border: '1px solid #000',
                        borderRadius: '8px',
                        padding: '12px 24px',
                        cursor: 'pointer',
                    }}
                >
                    閉じる
                </button>
            </div>
        </div>
    );
};

export default CameraModal;
