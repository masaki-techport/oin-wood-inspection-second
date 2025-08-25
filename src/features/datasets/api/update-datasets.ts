import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';
import { ApiResult } from '@/types/api';

export type DatasetPostData = {
  action: string;
  id?: number;
  label?: number;
  file_index?: number;
};
export type DatasetsPostData = {
  product_no: string;
  datasets: DatasetPostData[];
  files: File[];
};

export const updateDatasets = ({
  data,
}: {
  data: DatasetsPostData;
}): Promise<ApiResult> => {
  const formData = new FormData();
  formData.append('product_no', data.product_no);
  if (data.datasets.length > 0)
    formData.append('datasets_json', JSON.stringify(data.datasets));
  if (data.files.length > 0)
    data.files.forEach((file) => formData.append('files', file));
  return api.post('/datasets', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};
type UseUpdateDatasetsOptions = {
  mutationConfig?: MutationConfig<typeof updateDatasets>;
};

export const useUpdateDatasets = ({
  mutationConfig,
}: UseUpdateDatasetsOptions = {}) => {
  const queryClient = useQueryClient();

  const { onSuccess, ...restConfig } = mutationConfig || {};
  return useMutation({
    onSuccess: (data, ...args) => {
      const { result } = data;
      const {
        data: { product_no },
      } = args[0];
      if (result) {
        queryClient.invalidateQueries({
          queryKey: ['datasets', product_no],
        });
      }
      onSuccess?.(data, ...args);
    },
    ...restConfig,
    mutationFn: updateDatasets,
  });
};
