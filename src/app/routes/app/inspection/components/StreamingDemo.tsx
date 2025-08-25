import React, { useState } from 'react';
import { StreamingCameraPreview } from './StreamingCameraPreview';
import { useSensorStatusStream, useFileStream, getStreamingStats } from '../hooks/useStreamingData';

interface StreamingDemoProps {
  className?: string;
}

export const StreamingDemo: React.FC<StreamingDemoProps> = ({ className = '' }) => {
  const [selectedTab, setSelectedTab] = useState<'camera' | 'sensor' | 'file' | 'stats'>('camera');
  const [filePath, setFilePath] = useState<string>('');
  const [convertFormat, setConvertFormat] = useState<string>('');
  const [stats, setStats] = useState<any>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // SSE sensor status stream
  const { data: sensorData, isConnected: sensorConnected, error: sensorError } = useSensorStatusStream();

  // File streaming
  const { streamUrl: fileStreamUrl, isLoading: fileLoading, error: fileError } = useFileStream(
    filePath || null,
    convertFormat || undefined
  );

  // Load streaming statistics
  const loadStats = async () => {
    setLoadingStats(true);
    try {
      const data = await getStreamingStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoadingStats(false);
    }
  };

  const tabs = [
    { id: 'camera', label: 'Camera Stream', icon: '📹' },
    { id: 'sensor', label: 'Sensor SSE', icon: '📡' },
    { id: 'file', label: 'File Stream', icon: '📁' },
    { id: 'stats', label: 'Statistics', icon: '📊' }
  ];

  return (
    <div className={`streaming-demo ${className}`}>
      <div className="bg-white rounded-lg shadow-lg overflow-hidden">
        {/* Tab Navigation */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSelectedTab(tab.id as any)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${selectedTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
              >
                <span className="mr-2">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {/* Camera Streaming Tab */}
          {selectedTab === 'camera' && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Real-time Camera Streaming</h3>
              <p className="text-sm text-gray-600 mb-6">
                This demonstrates MJPEG streaming from the camera using FastAPI StreamingResponse.
                The stream provides real-time video feed with configurable frame rate and quality.
              </p>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Basler Camera</h4>
                  <StreamingCameraPreview
                    cameraType="basler"
                    showControls={true}
                    onError={(error) => console.error('Basler camera error:', error)}
                  />
                </div>

                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Webcam</h4>
                  <StreamingCameraPreview
                    cameraType="webcam"
                    showControls={true}
                    onError={(error) => console.error('Webcam error:', error)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Sensor SSE Tab */}
          {selectedTab === 'sensor' && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Real-time Sensor Status (SSE)</h3>
              <p className="text-sm text-gray-600 mb-6">
                This demonstrates Server-Sent Events for real-time sensor status updates.
                No polling required - updates are pushed from the server immediately.
              </p>

              {/* Connection Status */}
              <div className="mb-6">
                <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${sensorConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                  <div className={`w-2 h-2 rounded-full mr-2 ${sensorConnected ? 'bg-green-500' : 'bg-red-500'
                    }`}></div>
                  {sensorConnected ? 'Connected' : 'Disconnected'}
                </div>

                {sensorError && (
                  <div className="mt-2 text-sm text-red-600">
                    Error: {sensorError}
                  </div>
                )}
              </div>

              {/* Sensor Data Display */}
              {sensorData && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-medium text-gray-700 mb-3">Live Sensor Data</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div className="bg-white p-3 rounded border">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">Status</div>
                      <div className="text-lg font-semibold">Active</div>
                    </div>

                    <div className="bg-white p-3 rounded border">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">Sensor A</div>
                      <div className={`text-lg font-semibold ${sensorData.sensor_a ? 'text-green-600' : 'text-gray-400'}`}>
                        {sensorData.sensor_a ? 'ACTIVE' : 'INACTIVE'}
                      </div>
                    </div>

                    <div className="bg-white p-3 rounded border">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">Sensor B</div>
                      <div className={`text-lg font-semibold ${sensorData.sensor_b ? 'text-green-600' : 'text-gray-400'}`}>
                        {sensorData.sensor_b ? 'ACTIVE' : 'INACTIVE'}
                      </div>
                    </div>

                    <div className="bg-white p-3 rounded border">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">Direction</div>
                      <div className="text-lg font-semibold">{sensorData.direction}</div>
                    </div>

                    <div className="bg-white p-3 rounded border">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">Timestamp</div>
                      <div className="text-lg font-semibold">{new Date(sensorData.timestamp).toLocaleTimeString()}</div>
                    </div>

                    <div className="bg-white p-3 rounded border">
                      <div className="text-xs text-gray-500 uppercase tracking-wide">Sensor Count</div>
                      <div className="text-lg font-semibold">{[sensorData.sensor_a, sensorData.sensor_b].filter(Boolean).length}/2</div>
                    </div>
                  </div>

                  {/* Raw Data (for debugging) */}
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-800">
                      Show Raw Data
                    </summary>
                    <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-40">
                      {JSON.stringify(sensorData, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          )}

          {/* File Streaming Tab */}
          {selectedTab === 'file' && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">File Streaming</h3>
              <p className="text-sm text-gray-600 mb-6">
                This demonstrates efficient file streaming with optional format conversion.
                Files are streamed in chunks to reduce memory usage.
              </p>

              {/* File Path Input */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  File Path
                </label>
                <input
                  type="text"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  placeholder="e.g., inspection/2024-01-15/image.bmp"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Format Conversion */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Convert Format (optional)
                </label>
                <select
                  value={convertFormat}
                  onChange={(e) => setConvertFormat(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">No conversion</option>
                  <option value="jpg">Convert to JPG</option>
                  <option value="png">Convert to PNG</option>
                </select>
              </div>

              {/* File Display */}
              {filePath && (
                <div className="border rounded-lg p-4">
                  {fileLoading && (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
                      <p className="text-sm text-gray-600">Loading file...</p>
                    </div>
                  )}

                  {fileError && (
                    <div className="text-center py-8">
                      <div className="text-red-600 mb-2">
                        <svg className="w-8 h-8 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <p className="text-sm text-red-600">{fileError}</p>
                    </div>
                  )}

                  {fileStreamUrl && !fileLoading && !fileError && (
                    <div>
                      <div className="mb-2 text-sm text-gray-600">
                        Streaming URL: <code className="bg-gray-100 px-1 rounded">{fileStreamUrl}</code>
                      </div>
                      <img
                        src={fileStreamUrl}
                        alt="Streamed file"
                        className="max-w-full h-auto rounded border"
                        onError={() => console.error('Failed to load streamed image')}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Statistics Tab */}
          {selectedTab === 'stats' && (
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Streaming Statistics</h3>
              <p className="text-sm text-gray-600 mb-6">
                Monitor active streams, bandwidth usage, and performance metrics.
              </p>

              <button
                onClick={loadStats}
                disabled={loadingStats}
                className="mb-6 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {loadingStats ? 'Loading...' : 'Refresh Statistics'}
              </button>

              {stats && (
                <div className="space-y-6">
                  {/* Overview */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {stats.data?.total_active_streams || 0}
                      </div>
                      <div className="text-sm text-blue-600">Active Streams</div>
                    </div>

                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        {Math.round((stats.data?.total_bytes_sent || 0) / 1024 / 1024 * 100) / 100} MB
                      </div>
                      <div className="text-sm text-green-600">Total Data Sent</div>
                    </div>

                    <div className="bg-purple-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-purple-600">
                        {stats.data?.camera_streams?.active_streams || 0}
                      </div>
                      <div className="text-sm text-purple-600">Camera Streams</div>
                    </div>
                  </div>

                  {/* Detailed Stats */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h4 className="font-medium text-gray-700 mb-3">Detailed Statistics</h4>
                    <pre className="text-xs bg-white p-3 rounded border overflow-auto max-h-96">
                      {JSON.stringify(stats, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};