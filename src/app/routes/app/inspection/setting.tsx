import { useState, useEffect } from 'react';
import { useNotifications } from '@/components/ui/notifications';
import useNavigate from '@/hooks/use-navigate';
import { useLocation } from 'react-router-dom';
import StandardHeader from '@/components/ui/StandardHeader';

// Types for settings data - simplified to match sample
interface SettingsData {
    ai_threshold: number;
    horizontal_mm_per_pixel: number;
    vertical_mm_per_pixel: number;
    // Keep other fields for API compatibility but don't show in UI
    camera_exposure?: number;
    lighting_intensity?: number;
    length_threshold?: number;
}

// Utility validators for controlling user input
const isValidIntegerString = (value: string): boolean => {
    // Allow empty string for editing, otherwise only digits
    return value === '' || /^\d+$/.test(value);
};

const isValidFloatString = (value: string): boolean => {
    // Allow empty string while editing, then digits with optional single dot
    // Examples allowed: "1", "1.", "1.0", ".5", "0.25"
    return (
        value === '' ||
        /^\d*\.?\d*$/.test(value)
    );
};

// Add interface for raw input values
interface RawInputValues {
    ai_threshold: string;
    horizontal_mm_per_pixel: string;
    vertical_mm_per_pixel: string;
}

interface ValidationErrors {
    ai_threshold?: string;
    horizontal_mm_per_pixel?: string;
    vertical_mm_per_pixel?: string;
}

