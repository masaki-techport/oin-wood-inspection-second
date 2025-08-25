import { queryOptions, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { ApiResult, Datasets } from '@/types/api';

export const getDatasets = ({
  productNo,
}: {
  productNo: string;
}): Promise<ApiResult<Datasets[]>> => {
  return api.get(`/datasets`, {
    params: { product_no: productNo },
  });
};

export const getDatasetsQueryOptions = (productNo: string) => {
  return queryOptions({
    queryKey: ['datasets', productNo],
    queryFn: () => getDatasets({ productNo }),
  });
};

type UseDatasetsOptions = {
  productNo: string;
  queryConfig?: QueryConfig<typeof getDatasetsQueryOptions>;
};

export const UseDatasets = ({ productNo, queryConfig }: UseDatasetsOptions) => {
  return useQuery({
    ...getDatasetsQueryOptions(productNo),
    ...queryConfig,
  });
};
