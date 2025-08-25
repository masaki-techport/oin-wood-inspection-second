import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { MutationConfig } from '@/lib/react-query';

export const saveImage = async (_: void): Promise<{ path: string }> => {
  await api.post('/api/camera/connect', {}, { suppressGlobalError: true });
  await api.post('/api/camera/stop', {}, { suppressGlobalError: true });
  return await api.post('/api/camera/save', {}, { suppressGlobalError: true });
};

type UseSaveImageOptions = {
  mutationConfig?: MutationConfig<typeof saveImage>;
};

export const useSaveImage = ({ mutationConfig }: UseSaveImageOptions = {}) => {
  return useMutation({
    mutationFn: saveImage,
    ...mutationConfig,
  });
};