const SettingScreen = () => {
    const { navigate } = useNavigate();
    const location = useLocation();
    const { addNotification } = useNotifications();
    
    // Form state - simplified to match sample
    const [settings, setSettings] = useState<SettingsData>({
        ai_threshold: 50,
        horizontal_mm_per_pixel: 0.245833,
        vertical_mm_per_pixel: 0.288889
    });
    
    // Add state for raw input values to allow free typing
    const [rawInputs, setRawInputs] = useState<RawInputValues>({
        ai_threshold: '',
        horizontal_mm_per_pixel: '',
        vertical_mm_per_pixel: ''
    });
    
    const [originalSettings, setOriginalSettings] = useState<SettingsData | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [errors, setErrors] = useState<ValidationErrors>({});
    const [isDirty, setIsDirty] = useState(false);
    
    // Load current settings on component mount
    useEffect(() => {
        loadCurrentSettings();
    }, []);
    
    // Track if form is dirty - only check visible fields
    useEffect(() => {
        if (originalSettings) {
            const hasChanges = 
                rawInputs.ai_threshold !== originalSettings.ai_threshold.toString() ||
                rawInputs.horizontal_mm_per_pixel !== originalSettings.horizontal_mm_per_pixel.toString() ||
                rawInputs.vertical_mm_per_pixel !== originalSettings.vertical_mm_per_pixel.toString();
            setIsDirty(hasChanges);
        }
    }, [rawInputs, originalSettings]);
    
    const loadCurrentSettings = async () => {
        setLoading(true);
        try {
            const response = await fetch('/api/settings/current');
            if (response.ok) {
                const data = await response.json();
                const newSettings = {
                    ai_threshold: data.ai_threshold,
                    horizontal_mm_per_pixel: data.horizontal_mm_per_pixel,
                    vertical_mm_per_pixel: data.vertical_mm_per_pixel,
                    // Keep other fields for API compatibility
                    camera_exposure: data.camera_exposure,
                    lighting_intensity: data.lighting_intensity,
                    length_threshold: data.length_threshold
                };
                setSettings(newSettings);
                
                // Also update raw inputs to match
                setRawInputs({
                    ai_threshold: data.ai_threshold.toString(),
                    horizontal_mm_per_pixel: data.horizontal_mm_per_pixel.toString(),
                    vertical_mm_per_pixel: data.vertical_mm_per_pixel.toString()
                });
                
                setOriginalSettings(data);
                console.log('Loaded settings:', data);
            } else {
                throw new Error('Failed to load settings');
            }
        } catch (error) {
            console.error('Error loading settings:', error);
            addNotification({
                type: 'error',
                title: '設定読み込みエラー',
                message: '設定の読み込みに失敗しました'
            });
        } finally {
            setLoading(false);
        }
    };
    
    const validateSettings = (): boolean => {
        const newErrors: ValidationErrors = {};
        
        // Parse raw inputs for validation
        const aiThreshold = parseInt(rawInputs.ai_threshold);
        const horizontalResolution = parseFloat(rawInputs.horizontal_mm_per_pixel);
        const verticalResolution = parseFloat(rawInputs.vertical_mm_per_pixel);
        
        // AI threshold validation
        if (isNaN(aiThreshold) || aiThreshold < 10 || aiThreshold > 100) {
            newErrors.ai_threshold = 'AI閾値は10〜100の範囲で入力してください';
        }
        
        // Resolution validation
        if (isNaN(horizontalResolution) || horizontalResolution <= 0) {
            newErrors.horizontal_mm_per_pixel = '分解能_横は正の値で入力してください';
        }
        
        if (isNaN(verticalResolution) || verticalResolution <= 0) {
            newErrors.vertical_mm_per_pixel = '分解能_縦は正の値で入力してください';
        }
        
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };
    
    const handleInputChange = (field: keyof RawInputValues, value: string) => {
        // Block invalid characters at the typing stage
        const isIntegerField = field === 'ai_threshold';
        const isValid = isIntegerField ? isValidIntegerString(value) : isValidFloatString(value);
        if (!isValid) {
            return; // ignore invalid keystrokes/pastes
        }

        // Update raw value (allows empty string while editing)
        setRawInputs(prev => ({
            ...prev,
            [field]: value
        }));

        // When the raw value can be parsed, mirror it into numeric state
        const numericValue = isIntegerField ? parseInt(value) : parseFloat(value);
        if (!isNaN(numericValue)) {
            setSettings(prev => ({
                ...prev,
                [field]: numericValue
            }));
        }
    };
    
    const handleSave = async () => {
        if (!validateSettings()) {
            addNotification({
                type: 'error',
                title: '入力エラー',
                message: '入力内容を確認してください'
            });
            return;
        }
        
        // Parse the final values from raw inputs
        const finalSettings = {
            ai_threshold: parseInt(rawInputs.ai_threshold),
            horizontal_mm_per_pixel: parseFloat(rawInputs.horizontal_mm_per_pixel),
            vertical_mm_per_pixel: parseFloat(rawInputs.vertical_mm_per_pixel)
        };
        
        setSaving(true);
        try {
            const response = await fetch('/api/settings', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    // Send all fields for API compatibility, preserving unchanged values
                    camera_exposure: settings.camera_exposure || originalSettings?.camera_exposure || 1000,
                    lighting_intensity: settings.lighting_intensity || originalSettings?.lighting_intensity || 50,
                    ai_threshold: finalSettings.ai_threshold,
                    length_threshold: settings.length_threshold || originalSettings?.length_threshold || 10.0,
                    horizontal_mm_per_pixel: finalSettings.horizontal_mm_per_pixel,
                    vertical_mm_per_pixel: finalSettings.vertical_mm_per_pixel
                })
            });
            
            if (response.ok) {
                const updatedSettings = await response.json();
                setSettings(updatedSettings);
                setOriginalSettings(updatedSettings);
                setIsDirty(false);
                
                // Update raw inputs to match the saved values
                setRawInputs({
                    ai_threshold: updatedSettings.ai_threshold.toString(),
                    horizontal_mm_per_pixel: updatedSettings.horizontal_mm_per_pixel.toString(),
                    vertical_mm_per_pixel: updatedSettings.vertical_mm_per_pixel.toString()
                });
                
                addNotification({
                    type: 'success',
                    title: '保存完了',
                    message: '設定が正常に保存されました'
                });
                
                console.log('Settings saved successfully:', updatedSettings);
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to save settings');
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            addNotification({
                type: 'error',
                title: '保存エラー',
                message: '設定の保存に失敗しました'
            });
        } finally {
            setSaving(false);
        }
    };
    
    const handleCancel = () => {
        if (isDirty) {
            if (window.confirm('未保存の変更があります。破棄してもよろしいですか？')) {
                if (originalSettings) {
                    setSettings({
                        ai_threshold: originalSettings.ai_threshold,
                        horizontal_mm_per_pixel: originalSettings.horizontal_mm_per_pixel,
                        vertical_mm_per_pixel: originalSettings.vertical_mm_per_pixel,
                        // Keep other fields
                        camera_exposure: originalSettings.camera_exposure,
                        lighting_intensity: originalSettings.lighting_intensity,
                        length_threshold: originalSettings.length_threshold
                    });
                    
                    // Reset raw inputs to match
                    setRawInputs({
                        ai_threshold: originalSettings.ai_threshold.toString(),
                        horizontal_mm_per_pixel: originalSettings.horizontal_mm_per_pixel.toString(),
                        vertical_mm_per_pixel: originalSettings.vertical_mm_per_pixel.toString()
                    });
                }
                setIsDirty(false);
                setErrors({});
            } else {
                return; // Don't navigate if user cancels
            }
        }
        
        // Navigate back
        if (location.pathname === '/') {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            navigate('/');
        }
    };
    
    const handleReset = async () => {
        if (window.confirm('設定をデフォルト値にリセットしますか？')) {
            setSaving(true);
            try {
                const response = await fetch('/api/settings/reset', {
                    method: 'POST'
                });
                
                if (response.ok) {
                    const defaultSettings = await response.json();
                    setSettings({
                        ai_threshold: defaultSettings.ai_threshold,
                        horizontal_mm_per_pixel: defaultSettings.horizontal_mm_per_pixel,
                        vertical_mm_per_pixel: defaultSettings.vertical_mm_per_pixel,
                        // Keep other fields
                        camera_exposure: defaultSettings.camera_exposure,
                        lighting_intensity: defaultSettings.lighting_intensity,
                        length_threshold: defaultSettings.length_threshold
                    });
                    
                    // Update raw inputs to match
                    setRawInputs({
                        ai_threshold: defaultSettings.ai_threshold.toString(),
                        horizontal_mm_per_pixel: defaultSettings.horizontal_mm_per_pixel.toString(),
                        vertical_mm_per_pixel: defaultSettings.vertical_mm_per_pixel.toString()
                    });
                    
                    setOriginalSettings(defaultSettings);
                    setIsDirty(false);
                    setErrors({});
                    
                    addNotification({
                        type: 'success',
                        title: 'リセット完了',
                        message: '設定をデフォルト値にリセットしました'
                    });
                } else {
                    throw new Error('Failed to reset settings');
                }
            } catch (error) {
                console.error('Error resetting settings:', error);
                addNotification({
                    type: 'error',
                    title: 'リセットエラー',
                    message: '設定のリセットに失敗しました'
                });
            } finally {
                setSaving(false);
            }
        }
    };
    
    if (loading) {
        return (
            <div className="min-h-screen w-full bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-800 mx-auto mb-4"></div>
                    <div className="text-lg text-gray-600">設定を読み込み中...</div>
                </div>
            </div>
        );
    }
    
    return (
        <div className="min-h-screen w-full bg-gray-50">
            {/* Header using StandardHeader component */}
            <StandardHeader
                title="木材検査システム　設定"
                variant="primary"
                showLogo={true}
            >
                {/* TOP Button in header */}
                <button
                    onClick={() => navigate('/')}
                    className="bg-[#2c5aa0] hover:bg-[#1e3f73] text-white px-6 py-2 rounded-lg font-bold transition-colors"
                >
                    TOP
                </button>
            </StandardHeader>

            {/* Main Content Area */}
            <div className="flex-1 flex items-center justify-center p-8">
                <div className="bg-white rounded-lg shadow-lg p-12 w-full max-w-2xl">
                    <div className="space-y-12">
                        {/* AI閾値 Section */}
                        <div className="text-center">
                            <div className="flex items-center justify-center gap-6 mb-6">
                                <h2 className="text-2xl font-bold text-[#2c5aa0]">AI閾値</h2>
                                <input 
                                    type="text" 
                                    inputMode="numeric"
                                    pattern="\\d+"
                                    value={rawInputs.ai_threshold}
                                    onChange={(e) => handleInputChange('ai_threshold', e.target.value)}
                                    className={`border-2 px-6 py-3 rounded-lg text-xl w-80 text-center ${
                                        errors.ai_threshold ? 'border-red-500' : 'border-[#2c5aa0]'
                                    }`}
                                    placeholder=""
                                />
                            </div>
                            {errors.ai_threshold && (
                                <div className="text-red-500 text-sm mt-2">{errors.ai_threshold}</div>
                            )}
                        </div>

                        {/* 分解能 Section */}
                        <div className="text-center">
                            <h2 className="text-2xl font-bold text-[#2c5aa0] mb-6">分解能</h2>
                            <div className="flex items-center justify-center gap-8">
                                {/* 分解能_横 (Horizontal mm per pixel) */}
                                <div className="flex items-center gap-3">
                                    <span className="text-xl font-bold text-[#2c5aa0]">分解能_横</span>
                                    <input 
                                        type="text" 
                                        inputMode="decimal"
                                        pattern="\\d*\\.?\\d*"
                                        value={rawInputs.horizontal_mm_per_pixel}
                                        onChange={(e) => handleInputChange('horizontal_mm_per_pixel', e.target.value)}
                                        className={`border-2 px-4 py-3 rounded-lg text-lg w-48 text-center ${
                                            errors.horizontal_mm_per_pixel ? 'border-red-500' : 'border-[#2c5aa0]'
                                        }`}
                                        placeholder=""
                                    />
                                </div>
                                
                                {/* 分解能_縦 (Vertical mm per pixel) */}
                                <div className="flex items-center gap-3">
                                    <span className="text-xl font-bold text-[#2c5aa0]">分解能_縦</span>
                                    <input 
                                        type="text" 
                                        inputMode="decimal"
                                        pattern="\\d*\\.?\\d*"
                                        value={rawInputs.vertical_mm_per_pixel}
                                        onChange={(e) => handleInputChange('vertical_mm_per_pixel', e.target.value)}
                                        className={`border-2 px-4 py-3 rounded-lg text-xl w-48 text-center ${
                                            errors.vertical_mm_per_pixel ? 'border-red-500' : 'border-[#2c5aa0]'
                                        }`}
                                        placeholder=""
                                    />
                                </div>
                            </div>
                            {(errors.horizontal_mm_per_pixel || errors.vertical_mm_per_pixel) && (
                                <div className="text-red-500 text-sm mt-2">
                                    {errors.horizontal_mm_per_pixel || errors.vertical_mm_per_pixel}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* 保存 Button */}
                    <div className="text-center mt-16">
                        <button 
                            onClick={handleSave}
                            disabled={saving || !isDirty}
                            className={`px-12 py-4 rounded-lg text-xl font-bold transition-colors ${
                                saving || !isDirty 
                                ? 'bg-gray-400 text-gray-600 cursor-not-allowed'
                                : 'bg-[#2c5aa0] text-white hover:bg-[#1e3f73] shadow-lg'
                            }`}
                        >
                            {saving ? '保存中...' : '保存'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SettingScreen;
