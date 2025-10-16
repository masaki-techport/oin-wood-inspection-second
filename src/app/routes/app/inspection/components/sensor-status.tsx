import React, { useEffect, useState } from "react";

// センサの状態を表す型を定義
type SensorStatus = {
  a_sensor: boolean | null; // Aセンサの値（数値または未取得時はnull）
  b_sensor: boolean | null; // Bセンサの値（数値または未取得時はnull）
};

const SensorStatusComponent: React.FC = () => {
  // センサ状態を管理するstateを初期化
  const [status, setStatus] = useState<SensorStatus>({ a_sensor: null, b_sensor: null });
  // エラー状態を管理するstateを追加
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // センサ状態をAPIから取得する非同期関数
    const fetchStatus = async () => {
      try {
        const res = await fetch("/inspection_status/latest"); // 最新のセンサ状態を取得
        if (!res.ok) {
          throw new Error(`APIリクエスト失敗: ${res.status}`);
        }
        const data = await res.json(); // レスポンスをJSONとしてパース
        setStatus({ a_sensor: data.a_sensor, b_sensor: data.b_sensor }); // stateを更新
        setError(null); // エラーをクリア
      } catch (err: any) {
        setError(err.message || "センサ状態の取得中にエラーが発生しました");
      }
    };

    fetchStatus(); // 初回マウント時に一度だけ実行

    // 100msごとにセンサ状態を取得
    const interval = setInterval(fetchStatus, 100);

    // コンポーネントのアンマウント時にintervalを解除
    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <h2>センサ状態</h2>
      {/* エラーがあれば表示 */}
      {error && <div style={{ color: "red" }}>エラー: {error}</div>}
      {/* Aセンサの状態を表示。取得できていなければ「取得中...」と表示 */}
      <div>Aセンサ: {status.a_sensor === null ? "取得中..." : status.a_sensor ? "ON" : "OFF"}</div>
      {/* Bセンサの状態を表示。取得できていなければ「取得中...」と表示 */}
      <div>Bセンサ: {status.b_sensor === null ? "取得中..." : status.b_sensor ? "ON" : "OFF"}</div>
    </div>
  );
};

export default SensorStatusComponent;