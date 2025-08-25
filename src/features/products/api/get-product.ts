import { queryOptions, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { ApiResult, Product } from '@/types/api';

export const getProduct = ({
  productNo,
}: {
  productNo: string;
}): Promise<ApiResult<Product>> => {
  return api.get(`/products/${productNo}`);
};

export const getProductQueryOptions = (productNo: string) => {
  return queryOptions({
    queryKey: ['product', productNo],
    queryFn: () => getProduct({ productNo }),
  });
};

type UseProductOptions = {
  productNo: string;
  queryConfig?: QueryConfig<typeof getProductQueryOptions>;
};

export const useProduct = ({ productNo, queryConfig }: UseProductOptions) => {
  return useQuery({
    ...getProductQueryOptions(productNo),
    ...queryConfig,
  });
};
