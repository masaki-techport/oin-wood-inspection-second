import React, { useState, useEffect } from 'react';
import { Inspection } from '@/types/api';
import { fetchInspectionDetailsById, fetchInspectionResultById } from '@/features/inspections/api/inspections-details';
import InspectionDetailsModal from '@/components/modal/InspectionDetailsModal';

type InspectionListProps = {
    inspections: Inspection[];
};

const InspectionList: React.FC<InspectionListProps> = ({ inspections }) => {

    // モーダル表示の状態管理
    const [showDetail, setShowDetail] = useState(false);
    // 選択された検査データの保存
    const [selectedInspection, setSelectedInspection] = useState<Inspection | null>(null);
    // 検査結果（inspection_idごとに真のキーの配列）を保存するステート
    const [inspectionResults, setInspectionResults] = useState<Record<number, string[]>>({});

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

    // 検査結果のラベルマッピング
    // APIから返されるキーを日本語のラベルに変換するための対応表
    const resultLabels: Record<string, string> = {
        discoloration: '変色',
        hole: '穴',
        knot: '節',
        dead_knot: '流れ節_死',
        tight_knot: '流れ節_生',
        live_knot: '生き節',
    };

    // inspectionsが変更されたときにAPIを呼び、検査結果を取得する
    useEffect(() => {
        const fetchResults = async () => {
            // inspection_idごとの検査結果を格納するオブジェクトを用意
            const resultMap: Record<number, string[]> = {};

            // inspections配列をループし、各inspection_idでAPIを呼ぶ
            for (const item of inspections) {
                const res = await fetchInspectionResultById({ id: item.inspection_id });

                if (res.result && res.data) {
                    const trueKeys = Object.keys(resultLabels).filter(
                        (key) => res.data[key as keyof typeof res.data] === true
                    );
                    resultMap[item.inspection_id] = trueKeys;
                } else {
                    resultMap[item.inspection_id] = [];
                }
            }

            // 取得した検査結果をステートにセットする
            setInspectionResults(resultMap);
        };

        if (inspections.length > 0) {
            fetchResults();
        }
}, [inspections]);

    return (
        <div>
            <div className="max-h-[400px] overflow-y-auto border rounded p-4 shadow">
                <div className="space-y-4">
                    {inspections.map((item, index) => (
                        <div
                            key={item.inspection_id}
                            className="flex justify-between items-center border-b pb-2"
                        >
                        <div>
                            <div>
                                {new Date(item.inspection_dt).toLocaleString(undefined, {
                                    year: 'numeric',
                                    month: '2-digit',
                                    day: '2-digit',
                                    hour: '2-digit',
                                    minute: '2-digit',
                                })}
                                <span className="ml-5 mr-5">板No:{item.inspection_id}</span>

                                {/* 検査結果 */}
                                <span>
                                    {(inspectionResults[item.inspection_id] ?? [])
                                        .map((key) => resultLabels[key])
                                        .join(' , ')}
                                </span>

                            </div>
                        </div>
                        <button
                            onClick={() =>
                                handleShowDetail(item.inspection_id)
                            }
                            className="bg-[#0f9ed5] text-white px-3 py-1 rounded text-lg font-bold"
                        >
                            結果を表示
                        </button>
                        </div>
                    ))}
                </div>
                
                {showDetail && selectedInspection && (
                    <InspectionDetailsModal
                        inspection={selectedInspection}
                        onClose={() => setShowDetail(false)}
                    />
                )}
            </div>
        </div>
    );
};

export default InspectionList;
