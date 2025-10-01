import React, { useEffect, useState, useMemo } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { registerLocale, setDefaultLocale } from 'react-datepicker';
import { ja } from 'date-fns/locale';
import useNavigate from '@/hooks/use-navigate';
import { fetchInspectionDetailsByDate, fetchInspectionDetailsAll } from '@/features/inspections/api/inspections-history';
import type { Inspection, InspectionResult } from '@/types/api';
import dayjs from 'dayjs'; // format date
import InspectionList from '@/components/modal/InspectionHistoryDetailsList';
import StandardHeader from '@/components/ui/StandardHeader';
import Pagination from '@/components/ui/Pagination';

// Register Japanese locale for DatePicker
registerLocale('ja', ja);
setDefaultLocale('ja');

const InspectionHistoryScreen = () => {
    const [showCalendar, setShowCalendar] = useState(false);
    const [selectedDate, setSelectedDate] = useState<Date | null>(null);
    const [inspections, setInspections] = useState<Inspection[]>([]);
    const [loading, setLoading] = useState(false);
    const [hasSelectedDate, setHasSelectedDate] = useState(false);
    const { navigate } = useNavigate();

    // Pagination state
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(10);
    
    // Cache for inspection results to avoid re-fetching on page changes
    const [inspectionResultsCache, setInspectionResultsCache] = useState<Record<number, any>>({});
    const [defectStatusCache, setDefectStatusCache] = useState<Map<number, any>>(new Map());

    // Sort inspections by date (newest to oldest)
    const sortedInspections = useMemo(() => {
        return [...inspections].sort((a, b) => {
            const dateA = new Date(a.inspection_dt);
            const dateB = new Date(b.inspection_dt);
            return dateB.getTime() - dateA.getTime(); // Newest first
        });
    }, [inspections]);

    // Pagination calculations
    const totalPages = Math.ceil(sortedInspections.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const paginatedInspections = sortedInspections.slice(startIndex, endIndex);

    // Reset to first page when inspections change
    useEffect(() => {
        setCurrentPage(1);
    }, [inspections]);

    // Handle page change
    const handlePageChange = (page: number) => {
        setCurrentPage(page);
    };

    // Handle items per page change
    const handleItemsPerPageChange = (newItemsPerPage: number) => {
        setItemsPerPage(newItemsPerPage);
        setCurrentPage(1); // Reset to first page when changing page size
    };

    // Handle inspection changes (for bulk operations)
    const handleInspectionsChange = async (updatedInspections: Inspection[]) => {
        // If empty array is passed, it means items were deleted - refetch data
        if (updatedInspections.length === 0 && selectedDate) {
            const formattedDate = dayjs(selectedDate).format('YYYY-MM-DD');
            setLoading(true);
            try {
                const res = await fetchInspectionDetailsByDate({
                    date_selected: formattedDate,
                });
                if (res.result) {
                    setInspections(res.data);
                    // Clear cache when data changes
                    setInspectionResultsCache({});
                    setDefectStatusCache(new Map());
                } else {
                    alert(res.message);
                    setInspections([]);
                }
            } catch (error) {
                console.error(error);
                alert('通信エラーが発生しました');
            } finally {
                setLoading(false);
            }
        } else {
            setInspections(updatedInspections);
        }
    };

    // Handle cache updates from InspectionList
    const handleCacheUpdate = (results: Record<number, any>, status: Map<number, any>) => {
        setInspectionResultsCache(results);
        setDefectStatusCache(status);
    };

    // handleDateChange
    const handleDateChange = async (date: Date | null) => {
        setSelectedDate(date);
        setShowCalendar(false);

        if (!date) {
            setHasSelectedDate(false);
            setInspections([]);
            // Clear cache when no date is selected
            setInspectionResultsCache({});
            setDefectStatusCache(new Map());
            return;
        }

        setHasSelectedDate(true);
        // Clear cache when date changes
        setInspectionResultsCache({});
        setDefectStatusCache(new Map());
        
        const formattedDate = dayjs(date).format('YYYY-MM-DD');
        setLoading(true);
        try {
            const res = await fetchInspectionDetailsByDate({
                date_selected: formattedDate,
            });
            if (res.result) {
                setInspections(res.data);
            } else {
                alert(res.message);
                setInspections([]);
            }
        } catch (error) {
            console.error(error);
            alert('通信エラーが発生しました');
        } finally {
            setLoading(false);
        }
    };

  return (
    <div className="h-screen bg-white flex flex-col">
        {/* Header */}
        <StandardHeader
            title="木材検査システム 検査履歴一覧画面​"
            variant="primary"
            showLogo={true}
        />
        <div id="wrapper" className="flex flex-row h-full">
            <div className="w-1/2 h-full justify-center p-6 mx-auto">
                <div className="flex justify-end mb-4">
                    <button
                    onClick={() => navigate('/')}
                    className="bg-[#155f83] text-white px-4 py-2 rounded shadow"
                    >
                    TOP
                    </button>
                </div>

                <div className="mb-4">
                    <StandardHeader
                        title="検査履歴一覧"
                        variant="page"
                        showLogo={false}
                    />
                </div>

                <div className="relative">
                    {/* Calendar Popup */}
                    {showCalendar && (
                    <div className="absolute right-[-280px] top-[-30px] z-50 bg-white p-4 rounded shadow border border-gray-300">
                        <DatePicker
                        selected={selectedDate}
                        onChange={handleDateChange}
                        inline
                        locale="ja"
                        />
                    </div>
                    )}
                </div>
                {/* 日付選択ボタン */}
                <div className="flex justify-end mb-10">
                    <button
                        className="bg-[#155f83] text-white px-4 py-2 rounded shadow"
                        onClick={() => setShowCalendar(!showCalendar)}
                    >
                    表示する日付選択
                    </button>
                </div>

                {/* Show selected date if available */}
                {selectedDate && (
                    <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded">
                        <p className="text-blue-800 font-medium">
                            選択された日付: {dayjs(selectedDate).format('YYYY年MM月DD日')}
                        </p>
                    </div>
                )}

                {/* Show message when no date is selected */}
                {!hasSelectedDate && (
                    <div className="text-center py-8">
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                            <p className="text-yellow-800 text-lg font-medium mb-2">
                                日付を選択してください
                            </p>
                            <p className="text-yellow-700">
                                検査履歴を表示するには、上記の「表示する日付選択」ボタンをクリックして日付を選択してください。
                            </p>
                        </div>
                    </div>
                )}

                {/* list result get component */}
                {hasSelectedDate && (
                    loading ? (
                        <div className="flex items-center justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
                            <span className="text-gray-600">データを読み込み中...</span>
                        </div>
                    ) : sortedInspections.length > 0 ? (
                        <div className="flex flex-col">
                            <InspectionList 
                                inspections={paginatedInspections} 
                                onInspectionsChange={handleInspectionsChange}
                                totalCount={sortedInspections.length}
                                inspectionResultsCache={inspectionResultsCache}
                                defectStatusCache={defectStatusCache}
                                onCacheUpdate={handleCacheUpdate}
                            />
                            {!loading && (
                                <Pagination
                                    currentPage={currentPage}
                                    totalPages={totalPages}
                                    totalItems={sortedInspections.length}
                                    itemsPerPage={itemsPerPage}
                                    onPageChange={handlePageChange}
                                    onItemsPerPageChange={handleItemsPerPageChange}
                                    showItemsPerPageSelector={true}
                                    itemsPerPageOptions={[5, 10, 20, 50]}
                                />
                            )}
                        </div>
                    ) : (
                        <div className="text-center py-8">
                            <p className="text-gray-500 text-lg">
                                選択された日付（{dayjs(selectedDate).format('YYYY年MM月DD日')}）に検査データがありません。
                            </p>
                        </div>
                    )
                )}
            </div>
        </div>
    </div>
  );
};

export default InspectionHistoryScreen;
