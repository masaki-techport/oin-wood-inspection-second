import { api } from '@/lib/api-client';
import { ApiResult, Inspection } from '@/types/api';

// ==== 型定義 ====

// リクエスト型: 指定された日付で検査記録を取得するために使う
type InspectionByDateRequest = {
  date_selected: string; // 形式: 'YYYY-MM-DD'
};

// ==== API呼び出し関数 ====

// 【API】指定された日付の検査結果を取得
// エンドポイント: /inspections/history
// メソッド: GET
// パラメータ: date_selected（例: '2024-01-01'）
// レスポンス: ApiResult<Inspection[]>（検査結果の配列）
export const fetchInspectionDetailsByDate = (
  data: InspectionByDateRequest
): Promise<ApiResult<Inspection[]>> => {
  return api.get('/inspections/history', {
    params: { date_selected: data.date_selected },
  });
};

// 【API】全ての検査結果を取得（初期表示用など）
// エンドポイント: /inspections/history-all
// メソッド: GET
// パラメータ: なし
// レスポンス: ApiResult<Inspection[]>（全検査結果の配列）
export const fetchInspectionDetailsAll = (): Promise<ApiResult<Inspection[]>> => {
  return api.get('/inspections/history-all');
};


export interface InspectionResultDetail {
  inspection_id: number;
}

export const fetchInspectionResultById = (
  inspection_id: number
): Promise<ApiResult<InspectionResultDetail[]>> => {
  return api.get('/inspections/result', {
    params: { inspection_id },
  });
};
