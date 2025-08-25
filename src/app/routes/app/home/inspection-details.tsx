import React from 'react';
import { api } from '@/lib/api-client';
import { dateToString } from '@/utils/cn';
import { ApiResult, Inspection } from '@/types/api';
import { Spinner } from '@/components/ui/spinner';

type Props = {
  isLoading: boolean;
  data: ApiResult<Inspection> | undefined;
};

const InspectionDetails = ({ isLoading, data }: Props) => {
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
                ? data.result === true
                  ? dateToString(data.data.inspection_dt)
                  : 'なし'
                : ''}
          </h2>
        </div>
      </div>
      <div className="flex flex-row items-center mb-4">
        <h2 className="text-4xl mr-4" style={{ flex: 1 }}>
          シリアルNo:
        </h2>
        <div style={{ flex: 2 }}>
          <h2 className="text-4xl h-auto w-full">
            {isLoading
              ? '取得中'
              : data
                ? data.result === true
                  ? data.data.serial
                  : 'なし'
                : ''}
          </h2>
        </div>
      </div>
      <div className="h-full">
        {data && data.result ? (
          data.data.file_path ? (
            <img
              src={`${api.defaults.baseURL}/${data.data.file_path}`}
              alt="inspection image"
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
