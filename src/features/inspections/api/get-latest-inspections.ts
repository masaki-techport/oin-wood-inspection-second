import { queryOptions, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { ApiResult, Inspection } from '@/types/api';

export const getLatestInspection = ({
  productNo,
}: {
  productNo: string;
}): Promise<ApiResult<Inspection>> => {
  return api.get(`/inspections/latest`, {
    params: { product_no: productNo },
  });
};

export const getLatestInspectionQueryOptions = (productNo: string) => {
  return queryOptions({
    queryKey: ['latestInspection', productNo],
    queryFn: () => getLatestInspection({ productNo }),
  });
};

type UseLatestInspectionOptions = {
  productNo: string;
  queryConfig?: QueryConfig<typeof getLatestInspectionQueryOptions>;
};

export const UseLatestInspection = ({
  productNo,
  queryConfig,
}: UseLatestInspectionOptions) => {
  return useQuery({
    ...getLatestInspectionQueryOptions(productNo),
    ...queryConfig,
  });
};
