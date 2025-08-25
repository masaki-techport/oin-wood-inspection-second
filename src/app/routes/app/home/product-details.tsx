import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Input } from '@/components/ui/form/input';
import { useProduct } from '@/features/products/api';
import { Spinner } from '@/components/ui/spinner';
import InspectionDetails from './inspection-details-ws';
import useLocalStorage from '@/hooks/use-local-storage';
import { api } from '@/lib/api-client';

const ProductDetails = () => {
  const productNoRef = useRef<HTMLInputElement>(null);
  const [productNo, setProductNo] = useLocalStorage('homeProductNo', '');
  const [targetProductNo, setTargetProductNo] = useState(productNo);
  const { data, isLoading, refetch } = useProduct({
    productNo: targetProductNo,
    queryConfig: { enabled: targetProductNo !== '' },
  });
  // const {
  //   data: inspectionData,
  //   isLoading: inspectionIsLoading,
  //   refetch: inspectionRefetch,
  // } = UseLatestInspection({
  //   productNo: targetProductNo,
  //   queryConfig: { enabled: false },
  // });
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (
        event.keyCode === 13 &&
        productNoRef.current === document.activeElement &&
        isLoading === false
      ) {
        setTargetProductNo(productNo);
      }
    },
    [productNo, isLoading],
  );
  useEffect(() => {
    const handleKeyDownWrapper = (event: KeyboardEvent) => handleKeyDown(event);
    document.addEventListener('keydown', handleKeyDownWrapper);

    return () => {
      document.removeEventListener('keydown', handleKeyDownWrapper);
    };
  }, [handleKeyDown]);

  useEffect(() => {
    if (targetProductNo !== '') refetch();
  }, [targetProductNo, refetch]);

  // useEffect(() => {
  //   if (targetProductNo !== '') inspectionRefetch();
  // }, [targetProductNo, inspectionRefetch]);

  // useEffect(() => {
  //   if (targetProductNo !== '') {
  //     const interval = setInterval(() => {
  //       inspectionRefetch();
  //     }, 1000);
  //     return () => clearInterval(interval);
  //   }
  // }, [targetProductNo, inspectionRefetch]);

  return (
    <div id="wrapper" className="flex flex-row h-full">
      <div className="flex-1 h-full">
        <div className="flex flex-col p-4">
          <div className="flex flex-row items-center mb-4">
            <h2 className="text-4xl mr-4">品番:</h2>
            <div className="flex-1">
              <Input
                disabled={isLoading}
                ref={productNoRef}
                className="text-4xl h-auto w-full"
                value={productNo}
                onChange={(ev) => setProductNo(ev.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-row items-center mb-4">
            <h2 className="text-4xl mr-4">品名:</h2>
            <div className="flex-1">
              <h2 className="text-4xl h-auto w-full">
                {isLoading
                  ? '取得中'
                  : data
                    ? data.result === true
                      ? data.data.product_name
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
                  alt="product-image"
                  className="w-full shadow-md p-6 rounded-lg bg-white"
                />
              ) : (
                <h2 className="text-4xl text-center text-red-500">
                  イメージなし
                </h2>
              )
            ) : isLoading ? (
              <Spinner className="mx-auto my-auto" />
            ) : (
              ''
            )}
          </div>
        </div>
      </div>
      <div className="flex-1 h-full">
        <InspectionDetails productNo={targetProductNo} />
        {/* <InspectionDetails
          isLoading={inspectionIsLoading}
          data={inspectionData}
        /> */}
      </div>
    </div>
  );
};

export default ProductDetails;
