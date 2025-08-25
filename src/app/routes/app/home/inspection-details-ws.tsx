import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api-client';
import { dateToString } from '@/utils/cn';
import { Inspection } from '@/types/api';
import { Spinner } from '@/components/ui/spinner';
import { useNotifications } from '@/components/ui/notifications';
import { Button } from '@mui/material';

type Props = {
  productNo: string;
};

const InspectionDetails = ({ productNo }: Props) => {
  const { addNotification } = useNotifications();
  const [data, setData] = useState<Inspection | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (productNo) {
      setIsLoading(true);
      const socket = new WebSocket(
        `ws://${process.env.REACT_APP_API_URL}/inspections/latest/${productNo}`,
      );

      socket.onerror = (event) => {
        // TODO: productNoが変更されてないのにこのuseEffectが２回呼ばれる原因が不明
        // 2回目が呼び出される時点で１回目のsocketが切断されてエラーメッセージが表示される
        // そのため仮対策としてコメントアウト
        // addNotification({
        //   type: 'error',
        //   title: 'エラー発生',
        // });
      };

      socket.onmessage = (event) => {
        setIsLoading(false);
        setData(JSON.parse(event.data) || null);
      };

      return () => {
        socket.close();
      };
    }
  }, [productNo, addNotification]);
  return (
    <div className="flex flex-col p-4">
      <div className="flex flex-row items-center mb-4">
        <h2 className="text-4xl mr-4" style={{ flex: 1 }}>
          最終検査日時:
        </h2>
        <div style={{ flex: 2 }}>
          <h2 className="text-4xl h-auto w-full">
            {isLoading
              ? '取得中'
              : data
                ? dateToString(data.inspection_dt)
                : 'なし'}
          </h2>
        </div>
      </div>
      <div className="flex flex-row items-center mb-4">
        <h2 className="text-4xl mr-4" style={{ flex: 1 }}>
          シリアルNo:
        </h2>
        <div style={{ flex: 2 }}>
          <h2 className="text-4xl h-auto w-full">
            {isLoading ? '取得中' : data ? data.serial : 'なし'}
          </h2>
        </div>
      </div>
      <Button
        sx={{
          width: '100%',
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'black',
          marginBottom: 2,
          fontSize: 24,
        }}
        variant="contained"
        color={
          data ? (!data.inspection_result ? 'success' : 'error') : undefined
        }
      >
        {isLoading ? (
          <Spinner />
        ) : data ? (
          !data.inspection_result ? (
            'OK'
          ) : (
            'NG'
          )
        ) : (
          'なし'
        )}
      </Button>
      <div className="h-full">
        {data ? (
          data.file_path ? (
            <img
              src={`${api.defaults.baseURL}/${data.file_path}`}
              alt="base64"
              className="w-full shadow-md p-6 rounded-lg bg-white"
            />
          ) : (
            <h2 className="text-4xl text-center text-red-500">イメージなし</h2>
          )
        ) : isLoading ? (
          <Spinner className="mx-auto my-auto" />
        ) : (
          ''
        )}
      </div>
    </div>
  );
};

export default InspectionDetails;
