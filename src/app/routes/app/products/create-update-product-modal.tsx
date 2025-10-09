import { zodResolver } from '@hookform/resolvers/zod';
import React, { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import {
  Box,
  TextField,
  Button,
  Typography,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
} from '@mui/material';
import { useNotifications } from '@/components/ui/notifications';
import { GridCloseIcon } from '@mui/x-data-grid';
import {
  ProductFormData,
  createOrUpdateProductInputSchema,
  useProduct,
  useCreateOrUpdateProduct,
} from '@/features/products/api';
type productModalProps = {
  open: boolean;
  onClose: () => void;
  onSave?: (data: ProductFormData) => void;
  initialProductNo?: string;
};

const CreateUpdateProductModal = ({
  open,
  onClose,
  onSave,
  initialProductNo,
}: productModalProps) => {
  const isCreateModal = initialProductNo === undefined;
  const { addNotification } = useNotifications();
  const { data, isLoading, refetch } = useProduct({
    productNo: initialProductNo ? initialProductNo : '',
    queryConfig: {
      enabled: false,
    },
  });
  const updateProductMutation = useCreateOrUpdateProduct(isCreateModal, {
    mutationConfig: {
      onError: () => {
        // ファイル読み込み失敗時
        addNotification({
          type: 'error',
          title: 'エラー発生',
        });
      },
      onSuccess: ({ result, message }) => {
        if (result) onClose();
        else
          addNotification({
            type: 'error',
            title: message,
          });
      },
    },
  });

  const {
    control,
    handleSubmit,
    setValue,
    formState: { errors },
    reset,
  } = useForm<ProductFormData>({
    resolver: zodResolver(createOrUpdateProductInputSchema),
    defaultValues: { product_no: '', product_name: '' },
  });

  const onSubmit = (data: ProductFormData) => {
    onSave && onSave(data);
    updateProductMutation.mutate({
      data,
    });
  };

  // フォームオープンのたびに、フォームをリセット
  useEffect(() => {
    if (open) {
      reset();
    }
  }, [open, reset]);

  // フォームオープンかつ修正の場合、該当品番情報を取得
  useEffect(() => {
    if (open && initialProductNo) {
      refetch();
    }
  }, [open, refetch, initialProductNo]);

  // データ取得出来たら、フォームに設定
  useEffect(() => {
    if (data && data.result) {
      const { product_no, product_name } = data.data;
      setValue('product_no', product_no);
      setValue('product_name', product_name);
    }
  }, [data, setValue]);
  // 品番情報取得中もしくは更新中は操作を無効化
  const isDisabled = isLoading || updateProductMutation.isPending;

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle fontSize={24}>{isCreateModal ? '追加' : '修正'}</DialogTitle>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <Controller
            name="product_no"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="品番"
                fullWidth
                margin="normal"
                variant="outlined"
                error={Boolean(errors.product_no)}
                helperText={errors.product_no?.message}
                disabled={!isCreateModal || isDisabled}
              />
            )}
          />
          <Controller
            name="product_name"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="品名"
                fullWidth
                margin="normal"
                variant="outlined"
                error={Boolean(errors.product_name)}
                helperText={errors.product_name?.message}
                disabled={isDisabled}
              />
            )}
          />
          <Controller
            name="product_file"
            control={control}
            render={({ field }) => (
              <Box>
                <input
                  type="file"
                  id="file"
                  accept="image/jpeg,image/png"
                  onChange={(event) => {
                    if (event.target.files && event.target.files[0]) {
                      field.onChange(event.target.files[0]);
                    }
                  }}
                  style={{ display: 'none' }}
                  disabled={isDisabled}
                />
                <label htmlFor="file">
                  <Button
                    component="span"
                    variant="outlined"
                    color="primary"
                    disabled={isDisabled}
                  >
                    イメージ選択
                  </Button>
                </label>
                {field.value && (
                  <IconButton
                    onClick={() => field.onChange(undefined)}
                    size="small"
                    color="error"
                  >
                    {' '}
                    <GridCloseIcon />
                  </IconButton>
                )}
                {errors.product_file && (
                  <Typography variant="body2" color="error">
                    {errors.product_file.message}
                  </Typography>
                )}
                {!errors.product_file && field.value && (
                  <Typography variant="body1" color="textSecondary">
                    {field.value.name}
                  </Typography>
                )}
              </Box>
            )}
          />
        </form>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="secondary" disabled={isDisabled}>
          キャンセル
        </Button>
        <Button
          onClick={handleSubmit(onSubmit)}
          color="primary"
          disabled={isDisabled}
        >
          保存
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CreateUpdateProductModal;
