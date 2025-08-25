import { queryOptions, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api-client';
import { QueryConfig } from '@/lib/react-query';
import { ApiResult, Product } from '@/types/api';

export const getProducts = (
  {
    productNo,
    productName,
    fromDate,
    toDate,
    pageNo,
    pageSize,
    orderBy,
    order,
  }: GetProductFilter = { pageNo: 1, pageSize: 10 },
): Promise<ApiResult<Product[]>> => {
  const params: Record<string, string | Date | number | undefined> = {
    product_no: productNo,
    product_name: productName,
    from_dt: fromDate,
    to_dt: toDate,
    page_no: pageNo,
    page_size: pageSize,
    order_by: orderBy,
    order,
  };

  Object.keys(params).forEach((key) => {
    if (params[key] === undefined || params[key] === '') {
      delete params[key];
    }
  });
  return api.get('/products', { params });
};

export type GetProductFilter = {
  productNo?: string;
  productName?: string;
  fromDate?: Date;
  toDate?: Date;
  pageNo: number;
  pageSize: number;
  orderBy?: string;
  order?: string;
};

export const getProductsQueryOptions = (
  {
    productNo,
    productName,
    fromDate,
    toDate,
    pageNo,
    pageSize,
    orderBy,
    order,
  }: GetProductFilter = { pageNo: 1, pageSize: 10 },
) => {
  return queryOptions({
    queryKey: [
      'products',
      productNo,
      productName,
      fromDate,
      toDate,
      pageNo,
      pageSize,
      orderBy,
      order,
    ],
    queryFn: () =>
      getProducts({
        productNo,
        productName,
        fromDate,
        toDate,
        pageNo,
        pageSize,
        orderBy,
        order,
      }),
  });
};

type UseProductsOptions = {
  queryConfig?: QueryConfig<typeof getProductsQueryOptions>;
} & GetProductFilter;

export const useProducts = (
  {
    productNo,
    productName,
    fromDate,
    toDate,
    pageNo,
    pageSize,
    orderBy,
    order,
    queryConfig,
  }: UseProductsOptions = { pageNo: 1, pageSize: 10 },
) => {
  return useQuery({
    ...getProductsQueryOptions({
      productNo,
      productName,
      fromDate,
      toDate,
      pageNo,
      pageSize,
      orderBy,
      order,
    }),
    ...queryConfig,
  });
};
