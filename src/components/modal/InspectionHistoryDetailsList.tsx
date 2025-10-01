import React, { useState, useEffect, useCallback } from 'react';
import { Inspection } from '@/types/api';
import { fetchInspectionDetailsById, fetchInspectionResultById } from '@/features/inspections/api/inspections-details';
import { deleteInspectionsByIds } from '@/features/inspections/api/inspections-history';
import InspectionDetailsModal from '@/components/modal/InspectionDetailsModal';
import BulkOperationControls from '@/components/ui/BulkOperationControls';
import ConfirmDialog from '@/components/ui/confirm-dialog';
import { getDefectDisplayInfo, DefectStatusInfo } from '@/utils/defectStatus';

type InspectionListProps = {
    inspections: Inspection[];
    onInspectionsChange?: (inspections: Inspection[]) => void;
    totalCount?: number;
    inspectionResultsCache?: Record<number, any>;
    defectStatusCache?: Map<number, any>;
    onCacheUpdate?: (results: Record<number, any>, status: Map<number, any>) => void;
};

const InspectionList: React.FC<InspectionListProps> = ({ 
    inspections, 
    onInspectionsChange, 
    totalCount, 
    inspectionResultsCache = {}, 
    defectStatusCache = new Map(),
    onCacheUpdate 
}) => {

    // モーダル表示の状態管理
    const [showDetail, setShowDetail] = useState(false);
    // 選択された検査データの保存
    const [selectedInspection, setSelectedInspection] = useState<Inspection | null>(null);
    // 検査結果（inspection_idごとに真のキーの配列）を保存するステート
    const [inspectionResults, setInspectionResults] = useState<Record<number, string[]>>(inspectionResultsCache);

    // Bulk operations state management
    const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    // Defect status processing state
    const [defectStatusMap, setDefectStatusMap] = useState<Map<number, DefectStatusInfo>>(defectStatusCache);

    // 詳細表示ボタンを押したときに呼ばれる関数
    // 指定IDの検査詳細をAPIから取得し、成功したらモーダルを表示する
    const handleShowDetail = async (id: number) => {
        const result = await fetchInspectionDetailsById({ id });
        if (result.result && result.data) {
            setSelectedInspection(result.data);
            setShowDetail(true);
        } else {
            alert(result.message);
        }
    };

    // Selection change handlers
    const handleItemSelection = useCallback((id: number, selected: boolean) => {
        setSelectedItems(prev => {
            const newSet = new Set(prev);
            if (selected) {
                newSet.add(id);
            } else {
                newSet.delete(id);
            }
            return newSet;
        });
        // Clear messages when selection changes
        if (deleteError) {
            setDeleteError(null);
        }
        if (successMessage) {
            setSuccessMessage(null);
        }
    }, [deleteError, successMessage]);

    const handleSelectAll = useCallback(() => {
        if (isDeleting || isLoading) return;

        // Select all items on the current page
        const currentPageIds = new Set(inspections.map(item => item.inspection_id));
        setSelectedItems(prev => {
            const newSet = new Set(prev);
            currentPageIds.forEach(id => newSet.add(id));
            return newSet;
        });
        // Clear messages when selection changes
        if (deleteError) {
            setDeleteError(null);
        }
        if (successMessage) {
            setSuccessMessage(null);
        }
    }, [inspections, deleteError, successMessage, isDeleting, isLoading]);

    const handleDeselectAll = useCallback(() => {
        if (isDeleting || isLoading) return;

        setSelectedItems(new Set());
        // Clear messages when selection changes
        if (deleteError) {
            setDeleteError(null);
        }
        if (successMessage) {
            setSuccessMessage(null);
        }
    }, [deleteError, successMessage, isDeleting, isLoading]);

    // Bulk delete functionality with validation
    const handleBulkDelete = useCallback(() => {
        // Validation: check for selected items before showing dialog
        if (selectedItems.size === 0) {
            setDeleteError('削除する項目を選択してください');
            return;
        }

        // Clear any existing error and show confirmation dialog
        setDeleteError(null);
        setShowDeleteConfirm(true);
    }, [selectedItems]);

    // Handle delete confirmation
    const handleDeleteConfirm = useCallback(async () => {
        setShowDeleteConfirm(false);
        setIsDeleting(true);
        setDeleteError(null);
        setSuccessMessage(null);

        try {
            const result = await deleteInspectionsByIds({
                inspection_ids: Array.from(selectedItems)
            });

            if (result.result && result.data) {
                // Success: clear selection and notify parent
                setSelectedItems(new Set());

                // Notify parent component to refresh the full inspection list
                if (onInspectionsChange) {
                    // The parent will handle filtering out deleted items
                    // We just need to trigger a refresh
                    onInspectionsChange([]);
                }

                // Show success message with better user feedback
                setSuccessMessage(`${result.data.deleted_count}件の検査記録を削除しました。`);

                // Auto-clear success message after 5 seconds
                setTimeout(() => {
                    setSuccessMessage(null);
                }, 5000);
            } else {
                // Handle partial deletion or server errors
                if (result.data && result.data.deleted_count > 0) {
                    // Partial success - some items were deleted
                    setSelectedItems(new Set());

                    if (onInspectionsChange) {
                        onInspectionsChange([]);
                    }

                    setDeleteError(`${result.data.deleted_count}件を削除しましたが、一部の削除に失敗しました: ${result.message}`);
                } else {
                    // Complete failure
                    setDeleteError(result.message || '削除に失敗しました。');
                }
            }
        } catch (error) {
            console.error('Delete error:', error);
            setDeleteError('削除中にエラーが発生しました。ネットワーク接続を確認してください。');
        } finally {
            setIsDeleting(false);
        }
    }, [selectedItems, onInspectionsChange]);

    // Handle delete cancellation
    const handleDeleteCancel = useCallback(() => {
        setShowDeleteConfirm(false);
    }, []);

    // Process defect status for each inspection
    const processDefectStatus = useCallback(async (inspectionId: number, inspectionResult: any) => {
        try {
            // Use the inspection result data to determine defect status
            // This provides enhanced classification using existing defect logic
            const defectInfo = getDefectDisplayInfo(inspectionResult || {}, []);

            setDefectStatusMap(prev => {
                const newMap = new Map(prev);
                newMap.set(inspectionId, defectInfo);
                return newMap;
            });
        } catch (error) {
            console.error('Error processing defect status for inspection', inspectionId, ':', error);
            // Set default status on error to ensure consistent display
            setDefectStatusMap(prev => {
                const newMap = new Map(prev);
                newMap.set(inspectionId, {
                    classification: 'none',
                    displayText: '無欠点',
                    mainStatus: '無欠点',
                    subStatus: '',
                    hasMultipleTypes: false,
                    details: ['データ処理エラー']
                });
                return newMap;
            });
        }
    }, []);

    // 検査結果のラベルマッピング
    // APIから返されるキーを日本語のラベルに変換するための対応表
    const resultLabels: Record<string, string> = React.useMemo(() => ({
        discoloration: '変色',
        hole: '穴',
        knot: '節',
        dead_knot: '流れ節_死',
        tight_knot: '流れ節_生',
        live_knot: '生き節',
    }), []);

    // Update local state when cache props change
    useEffect(() => {
        setInspectionResults(inspectionResultsCache);
        setDefectStatusMap(defectStatusCache);
    }, [inspectionResultsCache, defectStatusCache]);

    // inspectionsが変更されたときにAPIを呼び、検査結果を取得する
    useEffect(() => {
        const fetchResults = async () => {
            if (inspections.length === 0) {
                // Clear all state when no inspections
                setInspectionResults({});
                setDefectStatusMap(new Map());
                setIsLoading(false);
                return;
            }

            // Check if we already have results for all inspections on this page
            const missingResults = inspections.filter(
                item => !inspectionResults[item.inspection_id] && !defectStatusMap.has(item.inspection_id)
            );

            // If we already have all results, don't show loading
            if (missingResults.length === 0) {
                setIsLoading(false);
                return;
            }

            setIsLoading(true);

            // inspection_idごとの検査結果を格納するオブジェクトを用意
            const resultMap: Record<number, string[]> = { ...inspectionResults };
            const newDefectStatusMap = new Map(defectStatusMap);

            try {
                // Only fetch results for inspections we don't have yet
                for (const item of missingResults) {
                    try {
                        const res = await fetchInspectionResultById({ id: item.inspection_id });

                        if (res.result && res.data) {
                            const trueKeys = Object.keys(resultLabels).filter(
                                (key) => res.data[key as keyof typeof res.data] === true
                            );
                            resultMap[item.inspection_id] = trueKeys;

                            // Process defect status for enhanced display using API data
                            const defectInfo = getDefectDisplayInfo(res.data || {}, []);
                            newDefectStatusMap.set(item.inspection_id, defectInfo);
                        } else {
                            console.warn(`Failed to fetch inspection result for ID ${item.inspection_id}:`, res.message);
                            resultMap[item.inspection_id] = [];
                            // Process defect status with empty data (will show 無欠点)
                            const emptyResult = {
                                inspection_id: item.inspection_id,
                                discoloration: false,
                                hole: false,
                                knot: false,
                                dead_knot: false,
                                live_knot: false,
                                tight_knot: false,
                                length: 0
                            };
                            const defectInfo = getDefectDisplayInfo(emptyResult, []);
                            newDefectStatusMap.set(item.inspection_id, defectInfo);
                        }
                    } catch (error) {
                        console.error(`Error fetching inspection result for ID ${item.inspection_id}:`, error);
                        resultMap[item.inspection_id] = [];
                        // Process defect status with empty data on error
                        const emptyResult = {
                            inspection_id: item.inspection_id,
                            discoloration: false,
                            hole: false,
                            knot: false,
                            dead_knot: false,
                            live_knot: false,
                            tight_knot: false,
                            length: 0
                        };
                        const defectInfo = getDefectDisplayInfo(emptyResult, []);
                        newDefectStatusMap.set(item.inspection_id, defectInfo);
                    }
                }

                // 取得した検査結果をステートにセットする
                setInspectionResults(resultMap);
                setDefectStatusMap(newDefectStatusMap);
                
                // Update parent cache
                if (onCacheUpdate) {
                    onCacheUpdate(resultMap, newDefectStatusMap);
                }
            } catch (error) {
                console.error('Error fetching inspection results:', error);
                setDeleteError('検査結果の読み込み中にエラーが発生しました。');
            } finally {
                setIsLoading(false);
            }
        };

        // Clear selection and messages when inspections change
        setSelectedItems(new Set<number>());
        setDeleteError(null);
        setSuccessMessage(null);

        fetchResults();
    }, [inspections, processDefectStatus, resultLabels, inspectionResults, defectStatusMap, onCacheUpdate]);

    return (
        <div>
            {/* Success message display */}
            {successMessage && (
                <div
                    className="mb-4 text-green-600 text-sm font-medium bg-green-50 border border-green-200 rounded p-2"
                    role="alert"
                    aria-live="polite"
                >
                    <span className="inline-block mr-2" aria-hidden="true">✅</span>
                    {successMessage}
                </div>
            )}

            {/* Bulk Operation Controls */}
            <BulkOperationControls
                selectedCount={selectedItems.size}
                totalCount={totalCount ?? inspections.length}
                onSelectAll={handleSelectAll}
                onDeselectAll={handleDeselectAll}
                onDelete={handleBulkDelete}
                deleteError={deleteError}
                isDeleting={isDeleting}
                isLoading={isLoading}
            />

            <div className="max-h-[400px] overflow-y-auto border rounded p-4 shadow">
                {/* Loading overlay */}
                {isLoading && (
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3" role="status" aria-label="読み込み中"></div>
                        <span className="text-gray-600">検査結果を読み込み中...</span>
                    </div>
                )}

                <div className={`space-y-4 ${isLoading ? 'opacity-50' : ''}`}>
                    {inspections.map((item) => {
                        const isSelected = selectedItems.has(item.inspection_id);
                        const defectStatus = defectStatusMap.get(item.inspection_id);

                        return (
                            <div
                                key={item.inspection_id}
                                className="flex items-center border-b pb-2"
                            >
                                {/* Checkbox for selection with enhanced feedback */}
                                <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => handleItemSelection(item.inspection_id, e.target.checked)}
                                    disabled={isDeleting || isLoading}
                                    className={`mr-3 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded transition-opacity duration-200 ${isDeleting || isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                                        } ${isSelected ? 'bg-blue-600 border-blue-600' : ''}`}
                                    aria-label={`検査記録 ${item.inspection_id} を選択`}
                                    aria-describedby={`inspection-${item.inspection_id}-details`}
                                />

                                <div className="flex-1 flex justify-between items-center">
                                    <div id={`inspection-${item.inspection_id}-details`}>
                                        <div>
                                            {new Date(item.inspection_dt).toLocaleString(undefined, {
                                                year: 'numeric',
                                                month: '2-digit',
                                                day: '2-digit',
                                                hour: '2-digit',
                                                minute: '2-digit',
                                                second: '2-digit',
                                            })}
                                            <span className="ml-5 mr-5">板No:{item.inspection_id}</span>

                                            {/* Enhanced defect status display - inline with text */}
                                            {defectStatus ? (
                                                <div className="inline-flex items-center gap-2 ml-2">
                                                    {/* Main status label */}
                                                    <span className={`inline-block px-3 py-1 rounded-md text-sm font-semibold border ${defectStatus.classification === 'none'
                                                        ? 'bg-green-50 text-green-900 border-green-300'
                                                        : defectStatus.classification === 'minor'
                                                            ? 'bg-yellow-50 text-yellow-900 border-yellow-300'
                                                            : defectStatus.classification === 'major'
                                                                ? 'bg-red-50 text-red-900 border-red-300'
                                                                : 'bg-purple-50 text-purple-900 border-purple-300'
                                                        }`} title={defectStatus.details.length > 0 ? defectStatus.details.join(', ') : undefined}>
                                                        <span className="font-bold">{defectStatus.mainStatus}</span>
                                                    </span>
                                                    
                                                    {/* Sub status label (if available) */}
                                                    {defectStatus.subStatus && (
                                                        <span className="inline-block px-3 py-1 rounded-md text-sm font-semibold border bg-purple-50 text-purple-900 border-purple-300">
                                                            {defectStatus.subStatus}
                                                        </span>
                                                    )}
                                                </div>
                                            ) : (
                                                <span className="inline-block px-2 py-1 rounded text-sm bg-gray-100 text-gray-600 border border-gray-300 ml-2">
                                                    {(inspectionResults[item.inspection_id] ?? []).length > 0
                                                        ? (inspectionResults[item.inspection_id] ?? [])
                                                            .map((key) => resultLabels[key])
                                                            .join(' , ')
                                                        : '処理中...'}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleShowDetail(item.inspection_id)}
                                        disabled={isDeleting || isLoading}
                                        className={`px-3 py-1 rounded text-lg font-bold transition-colors duration-200 ${isDeleting || isLoading
                                            ? 'bg-gray-400 text-gray-600 cursor-not-allowed'
                                            : 'bg-[#0f9ed5] text-white hover:bg-[#0d8bb8] focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
                                            }`}
                                        aria-label={`検査記録 ${item.inspection_id} の詳細を表示`}
                                    >
                                        {isLoading ? '読み込み中...' : '結果を表示'}
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>

                {showDetail && selectedInspection && (
                    <InspectionDetailsModal
                        inspection={selectedInspection}
                        onClose={() => setShowDetail(false)}
                    />
                )}
            </div>

            {/* Delete Confirmation Dialog */}
            <ConfirmDialog
                open={showDeleteConfirm}
                onClose={handleDeleteCancel}
                onConfirm={handleDeleteConfirm}
                title="検査記録の削除"
                content={`選択された${selectedItems.size}件の検査記録を削除しますか？この操作は取り消せません。`}
            />
        </div>
    );
};

export default InspectionList;
