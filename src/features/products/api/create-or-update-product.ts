import { useMutation, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';

import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';
import { ApiResult } from '@/types/api';

export type ProductFormData = {
  product_no: string;
  product_name: string;
  product_file?: File;
};
export const createOrUpdateProductInputSchema = z.object({
  product_no: z.string().min(1, '必須').length(10, '10文字で入力してください'),
  product_name: z.string().min(1, '必須'),
  product_file: z
    .custom<File>()
    .optional()
    .refine((file) => {
      if (!file) return true;
      const validTypes = ['image/jpeg', 'image/png'];
      return validTypes.includes(file.type);
    }, 'ファイル型不正'),
});

export type CreateOrUpdateProductInput = z.infer<
  typeof createOrUpdateProductInputSchema
>;

export const createOrUpdateProduct = (create: boolean) => {
  return async ({
    data,
  }: {
    data: ProductFormData;
  }): Promise<ApiResult> => {
    const api_func = create ? api.post : api.patch;
    const formData = new FormData();
    formData.append('product_no', data.product_no);
    formData.append('product_name', data.product_name);
    if (data.product_file) {
      formData.append('product_file', data.product_file);
    }

    return api_func('/products', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  };
};

const createProduct = createOrUpdateProduct(true);
const updateProduct = createOrUpdateProduct(false);
type UseUpdateProductOptions = {
  mutationConfig?: MutationConfig<typeof updateProduct>;
};

export const useCreateOrUpdateProduct = (
  create: boolean,
  { mutationConfig }: UseUpdateProductOptions = {},
) => {
  const queryClient = useQueryClient();

  const { onSuccess, ...restConfig } = mutationConfig || {};
  return useMutation({
    onSuccess: (data, ...args) => {
      queryClient.invalidateQueries({
        // TODO: 定数化
        queryKey: ['products'], //getProductsQueryOptions().queryKey,
      });
      onSuccess?.(data, ...args);
    },
    ...restConfig,
    mutationFn: create ? createProduct : updateProduct,
  });
};
