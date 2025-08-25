import React, { useState, useRef } from 'react';
import { DefaultLayout } from '@/components/layouts';
import Button from '@/components/ui/button';
import { useNotifications } from '@/components/ui/notifications';
import { Spinner } from '@/components/ui/spinner';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import useNavigate from '@/hooks/use-navigate';
import { api } from '@/lib/api-client';
import { ApiResult, InferenceResult } from '@/types/api';

const InferencePage = () => {
  const { navigate } = useNavigate();
  const { addNotification } = useNotifications();
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<InferenceResult | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        setSelectedImage(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleInference = async () => {
    if (!fileInputRef.current?.files?.[0]) {
      addNotification({
        type: 'error',
        title: 'エラー',
        message: '画像ファイルを選択してください',
      });
      return;
    }

    setIsLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', fileInputRef.current.files[0]);

      const response = await api.post('/api/inference/predict', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }) as ApiResult<InferenceResult>;

      if (response && response.result && response.data) {
        setResult(response.data);
        addNotification({
          type: 'success',
          title: '推論完了',
          message: `${response.data.total_detections}個の節を検出しました`,
        });
      }
    } catch (error: any) {
      console.error('Inference error:', error);
      addNotification({
        type: 'error',
        title: '推論エラー',
        message: error.response?.data?.detail || '推論処理に失敗しました',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedImage(null);
    setResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <DefaultLayout title="推論">
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <h1 className="text-2xl font-bold">木材節検出推論</h1>
          <Button
            variant="outlined"
            onClick={() => navigate('/')}
            sx={{ px: 3, py: 1 }}
          >
            ホームに戻る
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 flex">
          {/* Left Panel - Controls */}
          <div className="w-80 border-r p-4 flex flex-col">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  画像ファイル選択
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="w-full p-2 border rounded-md"
                />
              </div>

              <div className="space-y-2">
                <Button
                  onClick={handleInference}
                  disabled={!selectedImage || isLoading}
                  sx={{ 
                    width: '100%', 
                    backgroundColor: '#3b82f6',
                    '&:hover': { backgroundColor: '#2563eb' }
                  }}
                >
                  {isLoading ? (
                    <>
                      <Spinner size="sm" className="mr-2" />
                      推論中...
                    </>
                  ) : (
                    '推論実行'
                  )}
                </Button>

                <Button
                  onClick={handleReset}
                  variant="outlined"
                  sx={{ width: '100%' }}
                >
                  リセット
                </Button>
              </div>

              {/* Results Panel */}
              {result && (
                <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                  <h3 className="font-bold text-lg mb-3">検出結果</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>検出数合計:</span>
                      <span className="font-bold">{result.total_detections}</span>
                    </div>
                    <hr />
                    {Object.entries(result.knot_counts).map(([type, count]) => (
                      <div key={type} className="flex justify-between">
                        <span>{type}:</span>
                        <span className="font-bold">{count}</span>
                      </div>
                    ))}
                    <hr />
                    
                    {/* Color Legend */}
                    <div className="mt-3">
                      <h4 className="font-semibold text-sm mb-2">カラーコード</h4>
                      <div className="space-y-1 text-xs">
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 border" style={{ backgroundColor: 'rgb(128, 0, 128)' }}></div>
                          <span>変色</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 border" style={{ backgroundColor: 'rgb(255, 0, 0)' }}></div>
                          <span>穴</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 border" style={{ backgroundColor: 'rgb(255, 165, 0)' }}></div>
                          <span>死に節</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 border" style={{ backgroundColor: 'rgb(255, 255, 0)' }}></div>
                          <span>流れ節(死)</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 border" style={{ backgroundColor: 'rgb(0, 255, 0)' }}></div>
                          <span>流れ節(生)</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 border" style={{ backgroundColor: 'rgb(0, 0, 255)' }}></div>
                          <span>生き節</span>
                        </div>
                      </div>
                    </div>
                    <hr />
                    
                    <div className="flex justify-between">
                      <span>しきい値:</span>
                      <span>{result.config.thresh}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>分解能:</span>
                      <span>{result.config.resolution} mm/pix</span>
                    </div>
                  </div>

                  {/* Debug Class Mappings */}
                  {result.debug && (
                    <div className="mt-4 p-3 bg-blue-50 rounded-lg border">
                      <h4 className="font-bold text-sm mb-2 text-blue-800">デバッグ情報 - クラスマッピング</h4>
                      <div className="text-xs space-y-2">
                        <div>
                          <span className="font-semibold">Model:</span>
                          <div className="ml-2 space-y-1">
                            {Object.entries(result.debug.model_class_mapping).map(([id, label]) => (
                              <div key={id} className="flex justify-between">
                                <span>{id}:</span>
                                <span>{label}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <span className="font-semibold">App:</span>
                          <div className="ml-2 space-y-1">
                            {Object.entries(result.debug.app_class_mapping).map(([id, label]) => (
                              <div key={id} className="flex justify-between">
                                <span>{id}:</span>
                                <span>{label}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="text-gray-600 text-xs mt-2">
                          {result.debug.mapping_note}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Image Display */}
          <div className="flex-1 p-4">
            <div className="h-full border rounded-lg overflow-hidden bg-gray-100">
              {selectedImage && !result && (
                <TransformWrapper
                  initialScale={1}
                  minScale={0.1}
                  maxScale={10}
                  centerOnInit
                >
                  <TransformComponent wrapperStyle={{ width: '100%', height: '100%' }}>
                    <img
                      src={selectedImage}
                      alt="Selected"
                      className="max-w-full max-h-full object-contain"
                    />
                  </TransformComponent>
                </TransformWrapper>
              )}

              {result && (
                <TransformWrapper
                  initialScale={1}
                  minScale={0.1}
                  maxScale={10}
                  centerOnInit
                >
                  <TransformComponent wrapperStyle={{ width: '100%', height: '100%' }}>
                    <img
                      src={`data:image/jpeg;base64,${result.result_image}`}
                      alt="Inference Result"
                      className="max-w-full max-h-full object-contain"
                    />
                  </TransformComponent>
                </TransformWrapper>
              )}

              {!selectedImage && (
                <div className="h-full flex items-center justify-center text-gray-500">
                  画像ファイルを選択してください
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </DefaultLayout>
  );
};

export default InferencePage; 