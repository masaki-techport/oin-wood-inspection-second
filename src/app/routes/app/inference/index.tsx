import React, { useState, useRef, useEffect } from 'react';
import { DefaultLayout } from '@/components/layouts';
import Button from '@/components/ui/button';
import { useNotifications } from '@/components/ui/notifications';
import { Spinner } from '@/components/ui/spinner';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import useNavigate from '@/hooks/use-navigate';
import { api, apiDebug } from '@/lib/api-client';
import { ApiResult, InferenceResult } from '@/types/api';
import { NetworkStatusIndicator } from '@/components/ui/network-status';

const InferencePage = () => {
  const { navigate } = useNavigate();
  const { addNotification } = useNotifications();
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<InferenceResult | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [inferenceServiceStatus, setInferenceServiceStatus] = useState<string>('checking');
  const [retryCount, setRetryCount] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastInferenceAttempt, setLastInferenceAttempt] = useState<Date | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const inferenceRetryTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Check connection and service status on component mount
  useEffect(() => {
    checkInferenceServiceStatus();
    const interval = setInterval(checkInferenceServiceStatus, 30000);
    return () => {
      clearInterval(interval);
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      if (inferenceRetryTimeoutRef.current) {
        clearTimeout(inferenceRetryTimeoutRef.current);
      }
    };
  }, []);

  const checkInferenceServiceStatus = async () => {
    try {
      // First check basic connectivity
      const connectionTest = await apiDebug.testConnection();
      if (!connectionTest.success) {
        setIsConnected(false);
        setInferenceServiceStatus('connection_failed');
        return;
      }
      
      setIsConnected(true);
      
      // Then check inference service specifically
      const response = await api.get('/inference/status') as any;
      
      // Handle successful response
      if (response.result && response.model_available) {
        setInferenceServiceStatus('available');
        setRetryCount(0); // Reset retry count on success
        setLastError(null); // Clear any previous errors
      } else {
        // Service responded but model is not available
        setInferenceServiceStatus('service_unavailable');
        
        // Set specific error message based on the issue
        if (response.issue === 'model_file_missing') {
          setLastError('推論モデルファイルが見つかりません。model/best.onnxファイルをモデルディレクトリに配置してください。');
        } else if (response.issue === 'model_load_failed') {
          setLastError('推論モデルの読み込みに失敗しました。モデルファイルが破損しているか、依存ライブラリが不足している可能性があります。');
        } else if (response.issue === 'initialization_failed') {
          setLastError(`推論サービスの初期化に失敗: ${response.initialization_error || response.message}`);
        } else {
          setLastError(response.message || '推論サービスが利用できません。');
        }
      }
    } catch (error: any) {
      console.error('Inference service status check failed:', error);
      setIsConnected(false);
      
      if (error.response?.status === 503) {
        setInferenceServiceStatus('service_unavailable');
        // Extract detailed error information from response
        const errorData = error.response.data;
        if (errorData?.details?.error_message) {
          setLastError(errorData.details.error_message);
        } else {
          setLastError('推論サービスの初期化に失敗しました。サーバーログを確認してください。');
        }
      } else {
        setInferenceServiceStatus('connection_failed');
        setLastError('サーバーへの接続に失敗しました。ネットワーク接続を確認してください。');
      }
      
      // Implement retry logic with exponential backoff
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 2000; // 2s, 4s, 8s
        retryTimeoutRef.current = setTimeout(() => {
          setRetryCount(prev => prev + 1);
          checkInferenceServiceStatus();
        }, delay);
      }
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        setSelectedImage(e.target?.result as string);
        setResult(null); // Clear previous results when new image is selected
      };
      reader.readAsDataURL(file);
    }
  };

  const handleInference = async (retryAttempt = 0) => {
    // Pre-validation checks
    if (!isConnected) {
      const errorMsg = 'サーバーに接続できません。ネットワーク接続を確認してください。';
      setLastError(errorMsg);
      addNotification({
        type: 'error',
        title: 'Connection Error',
        message: errorMsg,
      });
      return;
    }

    if (inferenceServiceStatus !== 'available') {
      const errorMsg = '推論サービスが利用できません。サーバーの状態を確認してください。';
      setLastError(errorMsg);
      addNotification({
        type: 'error',
        title: '推論サービスエラー',
        message: errorMsg,
      });
      return;
    }

    if (!fileInputRef.current?.files?.[0]) {
      const errorMsg = '画像ファイルを選択してください';
      setLastError(errorMsg);
      addNotification({
        type: 'error',
        title: 'エラー',
        message: errorMsg,
      });
      return;
    }

    setIsLoading(true);
    setResult(null);
    setLastInferenceAttempt(new Date());
    if (retryAttempt === 0) {
      setLastError(null); // Clear previous errors on new attempts
    }

    try {
      const formData = new FormData();
      formData.append('file', fileInputRef.current.files[0]);

      const response = await api.post('/inference/predict', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // Increase timeout for inference requests to 60 seconds
      }) as ApiResult<InferenceResult>;

      if (response && response.result && response.data) {
        setResult(response.data);
        setLastError(null); // Clear error on success
        addNotification({
          type: 'success',
          title: '推論完了',
          message: `${response.data.total_detections}個の節を検出しました`,
        });
      } else {
        throw new Error('Invalid response format');
      }
    } catch (error: any) {
      console.error('Inference error:', error);
      
      let errorMessage = '推論処理に失敗しました';
      let errorTitle = '推論エラー';
      let shouldRetry = false;
      
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        errorTitle = 'タイムアウトエラー';
        errorMessage = '推論処理がタイムアウトしました。ファイルサイズを確認するか、しばらく待ってから再試行してください。';
        shouldRetry = retryAttempt < 2; // Retry up to 2 times for timeouts
      } else if (error.response?.status === 503) {
        errorTitle = 'サービス利用不可';
        errorMessage = '推論サービスが利用できません。AIモデルの初期化を確認してください。';
        shouldRetry = retryAttempt < 1; // Retry once for service unavailable
      } else if (error.response?.status === 400) {
        errorMessage = error.response?.data?.detail || 'ファイル形式が無効です。JPG、PNG、BMPファイルを選択してください。';
      } else if (error.response?.status >= 500) {
        errorTitle = 'サーバーエラー';
        errorMessage = 'サーバーでエラーが発生しました。しばらく待ってから再試行してください。';
        shouldRetry = retryAttempt < 2; // Retry up to 2 times for server errors
      } else if (error.code === 'NETWORK_ERROR' || !error.response) {
        errorTitle = 'ネットワークエラー';
        errorMessage = 'ネットワーク接続に問題があります。接続を確認してから再試行してください。';
        shouldRetry = retryAttempt < 3; // Retry up to 3 times for network errors
      } else {
        errorMessage = error.response?.data?.detail || error.message || errorMessage;
      }
      
      setLastError(`${errorTitle}: ${errorMessage}`);
      
      // Implement automatic retry with exponential backoff
      if (shouldRetry) {
        const delay = Math.pow(2, retryAttempt) * 1000; // 1s, 2s, 4s
        console.log(`Retrying inference in ${delay}ms (attempt ${retryAttempt + 1})`);
        
        // Clear any existing inference retry timeout
        if (inferenceRetryTimeoutRef.current) {
          clearTimeout(inferenceRetryTimeoutRef.current);
        }
        
        inferenceRetryTimeoutRef.current = setTimeout(() => {
          handleInference(retryAttempt + 1);
        }, delay);
        
        addNotification({
          type: 'warning',
          title: `${errorTitle} - 再試行中`,
          message: `${errorMessage} ${delay / 1000}秒後に再試行します...（${retryAttempt + 1}/3）`,
        });
      } else {
        // No more retries, show final error
        addNotification({
          type: 'error',
          title: errorTitle,
          message: errorMessage,
        });
      }
      
      // Update service status if this was a service-related error
      if (error.response?.status === 503) {
        setInferenceServiceStatus('service_unavailable');
      }
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

  const getServiceStatusDisplay = () => {
    switch (inferenceServiceStatus) {
      case 'checking':
        return { text: 'サービス状態を確認中...', color: 'text-yellow-600' };
      case 'available':
        return { text: '推論サービス利用可能', color: 'text-green-600' };
      case 'service_unavailable':
        return { text: '推論サービス利用不可', color: 'text-red-600' };
      case 'connection_failed':
        return { text: 'サーバー接続失敗', color: 'text-red-600' };
      default:
        return { text: '状態不明', color: 'text-gray-600' };
    }
  };

  const canPerformInference = isConnected && inferenceServiceStatus === 'available';

  return (
    <DefaultLayout title="推論">
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold">木材節検出推論</h1>
            <div className="flex items-center gap-2">
              <NetworkStatusIndicator />
              <div className={`text-sm ${getServiceStatusDisplay().color}`}>
                {getServiceStatusDisplay().text}
              </div>
              {retryCount > 0 && (
                <div className="text-xs text-gray-500">
                  再試行 {retryCount}/3
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outlined"
              onClick={checkInferenceServiceStatus}
              size="small"
              disabled={isLoading}
            >
              状態更新
            </Button>
            <Button
              variant="outlined"
              onClick={() => navigate('/')}
              sx={{ px: 3, py: 1 }}
            >
              ホームに戻る
            </Button>
          </div>
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
                  onClick={() => handleInference()}
                  disabled={!selectedImage || isLoading || !canPerformInference}
                  sx={{ 
                    width: '100%', 
                    backgroundColor: canPerformInference ? '#3b82f6' : '#9ca3af',
                    '&:hover': { backgroundColor: canPerformInference ? '#2563eb' : '#9ca3af' },
                    '&:disabled': { backgroundColor: '#9ca3af' }
                  }}
                >
                  {isLoading ? (
                    <>
                      <Spinner size="sm" className="mr-2" />
                      推論中...
                    </>
                  ) : !canPerformInference ? (
                    'サービス利用不可'
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

              {/* Connection Status and Error Panel */}
              {(!isConnected || inferenceServiceStatus !== 'available' || lastError) && (
                <div className="mt-4 p-4 border rounded-lg bg-yellow-50 border-yellow-200">
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-yellow-800">接続状態</h3>
                    <div className="flex gap-2">
                      {lastError && selectedImage && (
                        <Button
                          variant="outlined"
                          onClick={() => handleInference(0)}
                          size="small"
                          disabled={isLoading || !canPerformInference}
                          sx={{ 
                            fontSize: '12px', 
                            padding: '4px 8px',
                            minHeight: 'auto',
                            backgroundColor: '#f97316',
                            color: 'white',
                            '&:hover': { backgroundColor: '#ea580c' }
                          }}
                        >
                          推論再試行
                        </Button>
                      )}
                      <Button
                        variant="outlined"
                        onClick={checkInferenceServiceStatus}
                        size="small"
                        disabled={isLoading}
                        sx={{ 
                          fontSize: '12px', 
                          padding: '4px 8px',
                          minHeight: 'auto'
                        }}
                      >
                        状態再確認
                      </Button>
                    </div>
                  </div>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center">
                      <span>ネットワーク接続:</span>
                      <span className={`font-semibold ${
                        isConnected ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {isConnected ? '正常' : '接続失敗'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>推論サービス:</span>
                      <span className={`font-semibold ${
                        inferenceServiceStatus === 'available' ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {getServiceStatusDisplay().text}
                      </span>
                    </div>
                    
                    {lastError && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded">
                        <div className="text-xs font-semibold text-red-800 mb-1">最新エラー:</div>
                        <div className="text-xs text-red-700">{lastError}</div>
                        {lastInferenceAttempt && (
                          <div className="text-xs text-gray-500 mt-1">
                            最新試行: {lastInferenceAttempt.toLocaleTimeString()}
                          </div>
                        )}
                      </div>
                    )}
                    
                    {retryCount > 0 && (
                      <div className="text-xs text-gray-600 mt-2">
                        自動再試行: {retryCount}/3 回実行済み
                      </div>
                    )}
                    
                    {/* Troubleshooting Tips */}
                    {!isConnected && (
                      <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-xs">
                        <div className="font-semibold text-red-800 mb-1">接続トラブルシューティング:</div>
                        <ul className="text-red-700 space-y-1 ml-4 list-disc">
                          <li>バックエンドサーバーが起動していることを確認</li>
                          <li>ネットワーク接続を確認</li>
                          <li>ファイアウォール設定を確認</li>
                          <li>ブラウザを再読み込み</li>
                        </ul>
                      </div>
                    )}
                    
                    {isConnected && inferenceServiceStatus !== 'available' && (
                      <div className="mt-3 p-3 bg-orange-50 border border-orange-200 rounded text-xs">
                        <div className="font-semibold text-orange-800 mb-1">推論サービス問題:</div>
                        <ul className="text-orange-700 space-y-1 ml-4 list-disc">
                          {lastError?.includes('モデルファイルが見つかりません') ? (
                            <>
                              <li>AIモデルファイル (best.onnx) をmodel/ディレクトリに配置</li>
                              <li>ファイルパスとファイル名を確認</li>
                              <li>ファイルの読み取り権限を確認</li>
                            </>
                          ) : lastError?.includes('読み込みに失敗') ? (
                            <>
                              <li>onnxruntimeライブラリのインストール確認</li>
                              <li>モデルファイルの整合性確認</li>
                              <li>Pythonバージョンとライブラリの互換性確認</li>
                              <li>サーバーログで詳細なエラーを確認</li>
                            </>
                          ) : lastError?.includes('初期化に失敗') || lastError?.includes('onnxruntime') ? (
                            <>
                              <li>pip install onnxruntime でライブラリをインストール</li>
                              <li>Python仮想環境が正しくアクティベートされているか確認</li>
                              <li>requirements.txtのライブラリを再インストール</li>
                              <li>サーバーを再起動してライブラリを再読み込み</li>
                            </>
                          ) : (
                            <>
                              <li>AIモデルの初期化を確認</li>
                              <li>model/best.onnxファイルの存在を確認</li>
                              <li>サーバーログでエラーを確認</li>
                              <li>設定ファイル（calc_param.yaml）を確認</li>
                            </>
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}

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