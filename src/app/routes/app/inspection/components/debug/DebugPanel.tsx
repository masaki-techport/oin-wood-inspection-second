import React, { useState, useRef, useEffect } from 'react';
import { DebugPanelProps } from '../../types';
import { WorkflowResponse, headersToObject, FileWithPath } from './types';
import { isDebugModeEnabled } from '../../../../../../utils/settingsReader';

/**
 * Debug panel component for development and testing
 */
const DebugPanel: React.FC<DebugPanelProps> = ({
  debugMode,
  createdInspectionId,
  presentationImages,
  loadPresentationImages,
  loadRecentInspections,
  recentInspections,
  loadingPresentationImages,
  loadingInspections,
  onImageTest,
  showDebugPanel, // Add this prop
  setShowDebugPanel // Add this prop
}) => {
  const [debugInspectionId, setDebugInspectionId] = useState<string>("");
  const [showTestImage, setShowTestImage] = useState<boolean>(false);
  const [testImageUrl, setTestImageUrl] = useState<string>('');
  const [selectedFolder, setSelectedFolder] = useState<string>('');
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [analysisMethod, setAnalysisMethod] = useState<string>('single');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // We no longer need forceDebugMode as we'll read from settings.ini directly

  // Handle folder selection
  const handleFolderSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    try {
      // Filter for image files
      const imageExtensions = [".jpg", ".jpeg", ".png", ".bmp", ".webp"];
      const images = Array.from(files).filter(file => {
        const fileObj = file as File;
        const extension = fileObj.name.toLowerCase().slice(fileObj.name.lastIndexOf("."));
        return imageExtensions.includes(extension);
      });

      // Get folder name from the first file's path
      // Safely access webkitRelativePath which is available when using webkitdirectory
      const firstFile = files[0] as FileWithPath;
      if (!firstFile.webkitRelativePath) {
        throw new Error("No directory selected. Please select a folder containing images.");
      }
      
      const path = firstFile.webkitRelativePath;
      const folderName = path.split("/")[0];

      setSelectedFolder(folderName);
      setImageFiles(images as File[]);
      console.log(`Selected folder ${folderName} with ${images.length} images`);
      
      // Show notification if no images were found
      if (images.length === 0) {
        const warningEvent = new CustomEvent('notificationRequest', {
          detail: {
            type: 'warning',
            title: 'No Images Found',
            message: `No supported image files found in the selected folder. Supported formats: JPG, PNG, BMP, WEBP.`
          }
        });
        window.dispatchEvent(warningEvent);
      }
    } catch (error) {
      console.error('Error selecting folder:', error);
      // Show error notification
      const errorEvent = new CustomEvent('notificationRequest', {
        detail: {
          type: 'error',
          title: 'Folder Selection Error',
          message: error instanceof Error ? error.message : 'Failed to select folder'
        }
      });
      window.dispatchEvent(errorEvent);
      
      // Reset selection
      setSelectedFolder('');
      setImageFiles([]);
    }
  };

  // Analyze a single image using BaslerCamera image_analyzer
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const analyzeSelectedImages = async () => {
    if (imageFiles.length === 0) return;

    try {
      setAnalyzing(true);
      console.log(`Analyzing ${imageFiles.length} images from folder ${selectedFolder}`);

      // Process first image as a proof of concept
      const firstImage = imageFiles[0];
      console.log('First image:', firstImage.name, firstImage.type, firstImage.size);

      // Create a URL for the image preview for display
      const imageUrl = URL.createObjectURL(firstImage);
      console.log('Created URL for image preview:', imageUrl);

      // Create form data for API request
      const formData = new FormData();
      formData.append('file', firstImage);

      // Call the BaslerCamera image analyzer endpoint
      console.log('Calling BaslerCamera image analyzer endpoint...');
      let response;
      let result;

      try {
        // First try using the BaslerCamera analyzer
        response = await fetch('/api/inference/analyze-with-basler', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          console.warn(`BaslerCamera analyzer responded with status: ${response.status}`);
          throw new Error(`API responded with status: ${response.status}`);
        }

        result = await response.json();
        console.log('Analysis result from BaslerCamera analyzer:', result);
      } catch (analyzerError) {
        // If BaslerCamera analyzer fails, try with standard inference endpoint
        console.warn('Error with BaslerCamera analyzer, falling back to standard inference:', analyzerError);

        try {
          console.log('Using standard inference endpoint as fallback...');
          response = await fetch('/api/inference/predict', {
            method: 'POST',
            body: formData
          });

          if (!response.ok) {
            throw new Error(`Fallback API responded with status: ${response.status}`);
          }

          result = await response.json();
          console.log('Analysis result from standard inference:', result);
        } catch (fallbackError) {
          console.error('Both analysis methods failed, using simulation as last resort');

          // Define detection type for simulation
          interface Detection {
            class_id: number;
            class_name: string;
            confidence: number;
            bbox: number[];
          }

          // Create simulated result as last resort
          result = {
            result: true,
            data: {
              total_detections: Math.floor(Math.random() * 5),
              detections: [] as Detection[]
            }
          };

          // Generate random detections for simulation
          for (let i = 0; i < result.data.total_detections; i++) {
            const classId = Math.floor(Math.random() * 6); // 0-5 for different types
            const className = [
              '変色',      // discoloration  
              '穴',        // hole
              '死に節',     // knot_dead
              '流れ節(死)', // flow_dead
              '流れ節(生)', // flow_live
              '生き節',     // knot_live
            ][classId];

            result.data.detections.push({
              class_id: classId,
              class_name: className,
              confidence: 0.5 + Math.random() * 0.5, // 0.5-1.0
              bbox: [
                Math.random() * 300, // x
                Math.random() * 200, // y
                50 + Math.random() * 100, // width
                50 + Math.random() * 100  // height
              ]
            });
          }

          console.log('Using simulated analysis result as fallback:', result);
        }
      }

      // Use the result (whether from API or simulation)
      {
        // Use the image URL directly
        let resultImageUrl = imageUrl;

        // Create a timestamp for the inspection
        const timestamp = Date.now();

        // Extract inspection details from API result or use defaults
        const analysisData = result.data || {};
        const detections = analysisData.detections || [];
        const totalDetections = analysisData.total_detections || detections.length || 0;

        // Create inspection data from the analysis result
        const fakeInspectionData = {
          inspection_id: timestamp,
          inspection_dt: new Date(timestamp).toISOString(),
          confidence_above_threshold: true,
          ai_threshold: 50,
          inspection_details: Array.isArray(detections)
            ? detections.map((detection: any, index: number) => ({
              id: index + 1,
              error_type: detection.class_id,
              error_type_name: detection.class_name,
              x_position: detection.bbox[0],
              y_position: detection.bbox[1],
              width: detection.bbox[2],
              height: detection.bbox[3],
              length: Math.max(detection.bbox[2], detection.bbox[3]) / 100,
              confidence: detection.confidence,
              image_path: firstImage.name
            }))
            : [],
          results: totalDetections > 0 ? '節あり' : '無欠点',
          status: totalDetections > 0 ? true : false, // true means defects found
          knot_counts: analysisData.knot_counts || {}
        };

        console.log('Created inspection from analysis:', fakeInspectionData);

        // Create and dispatch inspection data update event
        const event = new CustomEvent('inspectionDataUpdate', {
          detail: fakeInspectionData
        });
        window.dispatchEvent(event);

        // Create presentation images with both original and result image
        const presentationImages = [
          {
            id: timestamp,
            inspection_id: timestamp,
            group_name: 'Original',
            image_path: imageUrl,
            created_at: new Date().toISOString()
          }
        ];

        // Add a result image if available from the API, otherwise use the original
        if (analysisData.result_image) {
          try {
            const blob = await (await fetch(`data:image/jpeg;base64,${analysisData.result_image}`)).blob();
            const annotatedImageUrl = URL.createObjectURL(blob);

            presentationImages.push({
              id: timestamp + 1,
              inspection_id: timestamp,
              group_name: 'Analysis',
              image_path: annotatedImageUrl,
              created_at: new Date().toISOString()
            });

            // Update result image URL
            resultImageUrl = annotatedImageUrl;
          } catch (imageError) {
            console.error('Error creating annotated image URL:', imageError);
            // Fall back to using the original image
            presentationImages.push({
              id: timestamp + 1,
              inspection_id: timestamp,
              group_name: 'Analysis (fallback)',
              image_path: imageUrl,
              created_at: new Date().toISOString()
            });
          }
        } else {
          // No annotated image available, use original
          presentationImages.push({
            id: timestamp + 1,
            inspection_id: timestamp,
            group_name: 'Analysis (simulated)',
            image_path: imageUrl,
            created_at: new Date().toISOString()
          });
        }

        // Trigger presentation images updated event
        const presentationEvent = new CustomEvent('presentationImagesUpdated', {
          detail: {
            images: presentationImages,
            inspectionId: timestamp,
            inspectionDt: new Date(timestamp).toISOString()
          }
        });
        window.dispatchEvent(presentationEvent);

        // Show success notification
        const successEvent = new CustomEvent('notificationRequest', {
          detail: {
            type: 'success',
            title: 'Analysis Complete',
            message: `Found ${totalDetections} defects in the image`
          }
        });
        window.dispatchEvent(successEvent);

        // Update test image URL to show the analyzed image
        if (resultImageUrl) {
          setTestImageUrl(resultImageUrl);
          setShowTestImage(true);
        }
      }
    } catch (err) {
      console.error('Error analyzing image:', err);
      // Show error in UI
      const errorEvent = new CustomEvent('notificationRequest', {
        detail: {
          type: 'error',
          title: 'Analysis Error',
          message: `Failed to analyze image: ${err instanceof Error ? err.message : 'Unknown error'}`
        }
      });
      window.dispatchEvent(errorEvent);
    } finally {
      setAnalyzing(false);
    }
  };

  // Test the full BaslerCamera workflow including ImageAnalyzer and PresentationProcessor
  const analyzeWithFullWorkflow = async () => {
    // Check if files are selected
    if (imageFiles.length === 0) {
      const errorEvent = new CustomEvent('notificationRequest', {
        detail: {
          type: 'error',
          title: 'No Images Selected',
          message: 'Please select a folder with images first.'
        }
      });
      window.dispatchEvent(errorEvent);
      return;
    }

    try {
      setAnalyzing(true);
      setAnalysisMethod('workflow');
      console.log(`Testing full BaslerCamera workflow with ${imageFiles.length} images`);

      // Create a FormData object with multiple files
      const formData = new FormData();

      // Add up to 5 images (to match the presentation processor's grouping)
      const imagesToProcess = imageFiles.slice(0, Math.min(5, imageFiles.length));
      
      // Validate files before appending to FormData
      if (imagesToProcess.length === 0) {
        const errorMsg = 'No valid image files found in the selected folder.';
        console.error(errorMsg);
        throw new Error(errorMsg);
      }
      
      // Log file details for debugging
      console.log('Files to process:');
      imagesToProcess.forEach((file, index) => {
        console.log(`File ${index + 1}/${imagesToProcess.length}:`, {
          name: file.name,
          type: file.type,
          size: `${(file.size / 1024).toFixed(2)} KB`,
          lastModified: new Date(file.lastModified).toISOString()
        });
      });
      
      // Append files with the key 'files' as expected by the backend API
      imagesToProcess.forEach((file, index) => {
        formData.append('files', file);
        console.log(`Appending file ${index + 1}/${imagesToProcess.length}: ${file.name} (${file.type}, ${file.size} bytes)`);
      });

      // Define the API endpoint URL
      const apiEndpoint = '/api/inference/test-basler-workflow';
      
      // Call the BaslerCamera workflow test endpoint with proper headers
      console.log(`Calling full workflow test endpoint (${apiEndpoint}) with ${imagesToProcess.length} images...`);
      
      let response: Response | undefined;
      let usedFallback = false;
      let fallbackReason = '';
      
      try {
        response = await fetch(apiEndpoint, {
          method: 'POST',
          headers: {
            // Don't set Content-Type header when using FormData as it will be set automatically with the correct boundary
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: formData
        });
      } catch (networkError) {
        // Handle network-level errors (like CORS, network disconnection)
        console.error('Network error during API request:', networkError);
        fallbackReason = `Network error: ${networkError instanceof Error ? networkError.message : 'Unable to connect to the API'}`;
        console.log('Falling back to simulation mode due to network error');
        usedFallback = true;
      }

      let workflowResult: WorkflowResponse | undefined;
      let presentationTestResult: WorkflowResponse | undefined;
      
      // Only check response if we didn't use fallback yet
      if (!usedFallback && response) {
        // Check for specific HTTP status codes with detailed error messages
        if (!response.ok) {
          let errorDetails = 'No error details available';
          try {
            // Try to parse error response as JSON first
            const errorJson = await response.json().catch(() => null);
            if (errorJson) {
              errorDetails = errorJson.message || errorJson.error || JSON.stringify(errorJson);
            } else {
              // Fall back to text if not JSON
              errorDetails = await response.text().catch(() => 'No error details available');
            }
          } catch (parseError) {
            console.error('Error parsing error response:', parseError);
          }
          
          // Log detailed error information
          console.error(`API error (${response.status} ${response.statusText}):`, {
            endpoint: apiEndpoint,
            status: response.status,
            statusText: response.statusText,
            details: errorDetails,
            headers: headersToObject(response.headers)
          });
          
          // Create specific error messages based on status code
          let errorMessage = '';
          switch (response.status) {
            case 400:
              errorMessage = `Bad request: The API couldn't process the images. ${errorDetails}`;
              break;
            case 401:
              errorMessage = 'Authentication required: Please log in again.';
              break;
            case 403:
              errorMessage = 'Access denied: You don\'t have permission to use this feature.';
              break;
            case 404:
              errorMessage = 'API endpoint not found: The test-basler-workflow endpoint may have been moved or renamed.';
              break;
            case 413:
              errorMessage = 'Images too large: The selected images exceed the maximum allowed size.';
              break;
            case 500:
            case 502:
            case 503:
            case 504:
              errorMessage = `Server error (${response.status}): The backend service encountered an error. ${errorDetails}`;
              break;
            default:
              errorMessage = `API responded with status: ${response.status}. ${response.statusText}. ${errorDetails}`;
          }
          
          fallbackReason = errorMessage;
          console.log(`Falling back to simulation mode due to API error: ${errorMessage}`);
          usedFallback = true;
        }
      }

      // Try to parse the response if we haven't fallen back yet
      if (!usedFallback) {
        try {
          workflowResult = await response!.json() as WorkflowResponse;
          console.log('Full workflow test result:', workflowResult);
          
          // Validate the response structure with more detailed checks
          if (!workflowResult) {
            fallbackReason = 'Empty response received from the API.';
            console.log('Falling back to simulation mode due to empty response');
            usedFallback = true;
          } else if (!workflowResult.result) {
            // Handle API-level errors (when result is false)
            const errorMessage = workflowResult.message || 'Unknown error occurred in the workflow test.';
            console.error('API returned error:', errorMessage, workflowResult);
            fallbackReason = `API error: ${errorMessage}`;
            console.log(`Falling back to simulation mode due to API result error: ${errorMessage}`);
            usedFallback = true;
          } else if (!workflowResult.data) {
            fallbackReason = 'Missing data in API response.';
            console.log('Falling back to simulation mode due to missing data in response');
            usedFallback = true;
          } else {
            // Additional validation for required fields
            const data = workflowResult.data;
            
            // Check for inspection_id
            if (!data.inspection_id) {
              console.warn('Missing inspection_id in API response data:', data);
              fallbackReason = 'Missing inspection ID in API response.';
              console.log('Falling back to simulation mode due to missing inspection ID');
              usedFallback = true;
            } 
            // Check for analysis_results
            else if (!data.analysis_results || !Array.isArray(data.analysis_results) || data.analysis_results.length === 0) {
              console.warn('Missing or empty analysis_results in API response data:', data);
              // Don't fall back yet, we can still use the inspection_id and presentation_results if available
              console.log('API response missing analysis_results, will use defaults');
            }
            // Check for presentation_results
            else if (!data.presentation_results) {
              console.warn('Missing presentation_results in API response data:', data);
              // Don't fall back yet, we can still use the inspection_id and analysis_results
              console.log('API response missing presentation_results, will use defaults');
            }
            
            // Log the validated data structure for debugging
            console.log('Validated API response data structure:', {
              has_inspection_id: !!data.inspection_id,
              has_analysis_results: !!data.analysis_results && Array.isArray(data.analysis_results),
              analysis_results_count: data.analysis_results && Array.isArray(data.analysis_results) ? data.analysis_results.length : 0,
              has_presentation_results: !!data.presentation_results,
              has_presentation_images: data.presentation_results && Array.isArray(data.presentation_results.presentation_images),
              presentation_images_count: data.presentation_results && data.presentation_results.presentation_images ? data.presentation_results.presentation_images.length : 0
            });
          }
        } catch (parseError) {
          console.error('Error parsing API response as JSON:', parseError);
          fallbackReason = 'Invalid response format: The API returned an invalid JSON response.';
          console.log('Falling back to simulation mode due to JSON parse error');
          usedFallback = true;
        }
      }

      // If we need to use fallback, create simulated results - but only as a last resort
      if (usedFallback) {
        console.log('Using simulation mode for full workflow test - FALLBACK MODE');
        console.log('Fallback reason:', fallbackReason);
        
        // Show notification about falling back to simulation with more detailed reason
        const warningEvent = new CustomEvent('notificationRequest', {
          detail: {
            type: 'warning',
            title: 'Using Simulation Mode (Fallback)',
            message: `API issue: ${fallbackReason}. Using simulation mode as fallback.`
          }
        });
        window.dispatchEvent(warningEvent);
        
        // Create a simulated inspection ID with timestamp for uniqueness
        const simulatedInspectionId = Date.now();
        console.log('Created simulated inspection ID:', simulatedInspectionId);
        
        // Create simulated presentation images using the actual uploaded images
        const simulatedPresentationImages = [];
        
        // Create URLs for the original images with clear simulation markers
        console.log(`Creating ${imagesToProcess.length} simulated presentation images`);
        for (let i = 0; i < imagesToProcess.length; i++) {
          const file = imagesToProcess[i];
          const imageUrl = URL.createObjectURL(file);
          
          // Add clear simulation markers in the group name
          const groupName = i === 0 ? 'Original (Simulated)' : `Simulated View ${i+1}`;
          
          simulatedPresentationImages.push({
            id: simulatedInspectionId + i,
            inspection_id: simulatedInspectionId,
            group_name: groupName,
            image_path: imageUrl,
            created_at: new Date().toISOString(),
            is_simulated: true // Add flag to indicate this is simulated data
          });
          
          console.log(`Created simulated presentation image ${i+1}/${imagesToProcess.length}: ${groupName}`);
        }
        
        // Generate simulated defects for the analysis results - with consistent patterns
        // instead of completely random values
        const simulatedDefects = [];
        
        // Use a deterministic approach based on the image content rather than pure randomness
        // For this example, we'll use the file size as a seed for "defect count"
        const totalFileSize = imagesToProcess.reduce((sum, file) => sum + file.size, 0);
        const defectCount = Math.min(5, Math.max(0, Math.floor(totalFileSize / 100000) % 6)); // 0-5 defects
        
        console.log(`Creating ${defectCount} simulated defects based on file characteristics`);
        
        const defectTypes = [
          { id: 1, name: '変色' },      // discoloration
          { id: 2, name: '穴' },        // hole
          { id: 3, name: '死に節' },     // knot_dead
          { id: 4, name: '流れ節(死)' }, // flow_dead
          { id: 5, name: '流れ節(生)' }, // flow_live
          { id: 6, name: '生き節' },     // knot_live
        ];
        
        for (let i = 0; i < defectCount; i++) {
          // Use a more deterministic approach for selecting defect type
          const defectTypeIndex = (i + Math.floor(totalFileSize / 10000)) % defectTypes.length;
          const defectType = defectTypes[defectTypeIndex];
          
          // Create defect with more realistic positioning
          simulatedDefects.push({
            id: i + 1,
            error_type: defectType.id,
            error_type_name: defectType.name,
            x_position: 50 + (i * 50) % 250, // More evenly distributed
            y_position: 50 + (i * 40) % 150,
            width: 40 + (i * 10) % 60,
            height: 40 + (i * 10) % 60,
            length: (40 + (i * 10) % 60) / 100,
            confidence: 0.7 + (i * 0.05) % 0.3, // Higher confidence values
            image_path: imagesToProcess[0].name,
            is_simulated: true // Add flag to indicate this is simulated data
          });
          
          console.log(`Created simulated defect ${i+1}/${defectCount}: ${defectType.name}`);
        }
        
        // Create simulated inspection data with clear simulation markers
        const simulatedInspectionData = {
          inspection_id: simulatedInspectionId,
          inspection_dt: new Date().toISOString(),
          confidence_above_threshold: true,
          ai_threshold: 50,
          inspection_details: simulatedDefects,
          results: defectCount > 0 ? '節あり' : '無欠点',
          status: defectCount > 0,
          presentation_ready: true,
          presentation_images: simulatedPresentationImages,
          is_simulated: true, // Add flag to indicate this is simulated data
          simulation_reason: fallbackReason // Add the reason for simulation
        };
        
        console.log('Created simulated inspection data:', simulatedInspectionData);
        
        // Create and dispatch inspection data update event
        try {
          console.log('Dispatching simulated inspection data update event');
          const event = new CustomEvent('inspectionDataUpdate', {
            detail: simulatedInspectionData
          });
          window.dispatchEvent(event);
          console.log('Simulated inspection data update event dispatched successfully');
        } catch (eventError) {
          console.error('Error dispatching simulated inspection data event:', eventError);
        }
        
        // Create presentation images event
        try {
          console.log('Dispatching simulated presentation images event');
          const presentationEvent = new CustomEvent('presentationImagesUpdated', {
            detail: {
              images: simulatedPresentationImages,
              inspectionId: simulatedInspectionId,
              inspectionDt: new Date().toISOString(),
              is_simulated: true // Add flag to indicate this is simulated data
            }
          });
          window.dispatchEvent(presentationEvent);
          console.log('Simulated presentation images event dispatched successfully');
        } catch (eventError) {
          console.error('Error dispatching simulated presentation images event:', eventError);
        }
        
        // Show success notification with clear indication this is simulated data
        const successEvent = new CustomEvent('notificationRequest', {
          detail: {
            type: 'info', // Use info instead of success to differentiate from real API success
            title: 'Workflow Test Complete (SIMULATED DATA)',
            message: `Processed ${imagesToProcess.length} images with SIMULATED workflow. Created ${simulatedPresentationImages.length} presentation images. This is NOT real API data.`
          }
        });
        window.dispatchEvent(successEvent);
        
        // Show first presentation image if available
        if (simulatedPresentationImages.length > 0) {
          setTestImageUrl(simulatedPresentationImages[0].image_path);
          setShowTestImage(true);
          console.log('Set test image URL to simulated image:', simulatedPresentationImages[0].image_path);
        }
      } else {
        // Use the actual API results
        // Extract the workflow results
        const workflowData = workflowResult!.data;
        // Use optional chaining and nullish coalescing to safely access inspection_id
        const inspectionId = workflowData?.inspection_id;
        
        if (!workflowData || !inspectionId) {
          console.error('Missing inspection ID in response:', workflowData);
          throw new Error('Invalid response: Missing inspection ID.');
        }
        
        // Extract presentation results with better error handling and validation
        const presentationResults = (workflowData as WorkflowResponse['data'])?.presentation_results || {};
        
        // Validate presentation_images is an array
        let presentationImages: Array<{image_path?: string; group_name?: string}> = [];
        if (presentationResults.presentation_images && Array.isArray(presentationResults.presentation_images)) {
          presentationImages = presentationResults.presentation_images;
        } else {
          console.warn('No valid presentation_images array found in API response, using empty array');
        }

        // Log presentation images for debugging
        console.log(`Received ${presentationImages.length} presentation images from API:`, presentationImages);

        // Create processed images array for the presentation images
        const processedImages = [];

        // Process presentation images with improved error handling
        for (const img of presentationImages as Array<{image_path?: string; group_name?: string}>) {
          if (!img.image_path) {
            console.warn('Missing image path in presentation image:', img);
            continue;
          }
          
          const imgPath = img.image_path;
          console.log('Processing image path:', imgPath);
          
          // Create URL for the API based on the image path format
          let apiUrl;
          
          try {
            // Check if the image path is already a full URL
            if (imgPath.startsWith('http://') || imgPath.startsWith('https://')) {
              // Already a full URL, use as is
              apiUrl = imgPath;
              console.log('Using full URL from API response:', apiUrl);
            } 
            // Check if it's a base64 encoded image
            else if (imgPath.startsWith('data:image/')) {
              // Base64 image, use as is
              apiUrl = imgPath;
              console.log('Using base64 image from API response');
            }
            // Check if it's an absolute path starting with /
            else if (imgPath.startsWith('/')) {
              // Absolute path, construct URL with origin
              const baseUrl = window.location.origin;
              apiUrl = `${baseUrl}/api/file?path=${encodeURIComponent(imgPath.substring(1))}`;
              console.log('Constructed API URL for absolute path:', apiUrl);
            }
            // Must be a relative path
            else {
              // Construct a relative URL that works in any environment
              const baseUrl = window.location.origin;
              apiUrl = `${baseUrl}/api/file?path=${encodeURIComponent(imgPath)}`;
              console.log('Constructed API URL for relative path:', apiUrl);
            }
          } catch (pathError) {
            console.error('Error processing image path:', pathError);
            // Use a fallback URL that indicates the error
            apiUrl = `${window.location.origin}/no-image.png`;
            console.log('Using fallback image URL due to path processing error');
          }

          // Add to processed images
          processedImages.push({
            id: Date.now() + Math.random(),
            inspection_id: inspectionId,
            group_name: img.group_name || 'Unknown',
            image_path: apiUrl,
            created_at: new Date().toISOString()
          });
        }

        // Extract analysis results with better error handling and logging
        const analysisResults = (workflowData as WorkflowResponse['data'])?.analysis_results || [];
        console.log('Analysis results from API:', analysisResults);
        
        // Extract the first analysis result (if available)
        const firstAnalysisResult = analysisResults[0] || {};
        console.log('First analysis result:', firstAnalysisResult);
        
        // Extract inspection details with validation
        let inspectionDetails = [];
        if (firstAnalysisResult.inspection_details && Array.isArray(firstAnalysisResult.inspection_details)) {
          inspectionDetails = firstAnalysisResult.inspection_details;
          console.log(`Found ${inspectionDetails.length} inspection details in API response`);
        } else {
          console.warn('No valid inspection details found in API response, using empty array');
        }
        
        // Extract results with validation
        let results = '節あり'; // Default to showing defects
        let status = true;      // Default to defects found
        
        if (typeof firstAnalysisResult.results === 'string') {
          results = firstAnalysisResult.results;
          // Update status based on results (true means defects found)
          status = results === '節あり';
          console.log(`Using results from API: "${results}", status: ${status}`);
        } else {
          console.warn('No valid results found in API response, using default: 節あり');
        }
        
        // Create inspection data from the workflow results with validated data
        const inspectionData = {
          inspection_id: inspectionId,
          inspection_dt: new Date().toISOString(),
          confidence_above_threshold: true,
          ai_threshold: 50,
          inspection_details: inspectionDetails,
          results: results,
          status: status,
          presentation_ready: true,
          presentation_images: processedImages
        };
        
        console.log('Created inspection data from workflow with validated details:', inspectionData);

        // Create and dispatch inspection data update event with error handling
        try {
          console.log('Dispatching inspection data update event with data:', inspectionData);
          const event = new CustomEvent('inspectionDataUpdate', {
            detail: inspectionData
          });
          window.dispatchEvent(event);
          console.log('Inspection data update event dispatched successfully');
        } catch (eventError) {
          console.error('Error dispatching inspection data update event:', eventError);
        }

        // Create presentation images event with error handling
        if (processedImages.length > 0) {
          try {
            console.log('Dispatching presentation images updated event with images:', processedImages);
            const presentationEvent = new CustomEvent('presentationImagesUpdated', {
              detail: {
                images: processedImages,
                inspectionId: inspectionId,
                inspectionDt: new Date().toISOString()
              }
            });
            window.dispatchEvent(presentationEvent);
            console.log('Presentation images updated event dispatched successfully');
            
            // Show success notification with details
            const successEvent = new CustomEvent('notificationRequest', {
              detail: {
                type: 'success',
                title: 'Workflow Test Complete',
                message: `Processed ${imagesToProcess.length} images with BaslerCamera workflow. Created ${processedImages.length} presentation images.`
              }
            });
            window.dispatchEvent(successEvent);

            // Show first presentation image if available
            if (processedImages[0] && processedImages[0].image_path) {
              setTestImageUrl(processedImages[0].image_path);
              setShowTestImage(true);
              console.log('Set test image URL to:', processedImages[0].image_path);
            } else {
              console.warn('First presentation image has no valid image_path');
            }
          } catch (eventError) {
            console.error('Error dispatching presentation images event:', eventError);
            
            // Show error notification
            const errorEvent = new CustomEvent('notificationRequest', {
              detail: {
                type: 'error',
                title: 'Event Dispatch Error',
                message: `Error updating presentation images: ${eventError instanceof Error ? eventError.message : 'Unknown error'}`
              }
            });
            window.dispatchEvent(errorEvent);
          }
        } else {
          // No presentation images were generated
          console.warn('No presentation images were generated from the workflow test.');
          const warningEvent = new CustomEvent('notificationRequest', {
            detail: {
              type: 'warning',
              title: 'Workflow Test Incomplete',
              message: 'The workflow completed but no presentation images were generated.'
            }
          });
          window.dispatchEvent(warningEvent);
        }
      }
    } catch (err) {
      // Enhanced error logging with more context
      console.error('Error testing BaslerCamera workflow:', err);
      
      // Log detailed error information for debugging
      console.error('Error details:', {
        message: err instanceof Error ? err.message : 'Unknown error',
        stack: err instanceof Error ? err.stack : undefined,
        name: err instanceof Error ? err.name : undefined,
        timestamp: new Date().toISOString(),
        context: {
          imageCount: imageFiles.length,
          selectedFolder: selectedFolder,
          apiEndpoint: '/api/inference/test-basler-workflow'
        }
      });
      
      // Determine error category for better user feedback
      let errorTitle = 'Workflow Test Error';
      let errorMessage = `Failed to test BaslerCamera workflow: ${err instanceof Error ? err.message : 'Unknown error'}`;
      
      if (err instanceof TypeError) {
        errorTitle = 'Data Processing Error';
        errorMessage = `Error processing API response: ${err.message}`;
      } else if (err instanceof SyntaxError) {
        errorTitle = 'API Response Format Error';
        errorMessage = `Invalid API response format: ${err.message}`;
      } else if (err instanceof Error && err.message.includes('fetch')) {
        errorTitle = 'Network Error';
        errorMessage = `Network error while communicating with API: ${err.message}`;
      } else if (err instanceof Error && err.message.includes('Missing inspection ID')) {
        errorTitle = 'API Data Error';
        errorMessage = 'The API response is missing required data (inspection ID)';
      }
      
      // Show detailed error in UI with categorized error
      const errorEvent = new CustomEvent('notificationRequest', {
        detail: {
          type: 'error',
          title: errorTitle,
          message: errorMessage
        }
      });
      window.dispatchEvent(errorEvent);
      
      // Log recovery attempt
      console.log('Attempting to recover from error and clean up resources');
    } finally {
      // Always clean up resources and reset state
      setAnalyzing(false);
      setAnalysisMethod('single');
      console.log('Workflow test completed (success or failure), reset analyzing state');
    }
  };

  // Test just the presentation processor
  const testPresentationProcessor = async () => {
    // Check if files are selected
    if (imageFiles.length === 0) {
      const errorEvent = new CustomEvent('notificationRequest', {
        detail: {
          type: 'error',
          title: 'No Images Selected',
          message: 'Please select a folder with images first.'
        }
      });
      window.dispatchEvent(errorEvent);
      return;
    }

    try {
      setAnalyzing(true);
      setAnalysisMethod('presentation');
      console.log(`Testing presentation processor with ${imageFiles.length} images`);

      // Create a FormData object with multiple files
      const formData = new FormData();

      // Add up to 5 images (to match the presentation processor's grouping)
      const imagesToProcess = imageFiles.slice(0, Math.min(5, imageFiles.length));
      
      // Validate files before appending to FormData
      if (imagesToProcess.length === 0) {
        const errorMsg = 'No valid image files found in the selected folder.';
        console.error(errorMsg);
        throw new Error(errorMsg);
      }
      
      // Log file details for debugging
      console.log('Files to process for presentation test:');
      imagesToProcess.forEach((file, index) => {
        console.log(`File ${index + 1}/${imagesToProcess.length}:`, {
          name: file.name,
          type: file.type,
          size: `${(file.size / 1024).toFixed(2)} KB`,
          lastModified: new Date(file.lastModified).toISOString()
        });
      });
      
      // Append files with the key 'files' as expected by the backend API
      imagesToProcess.forEach((file, index) => {
        formData.append('files', file);
        console.log(`Appending file ${index + 1}/${imagesToProcess.length}: ${file.name} (${file.type}, ${file.size} bytes)`);
      });

      // Define the API endpoint URL
      const apiEndpoint = '/api/inference/presentation-test';
      
      // Call the presentation test endpoint with proper headers
      console.log(`Calling presentation test endpoint (${apiEndpoint}) with ${imagesToProcess.length} images...`);
      
      let response: Response | undefined;
      let usedFallback = false;
      let fallbackReason = '';
      let presentationTestResult: WorkflowResponse | undefined;
      
      try {
        response = await fetch(apiEndpoint, {
          method: 'POST',
          headers: {
            // Don't set Content-Type header when using FormData as it will be set automatically with the correct boundary
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: formData
        });
      } catch (networkError) {
        // Handle network-level errors (like CORS, network disconnection)
        console.error('Network error during presentation test API request:', networkError);
        fallbackReason = `Network error: ${networkError instanceof Error ? networkError.message : 'Unable to connect to the presentation test API'}`;
        console.log('Falling back to simulation mode due to network error');
        usedFallback = true;
      }
      
      // Only check response if we didn't use fallback yet
      if (!usedFallback && response) {
        // Check for specific HTTP status codes with detailed error messages
        if (!response.ok) {
          let errorDetails = 'No error details available';
          try {
            // Try to parse error response as JSON first
            const errorJson = await response.json().catch(() => null);
            if (errorJson) {
              errorDetails = errorJson.message || errorJson.error || JSON.stringify(errorJson);
            } else {
              // Fall back to text if not JSON
              errorDetails = await response.text().catch(() => 'No error details available');
            }
          } catch (parseError) {
            console.error('Error parsing presentation test error response:', parseError);
          }
          
          // Log detailed error information
          console.error(`Presentation test API error (${response.status} ${response.statusText}):`, {
            endpoint: apiEndpoint,
            status: response.status,
            statusText: response.statusText,
            details: errorDetails,
            headers: headersToObject(response.headers)
          });
          
          // Create specific error messages based on status code
          let errorMessage = '';
          switch (response.status) {
            case 400:
              errorMessage = `Bad request: The presentation test API couldn't process the images. ${errorDetails}`;
              break;
            case 401:
              errorMessage = 'Authentication required: Please log in again.';
              break;
            case 403:
              errorMessage = 'Access denied: You don\'t have permission to use the presentation test feature.';
              break;
            case 404:
              errorMessage = 'API endpoint not found: The presentation-test endpoint may have been moved or renamed.';
              break;
            case 413:
              errorMessage = 'Images too large: The selected images exceed the maximum allowed size for presentation testing.';
              break;
            case 500:
            case 502:
            case 503:
            case 504:
              errorMessage = `Server error (${response.status}): The presentation test service encountered an error. ${errorDetails}`;
              break;
            default:
              errorMessage = `Presentation test API responded with status: ${response.status}. ${response.statusText}. ${errorDetails}`;
          }
          
          fallbackReason = errorMessage;
          console.log(`Falling back to simulation mode due to API error: ${errorMessage}`);
          usedFallback = true;
        }
      }

      // Try to parse the response if we haven't fallen back yet
      if (!usedFallback) {
        try {
          presentationTestResult = await response!.json() as WorkflowResponse;
          console.log('Presentation test result:', presentationTestResult);
          
          // Validate the response structure
          if (!presentationTestResult) {
            fallbackReason = 'Empty response received from the presentation test API.';
            console.log('Falling back to simulation mode due to empty response');
            usedFallback = true;
          } else if (!presentationTestResult.result) {
            // Handle API-level errors (when result is false)
            const errorMessage = presentationTestResult.message || 'Unknown error occurred in the presentation test.';
            console.error('Presentation test API returned error:', errorMessage, presentationTestResult);
            fallbackReason = `API error: ${errorMessage}`;
            console.log(`Falling back to simulation mode due to API result error: ${errorMessage}`);
            usedFallback = true;
          } else if (!presentationTestResult.data) {
            fallbackReason = 'Missing data in presentation test API response.';
            console.log('Falling back to simulation mode due to missing data in response');
            usedFallback = true;
          }
        } catch (parseError) {
          console.error('Error parsing presentation test API response as JSON:', parseError);
          fallbackReason = 'Invalid response format: The presentation test API returned an invalid JSON response.';
          console.log('Falling back to simulation mode due to JSON parse error');
          usedFallback = true;
        }
      }

      // If we need to use fallback, create simulated results
      if (usedFallback) {
        console.log('Using simulation mode for presentation processor test');
        
        // Show notification about falling back to simulation
        const warningEvent = new CustomEvent('notificationRequest', {
          detail: {
            type: 'warning',
            title: 'Using Simulation Mode',
            message: `Presentation test API unavailable: ${fallbackReason}. Using simulation mode instead.`
          }
        });
        window.dispatchEvent(warningEvent);
        
        // Create a simulated inspection ID
        const simulatedInspectionId = Date.now();
        
        // Create simulated presentation images using the actual uploaded images
        const simulatedPresentationImages = [];
        
        // Define presentation group types
        const presentationGroups = [
          'Original',
          'Processed',
          'Highlighted',
          'Annotated',
          'Composite'
        ];
        
        // Create URLs for the original images with different simulated processing
        for (let i = 0; i < imagesToProcess.length; i++) {
          const file = imagesToProcess[i];
          const imageUrl = URL.createObjectURL(file);
          
          // Add the original image
          simulatedPresentationImages.push({
            id: simulatedInspectionId + i,
            inspection_id: simulatedInspectionId,
            group_name: presentationGroups[i % presentationGroups.length],
            image_path: imageUrl,
            created_at: new Date().toISOString()
          });
        }
        
        // Create presentation images event
        const presentationEvent = new CustomEvent('presentationImagesUpdated', {
          detail: {
            images: simulatedPresentationImages,
            inspectionId: simulatedInspectionId,
            inspectionDt: new Date().toISOString()
          }
        });
        window.dispatchEvent(presentationEvent);
        
        // Show first presentation image if available
        if (simulatedPresentationImages.length > 0) {
          setTestImageUrl(simulatedPresentationImages[0].image_path);
          setShowTestImage(true);
        }
        
        // Show success notification with details about simulation
        const successEvent = new CustomEvent('notificationRequest', {
          detail: {
            type: 'success',
            title: 'Presentation Test Complete (Simulated)',
            message: `Processed ${imagesToProcess.length} images with simulated presentation processor. Created ${simulatedPresentationImages.length} presentation images.`
          }
        });
        window.dispatchEvent(successEvent);
      } else {
        // Use the actual API results
        // Extract the presentation results
        const testData = presentationTestResult!.data || {};
        const inspectionId = (testData as any).inspection_id as number;
        
        if (!inspectionId) {
          console.error('Missing inspection ID in presentation test response:', testData);
          throw new Error('Invalid presentation test response: Missing inspection ID.');
        }
        
        const presentationResults = (testData as any).presentation_results || {};
        const presentationImages = presentationResults.presentation_images || [];

        // Log presentation images for debugging
        console.log(`Received ${presentationImages.length} presentation images from test:`, presentationImages);

        if (presentationImages.length === 0) {
          console.warn('No presentation images were returned from the API.');
          throw new Error('No presentation images were generated by the API.');
        }

        // Process presentation images
        const processedImages = [];
        for (const img of presentationImages) {
          if (!img.image_path) {
            console.warn('Missing image path in presentation image:', img);
            continue;
          }
          
          const imgPath = img.image_path;
          
          // Create URL for the API based on the image path format
          let apiUrl;
          
          // Check if the image path is already a full URL
          if (imgPath.startsWith('http://') || imgPath.startsWith('https://')) {
            // Already a full URL, use as is
            apiUrl = imgPath;
            console.log('Using full URL from API response:', apiUrl);
          } 
          // Check if it's a base64 encoded image
          else if (imgPath.startsWith('data:image/')) {
            // Base64 image, use as is
            apiUrl = imgPath;
            console.log('Using base64 image from API response');
          }
          // Check if it's a relative path with or without leading slash
          else {
            // Construct a relative URL that works in any environment
            // Use window.location.origin to get the current domain instead of hardcoding
            const baseUrl = window.location.origin;
            apiUrl = `${baseUrl}/api/file?path=${encodeURIComponent(imgPath.replace(/^\//, ''))}`;
            console.log('Constructed API URL for image:', apiUrl);
          }

          // Add to processed images
          processedImages.push({
            id: Date.now() + Math.random(),
            inspection_id: inspectionId,
            group_name: img.group_name || 'Unknown',
            image_path: apiUrl,
            created_at: new Date().toISOString()
          });
        }

        // Create presentation images event
        if (processedImages.length > 0) {
          const presentationEvent = new CustomEvent('presentationImagesUpdated', {
            detail: {
              images: processedImages,
              inspectionId: inspectionId,
              inspectionDt: new Date().toISOString()
            }
          });
          window.dispatchEvent(presentationEvent);

          // Show first presentation image
          setTestImageUrl(processedImages[0].image_path);
          setShowTestImage(true);

          // Show success notification with details
          const successEvent = new CustomEvent('notificationRequest', {
            detail: {
              type: 'success',
              title: 'Presentation Test Complete',
              message: `Successfully processed ${imagesToProcess.length} images and created ${processedImages.length} presentation images.`
            }
          });
          window.dispatchEvent(successEvent);
        } else {
          // This should not happen due to the earlier check, but just in case
          throw new Error('Failed to process any presentation images.');
        }
      }
    } catch (err) {
      // Detailed error logging
      console.error('Error testing presentation processor:', err);
      console.error('Presentation test error details:', {
        message: err instanceof Error ? err.message : 'Unknown error',
        stack: err instanceof Error ? err.stack : undefined,
        name: err instanceof Error ? err.name : undefined
      });
      
      // Show detailed error in UI with specific message
      const errorEvent = new CustomEvent('notificationRequest', {
        detail: {
          type: 'error',
          title: 'Presentation Test Error',
          message: `Failed to test presentation processor: ${err instanceof Error ? err.message : 'Unknown error'}`
        }
      });
      window.dispatchEvent(errorEvent);
    } finally {
      setAnalyzing(false);
      setAnalysisMethod('single');
    }
  };

  // Check if debug mode is enabled from settings.ini
  const [settingsDebugMode, setSettingsDebugMode] = useState<boolean>(false);
  
  // Effect to read debug mode from settings.ini
  useEffect(() => {
    // Read debug mode from settings.ini via our utility
    const checkDebugMode = async () => {
      try {
        const debugModeEnabled = await isDebugModeEnabled();
        console.log('Debug mode from settings.ini:', debugModeEnabled);
        setSettingsDebugMode(debugModeEnabled);
        
        // If debug mode is disabled in settings.ini, hide the debug panel
        if (!debugModeEnabled && setShowDebugPanel) {
          setShowDebugPanel(false);
        }
      } catch (error) {
        console.error('Error checking debug mode:', error);
      }
    };
    
    checkDebugMode();
  }, [setShowDebugPanel]);

  // Only show the debug panel if debug mode is enabled in settings.ini or via props
  if (!debugMode && !settingsDebugMode) return null;

  return (
    <div className="absolute bottom-2 right-2 z-10">
      {/* Debug button is now managed by parent component */}

      {showDebugPanel && (
        <div className="bg-white border-2 border-gray-300 p-4 rounded-lg shadow-lg absolute bottom-8 right-0 w-80">
          <h3 className="text-sm font-bold mb-2 text-gray-700">デバッグパネル</h3>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-600">検査ID:</label>
              <input
                type="number"
                value={debugInspectionId}
                onChange={(e) => setDebugInspectionId(e.target.value)}
                className="border border-gray-300 rounded px-2 py-1 text-xs w-16"
              />
              <button
                onClick={() => {
                  const id = parseInt(debugInspectionId);
                  if (!isNaN(id)) {
                    loadPresentationImages(id);
                  }
                }}
                className={`${loadingPresentationImages ? 'bg-blue-400' : 'bg-blue-500 hover:bg-blue-600'} text-white text-xs px-2 py-1 rounded transition-colors relative`}
                disabled={loadingPresentationImages || analyzing}
              >
                {loadingPresentationImages ? (
                  <>
                    <span className="inline-block mr-1">
                      <svg className="animate-spin h-3 w-3 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    </span>
                    読込中...
                  </>
                ) : '画像取得'}
              </button>
            </div>

            <div className="text-xs text-gray-500">
              現在のID: {createdInspectionId || 'なし'}
            </div>

            <div className="text-xs text-gray-500">
              画像数: {presentationImages.length}
            </div>

            {/* Recent inspections section */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <h4 className="text-xs font-bold text-gray-700">最近の検査</h4>
                <button
                  onClick={loadRecentInspections}
                  className={`text-xs ${loadingInspections ? 'text-blue-300 cursor-not-allowed' : 'text-blue-500 hover:text-blue-700'} transition-colors`}
                  disabled={loadingInspections || analyzing}
                >
                  {loadingInspections ? (
                    <>
                      <span className="inline-block mr-1">
                        <svg className="animate-spin h-3 w-3 text-blue-500 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      </span>
                      読込中...
                    </>
                  ) : '更新'}
                </button>
              </div>

              <div className="border border-gray-200 rounded max-h-32 overflow-y-auto">
                {recentInspections.length === 0 ? (
                  <div className="text-xs text-gray-400 p-2 text-center">
                    {loadingInspections ? '読込中...' : 'データなし'}
                  </div>
                ) : (
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="p-1 border-b">ID</th>
                        <th className="p-1 border-b">日時</th>
                        <th className="p-1 border-b">結果</th>
                        <th className="p-1 border-b">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentInspections.map(inspection => (
                        <tr key={inspection.inspection_id} className="hover:bg-gray-50">
                          <td className="p-1 border-b text-center">{inspection.inspection_id}</td>
                          <td className="p-1 border-b">
                            {new Date(inspection.inspection_dt).toLocaleString('ja-JP', {
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </td>
                          <td className="p-1 border-b text-center">
                            <span className={inspection.status ? 'text-red-500' : 'text-green-500'}>
                              {inspection.status ? '欠点あり' : '無欠点'}
                            </span>
                          </td>
                          <td className="p-1 border-b text-center">
                            <button
                              className="text-blue-500 hover:text-blue-700"
                              onClick={() => {
                                setDebugInspectionId(inspection.inspection_id.toString());
                                loadPresentationImages(inspection.inspection_id);
                              }}
                            >
                              選択
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Test Functions Section */}
            <div className="p-4 border-t border-gray-200">
              <div className="flex flex-col gap-2">
                <span className="text-sm font-semibold text-gray-600">Test Functions:</span>
                <button
                  onClick={async () => {
                    try {
                      // Set analyzing state to show loading indicator
                      setAnalyzing(true);
                      setAnalysisMethod('fake');
                      console.log('Creating fake inspection for testing...');
                      const response = await fetch('/api/sensor-inspection/trigger-fake-inspection', {
                        method: 'POST'
                      });
                      const data = await response.json();
                      console.log('Fake inspection response:', data);

                      // Trigger inspection data update event
                      if (data.inspection_data) {
                        const event = new CustomEvent('inspectionDataUpdate', {
                          detail: data.inspection_data
                        });
                        window.dispatchEvent(event);
                        
                        // Show success notification
                        const successEvent = new CustomEvent('notificationRequest', {
                          detail: {
                            type: 'success',
                            title: 'Fake Inspection Created',
                            message: `Successfully created fake inspection with ID: ${data.inspection_data.inspection_id}`
                          }
                        });
                        window.dispatchEvent(successEvent);
                      }
                    } catch (err) {
                      console.error('Failed to trigger fake inspection:', err);
                      
                      // Show error notification
                      const errorEvent = new CustomEvent('notificationRequest', {
                        detail: {
                          type: 'error',
                          title: 'Fake Inspection Error',
                          message: `Failed to create fake inspection: ${err instanceof Error ? err.message : 'Unknown error'}`
                        }
                      });
                      window.dispatchEvent(errorEvent);
                    } finally {
                      // Reset analyzing state
                      setAnalyzing(false);
                      setAnalysisMethod('single');
                    }
                  }}
                  className={`${analyzing ? 'bg-purple-400' : 'bg-purple-500 hover:bg-purple-600'} text-white px-4 py-2 rounded text-sm transition-colors mb-2 relative`}
                  disabled={analyzing}
                >
                  {analyzing && analysisMethod === 'fake' ? (
                    <>
                      <span className="inline-block mr-2">
                        <svg className="animate-spin h-4 w-4 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      </span>
                      Creating Fake Inspection...
                    </>
                  ) : 'Trigger Fake Inspection'}
                </button>

                {/* Image Folder Simulation */}
                <div className="border-t border-gray-200 pt-2 mt-2">
                  <span className="text-sm font-semibold text-gray-600 mb-2 block">BaslerCamera Analysis:</span>
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => {
                        // Trigger folder selection
                        fileInputRef.current?.click();
                      }}
                      className={`${analyzing ? 'bg-green-400 cursor-not-allowed' : 'bg-green-500 hover:bg-green-600'} text-white px-4 py-2 rounded text-xs transition-colors`}
                      disabled={analyzing}
                    >
                      {analyzing ? 'Processing in progress...' : 'Select Image Folder'}
                    </button>
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFolderSelect}
                      style={{ display: 'none' }}
                      // Properly handle directory selection attributes in React TypeScript
                      // @ts-ignore - webkitdirectory and directory are valid attributes but not in TypeScript definitions
                      webkitdirectory=""
                      // @ts-ignore - directory attribute is valid but not in TypeScript definitions
                      directory=""
                      multiple={true}
                    />
                    {selectedFolder && (
                      <div className="text-xs text-gray-700 mt-1">
                        <div>Selected folder: <span className="font-mono">{selectedFolder}</span></div>
                        <div>Images found: {imageFiles.length}</div>
                      </div>
                    )}
                    {imageFiles.length > 0 && (
                      <div className="flex flex-col gap-2">
                        <button
                          onClick={() => analyzeWithFullWorkflow()}
                          className={`${analyzing ? 'bg-purple-400' : 'bg-purple-500 hover:bg-purple-600'} text-white px-4 py-2 rounded text-xs transition-colors relative`}
                          disabled={analyzing}
                        >
                          {analyzing && analysisMethod === 'workflow' ? (
                            <>
                              <span className="inline-block mr-2">
                                <svg className="animate-spin h-4 w-4 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                              </span>
                              Processing Workflow...
                            </>
                          ) : 'Test Full Workflow'}
                        </button>
                        <button
                          onClick={() => testPresentationProcessor()}
                          className={`${analyzing ? 'bg-indigo-400' : 'bg-indigo-500 hover:bg-indigo-600'} text-white px-4 py-2 rounded text-xs transition-colors relative`}
                          disabled={analyzing}
                        >
                          {analyzing && analysisMethod === 'presentation' ? (
                            <>
                              <span className="inline-block mr-2">
                                <svg className="animate-spin h-4 w-4 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                              </span>
                              Processing Presentation...
                            </>
                          ) : 'Test Presentation Processor'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Image URL Testing */}
            {presentationImages.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-gray-700 mb-1">画像URLテスト</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span>表示中の画像:</span>
                    <div>
                      {presentationImages.map((img, index) => (
                        <span key={img.id || index} className="mr-2">
                          <button
                            className="text-blue-500 hover:text-blue-700 mr-1"
                            onClick={() => onImageTest(img.image_path)}
                          >
                            {img.group_name}
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-xs break-all">
                    <span>表示中の画像:</span>
                    <span className="font-mono block mt-1 bg-gray-50 p-1 rounded border">{
                      testImageUrl ? 
                        // Format the display of the URL based on its type
                        testImageUrl.startsWith('data:image/') ? 
                          'Base64 encoded image' : 
                          testImageUrl.includes('?path=') ? 
                            decodeURIComponent(testImageUrl.split('?path=')[1] || '') :
                            testImageUrl
                        : 
                        presentationImages[0]?.image_path || 'なし'
                    }</span>
                  </div>
                </div>

                {showTestImage && testImageUrl && (
                  <div className="mt-2 border border-gray-300 p-2 rounded">
                    <div className="text-xs mb-1">テスト画像:</div>
                    <div className="relative">
                      <img
                        src={testImageUrl}
                        alt="Test"
                        className="max-w-full h-auto"
                        onError={(e) => {
                          console.error("Test image failed to load:", testImageUrl);
                          
                          // Try to determine the reason for the failure
                          let errorReason = "Unknown error";
                          
                          if (testImageUrl.includes('localhost')) {
                            errorReason = "Using hardcoded localhost URL which may not work in all environments";
                          } else if (!testImageUrl.startsWith('http') && !testImageUrl.startsWith('data:')) {
                            errorReason = "Invalid URL format";
                          } else if (testImageUrl.includes('/api/file?path=')) {
                            errorReason = "File path may not exist on server";
                          }
                          
                          // Log detailed error information
                          console.error("Image load error details:", {
                            url: testImageUrl,
                            reason: errorReason,
                            timestamp: new Date().toISOString()
                          });
                          
                          // Update UI to show error with more details
                          e.currentTarget.style.display = 'none';
                          
                          // Clear any existing error messages first
                          const existingErrors = e.currentTarget.parentElement?.querySelectorAll('.image-error-message');
                          existingErrors?.forEach(el => el.remove());
                          
                          e.currentTarget.parentElement?.classList.add('bg-yellow-100', 'border-2', 'border-red-400', 'rounded', 'p-4', 'flex', 'flex-col', 'items-center', 'justify-center');
                          
                          // Create error container
                          const errorContainer = document.createElement('div');
                          errorContainer.className = 'image-error-message flex flex-col items-center';
                          
                          // Add error icon
                          const errorIcon = document.createElement('div');
                          errorIcon.className = 'text-red-500 text-2xl mb-2';
                          errorIcon.innerHTML = '⚠️';
                          errorContainer.appendChild(errorIcon);
                          
                          // Add error message
                          const errorMessage = document.createElement('div');
                          errorMessage.className = 'text-red-600 text-sm font-bold';
                          errorMessage.innerText = '画像の読み込みに失敗しました';
                          errorContainer.appendChild(errorMessage);
                          
                          // Add error details
                          const errorDetails = document.createElement('div');
                          errorDetails.className = 'text-gray-600 text-xs mt-1 text-center';
                          errorDetails.innerText = errorReason;
                          errorContainer.appendChild(errorDetails);
                          
                          // Add retry button
                          const retryButton = document.createElement('button');
                          retryButton.className = 'mt-2 bg-blue-500 hover:bg-blue-600 text-white text-xs px-3 py-1 rounded';
                          retryButton.innerText = '再試行';
                          retryButton.onclick = () => {
                            // Remove error container
                            errorContainer.remove();
                            // Reset parent element styles
                            e.currentTarget.parentElement?.classList.remove('bg-yellow-100', 'border-2', 'border-red-400', 'rounded', 'p-4', 'flex', 'flex-col', 'items-center', 'justify-center');
                            // Show image again
                            e.currentTarget.style.display = '';
                            // Force reload by updating src
                            e.currentTarget.src = testImageUrl + '?t=' + Date.now();
                          };
                          errorContainer.appendChild(retryButton);
                          
                          e.currentTarget.parentElement?.appendChild(errorContainer);
                        }}
                        onLoad={(e) => {
                          console.log("Image loaded successfully:", testImageUrl);
                          // Reset any error styling if the image loads successfully
                          e.currentTarget.parentElement?.classList.remove('bg-yellow-100', 'border-2', 'border-red-400', 'rounded', 'p-4', 'flex', 'flex-col', 'items-center', 'justify-center');
                          // Remove any error messages
                          const errorMessages = e.currentTarget.parentElement?.querySelectorAll('.image-error-message');
                          errorMessages?.forEach(el => el.remove());
                        }}
                      />
                      <button
                        className="absolute top-0 right-0 bg-red-500 text-white p-1 text-xs rounded-full w-5 h-5 flex items-center justify-center"
                        onClick={() => setShowTestImage(false)}
                      >
                        ×
                      </button>
                    </div>
                    <div className="text-xs mt-1 break-all">
                      <span>URL: </span>
                      <a href={testImageUrl} target="_blank" rel="noopener noreferrer" className="text-blue-500 font-mono">
                        {testImageUrl}
                      </a>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DebugPanel;