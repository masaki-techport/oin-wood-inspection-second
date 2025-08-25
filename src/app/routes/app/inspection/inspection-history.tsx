import React, { useEffect, useState } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import useNavigate from '@/hooks/use-navigate';
import { fetchInspectionDetailsByDate, fetchInspectionDetailsAll } from '@/features/inspections/api/inspections-history';
import type { Inspection, InspectionResult } from '@/types/api';
import dayjs from 'dayjs'; // format date
import InspectionList from '@/components/modal/InspectionHistoryDetailsList';

const InspectionHistoryScreen = () => {
    const [showCalendar, setShowCalendar] = useState(false);
    const [selectedDate, setSelectedDate] = useState<Date | null>(null);
    const [inspections, setInspections] = useState<Inspection[]>([]);
    const [loading, setLoading] = useState(false);
    const { navigate } = useNavigate();

    // Load all
    useEffect(() => {
        const fetchAllInspections = async () => {
            setLoading(true);
            try {
                const res = await fetchInspectionDetailsAll(); // API get all
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

        fetchAllInspections();
    }, []);

    // handleDateChange
    const handleDateChange = async (date: Date | null) => {
        setSelectedDate(date);
        setShowCalendar(false);

        if (!date) return;

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
        <div className="bg-cyan-800 text-white text-3xl font-bold py-4 w-full text-left px-4">
            <h1>木材検査システム 検査履歴一覧画面​</h1>
        </div>
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

                <h1 className="text-3xl font-bold mb-4 text-center">検査履歴一覧</h1>

                <div className="relative">
                    {/* Calendar Popup */}
                    {showCalendar && (
                    <div className="absolute right-[-280px] top-[-30px] z-50 bg-white p-4 rounded shadow border border-gray-300">
                        <DatePicker
                        selected={selectedDate}
                        onChange={handleDateChange}
                        inline
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

                {/* list result get component */}
                {inspections.length > 0 ? (
                    <InspectionList inspections={inspections} />
                ) : (
                    <p className="text-center text-gray-500">表示するデータがありません。</p>
                )}
            </div>
        </div>
    </div>
  );
};

export default InspectionHistoryScreen;
