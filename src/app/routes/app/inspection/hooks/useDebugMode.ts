import { useState, useEffect } from 'react';
import { useNotifications } from '@/components/ui/notifications';
import { RecentInspection, fetchPresentationImages, fetchRecentInspections } from '@/features/inspections/api/inspections-details';
import { UseDebugModeReturn } from '../types';
import { isDebugModeEnabled, shouldShowDebugPanelButton } from '@/utils/settingsReader';

/**
 * Hook for managing debug mode functionality
 * @returns Debug mode state and functions
 */
export const useDebugMode = (): UseDebugModeReturn => {
  const [debugMode, setDebugMode] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useState(false);
  const [debugInspectionId, setDebugInspectionId] = useState<string>("");
  const [recentInspections, setRecentInspections] = useState<RecentInspection[]>([]);
  const [loadingInspections, setLoadingInspections] = useState(false);
  const [loadingPresentationImages, setLoadingPresentationImages] = useState(false);
  const [testImageUrl, setTestImageUrl] = useState<string>('');
  const [showTestImage, setShowTestImage] = useState<boolean>(false);
  
  const { addNotification } = useNotifications();

  // Check debug mode on component mount - Uses the settings.ini debug_mode setting
  useEffect(() => {
    const checkDebugMode = async () => {
      try {
        // Use our utility function to check if debug mode is enabled in settings.ini
        const debugModeEnabled = await isDebugModeEnabled();
        
        console.log('Debug mode from settings.ini:', debugModeEnabled);
        
        // Set debug mode based on settings.ini
        setDebugMode(debugModeEnabled);
        
        // Check if we should show the debug panel button based on show_debug_panel in settings.ini
        const showDebugPanelEnabled = await shouldShowDebugPanelButton();
        console.log('Show debug panel from settings.ini:', showDebugPanelEnabled);
        
        // If debug mode is disabled in settings.ini, hide the debug panel and don't show the button
        if (!debugModeEnabled) {
          setShowDebugPanel(false);
          
          // Log that debug mode is disabled
          console.log('Debug mode is disabled in settings.ini - hiding debug panels and controls');
        } else {
          // Debug mode is enabled, check if we should show the debug panel based on the specific setting
          if (!showDebugPanelEnabled) {
            setShowDebugPanel(false);
            console.log('Debug mode is enabled but show_debug_panel is disabled - hiding debug panel');
          } else {
            // Both debug_mode and show_debug_panel are enabled
            console.log('Debug mode and show_debug_panel are both enabled - showing debug panels and controls');
          }
        }
      } catch (error) {
        console.error('Failed to check debug mode:', error);
        // Default to false to ensure debug mode is disabled if there's an error
        setDebugMode(false);
        setShowDebugPanel(false);
      }
    };
    checkDebugMode();
  }, []);

  // Function to load recent inspections for the debug panel - only when explicitly called
  const loadRecentInspections = async () => {
    try {
      setLoadingInspections(true);
      console.log('Manually fetching recent inspections');
      
      const result = await fetchRecentInspections(10); // Get the 10 most recent inspections
      
      if (result.result && result.data) {
        console.log(`Loaded ${result.data.length} recent inspections`);
        setRecentInspections(result.data);
      } else {
        console.error('Failed to load recent inspections:', result.message);
      }
    } catch (error) {
      console.error('Error loading recent inspections:', error);
    } finally {
      setLoadingInspections(false);
    }
  };

  // Function to load images for a specific inspection ID
  const loadImagesForInspectionId = async (manualId?: number): Promise<void> => {
    // Use either the provided ID or parse from the input field
    const id = manualId || parseInt(debugInspectionId);
    
    if (isNaN(id)) {
      addNotification({
        type: 'error',
        title: 'エラー',
        message: '有効な検査IDを入力してください'
      });
      return;
    }
    
    try {
      setLoadingPresentationImages(true);
      console.log(`Manually loading images for inspection ID: ${id}`);
      
      const result = await fetchPresentationImages({ id });
      
      if (result.result && result.data) {
        console.log(`Found ${result.data.length} presentation images for inspection ${id}`);
        
        addNotification({
          type: 'success',
          title: '画像読み込み完了',
          message: `検査ID: ${id} の画像を表示しました`
        });
        
        // The actual state update is handled in the parent component, we're just logging here
        console.log('Images found, parent component will handle state update');
      } else {
        console.log(`No presentation images found for inspection ${id}`);
        addNotification({
          type: 'warning',
          title: '画像なし',
          message: `検査ID: ${id} の画像が見つかりませんでした`
        });
      }
    } catch (error) {
      console.error(`Error loading images for inspection ${id}:`, error);
      addNotification({
        type: 'error',
        title: 'エラー',
        message: '画像の読み込みに失敗しました'
      });
    } finally {
      setLoadingPresentationImages(false);
    }
  };

  // Function to test an image URL
  const testImage = (imagePath: string) => {
    if (!imagePath) return;
    
    // Test various approaches to loading the image
    console.log(`Testing image URL for path: ${imagePath}`);
    
    // 1. Try the standard API path approach
    const standardUrl = `/api/file?path=${encodeURIComponent(imagePath)}`;
    console.log(`Test approach 1 - Standard API path: ${standardUrl}`);
    
    // 2. Try extracting filename only
    const filename = imagePath.split(/[\\/]/).pop();
    if (filename) {
      const filenameUrl = `/api/file?path=${encodeURIComponent(filename)}&convert=jpg`;
      console.log(`Test approach 2 - Filename only: ${filenameUrl}`);
    }
    
    // 3. Try extracting date folder if available
    const datePattern = imagePath.match(/\d{8}_\d{4}/g);
    if (datePattern && datePattern.length > 0 && filename) {
      const dateFolder = datePattern[datePattern.length - 1];
      const dateFolderUrl = `/api/file?path=${encodeURIComponent(`src-api/data/images/inspection/${dateFolder}/${filename}`)}&convert=jpg`;
      console.log(`Test approach 3 - Date folder: ${dateFolderUrl}`);
      
      // Use this as our primary test URL since it's likely to work
      setTestImageUrl(dateFolderUrl);
    } else {
      // Fall back to standard URL
      setTestImageUrl(standardUrl);
    }
    
    setShowTestImage(true);
    
    // Show a notification to the user
    addNotification({
      type: 'info',
      title: '画像テスト',
      message: '画像の読み込みテストを開始しました。コンソールをご確認ください。'
    });
  };

  return {
    debugMode,
    showDebugPanel,
    setShowDebugPanel,
    debugInspectionId,
    setDebugInspectionId,
    recentInspections,
    loadingInspections,
    loadingPresentationImages,
    loadRecentInspections,
    loadImagesForInspectionId,
    testImageUrl,
    showTestImage,
    setShowTestImage,
    testImage
  };
};