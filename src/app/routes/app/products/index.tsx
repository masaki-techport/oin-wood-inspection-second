import React, { useEffect, useMemo, useState } from 'react';

import { DefaultLayout } from '@/components/layouts';
import {
  GetProductFilter,
  useDeleteProduct,
  useProducts,
} from '@/features/products/api';
import { Product } from '@/types/api';
import {
  DataGrid,
  GridColDef,
  GridPaginationModel,
  GridRowSelectionModel,
  GridSortModel,
} from '@mui/x-data-grid';
import { Grid } from '@mui/material';
import CreateUpdateProductModal from './create-update-product-modal';
import ConfirmDialog from '@/components/ui/confirm-dialog';
import { useNotifications } from '@/components/ui/notifications';
import ImagePreviewDialog from '@/components/ui/image-preview-dialog';
import { useNavigate, useLocation } from 'react-router-dom';
import Button from '@/components/ui/button';
import ProductFilters from './product-filters';
import { api } from '@/lib/api-client';

const parseNumber = (value: string | null) => {
  const parsed = Number(value);
  return isNaN(parsed) ? 0 : parsed;
};

const parseDate = (value: string | null) => {
  return value ? new Date(value) : null;
};

const PAGE_SIZE = 10;
const ProductsPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const query = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  );

  const [filter, setFilter] = useState<GetProductFilter>({
    pageNo: parseNumber(query.get('pageNo')) || 1,
    pageSize: parseNumber(query.get('pageSize')) || PAGE_SIZE,
    productNo: query.get('productNo') || '',
    productName: query.get('productName') || '',
    fromDate: parseDate(query.get('fromDate')) || undefined,
    toDate: parseDate(query.get('toDate')) || undefined,
    orderBy: query.get('orderBy') || undefined,
    order: query.get('order') || undefined,
  });

  useEffect(() => {
    const params = new URLSearchParams();
    params.set('pageNo', filter.pageNo.toString());
    params.set('pageSize', filter.pageSize.toString());
    if (filter.productNo) params.set('productNo', filter.productNo);
    if (filter.productName) params.set('productName', filter.productName);
    if (filter.fromDate) params.set('fromDate', filter.fromDate.toISOString());
    if (filter.toDate) params.set('toDate', filter.toDate.toISOString());
    if (filter.orderBy) params.set('orderBy', filter.orderBy);
    if (filter.order) params.set('order', filter.order);
    navigate({ search: params.toString() }, { replace: true });
  }, [filter, navigate]);
  const [sortModel, setSortModel] = React.useState<GridSortModel>(
    filter.orderBy && filter.order
      ? [
        {
          field: filter.orderBy,
          sort: filter.order === 'asc' ? 'asc' : 'desc',
        },
      ]
      : [],
  );

  const { data, isLoading } = useProducts({ ...filter });
  const { addNotification } = useNotifications();

  // イメージプレビューダイアログ
  const [openPreview, setOpenPreview] = React.useState(false);
  const [selectedImage, setSelectedImage] = React.useState('');
  const handleClosePreview = () => {
    setOpenPreview(false);
    // setSelectedImage('');
  };
  const handleImageClick = (imageUrl: string) => {
    setSelectedImage(imageUrl);
    setOpenPreview(true);
  };
  const imagePreviewDialog = (
    <ImagePreviewDialog
      open={openPreview}
      src={selectedImage}
      onClose={handleClosePreview}
    />
  );

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [rowSelectionModel, setRowSelectionModel] =
    React.useState<GridRowSelectionModel>([]); // 選択した行情報
  const [selectedProductNo, setSelectedProductNo] = useState<
    string | undefined
  >(); // モーダルに渡すproductNo
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: PAGE_SIZE,
  });

  const columns: GridColDef[] = [
    {
      field: 'product_no',
      headerName: '品番',
      width: 200,
      cellClassName: 'text-2xl',
      headerClassName: 'text-2xl',
    },
    {
      field: 'product_name',
      headerName: '品名',
      width: 300,
      cellClassName: 'text-2xl',
      headerClassName: 'text-2xl',
    },
    {
      field: 'file_path', 
      headerName: 'イメージ',
      width: 300,
      sortable: false,
      cellClassName: 'text-2xl',
      headerClassName: 'text-2xl',
      renderCell: (param) =>
        param.row.file_path ? ( 
          <img
            src={`${api.defaults.baseURL}/${param.row.file_path}`}
            alt="画像"
            className="cursor-pointer object-contain max-w-full max-h-full"
            onClick={() =>
              handleImageClick(`${api.defaults.baseURL}/${param.row.file_path}`)
            }
          />
        ) : (
          'なし'
        ),
    },
  ];
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteConfirmDialog = (
    <ConfirmDialog
      open={deleteOpen}
      title="確認"
      content={`品番「${rowSelectionModel[0]}」 を削除してよろしいですか？`}
      onClose={() => setDeleteOpen(false)}
      onConfirm={() =>
        deleteProductMutation.mutate({
          productNo: rowSelectionModel[0].toString(),
        })
      }
    />
  );
  const deleteProductMutation = useDeleteProduct({
    mutationConfig: {
      onSuccess: ({ result, message }) => {
        if (result) {
          setDeleteOpen(false);
          addNotification({
            type: 'success',
            title: '削除しました',
          });
        } else
          addNotification({
            type: 'error',
            title: message,
          });
      },
    },
  });
  useEffect(() => {
    if (data?.result && data.page_no && data.page_size && data.total_count) {
      setCount(data.total_count);
      const page_no = data.page_no;
      const page_size = data.page_size;
      // data.total_countがレンダーされた後にPaginationModelをセット
      // TODO: setTimeoutじゃなく他の方法で出来ないか検討
      setTimeout(() => {
        setPaginationModel({
          page: page_no - 1,
          pageSize: page_size,
        });
      }, 10);
    }
  }, [data]);

  const [count, setCount] = useState(0); // 直接data.total_countは使えないため

  const handleCreate = () => setIsModalOpen(true);
  const handleEdit = () => {
    setSelectedProductNo(
      rowSelectionModel.length > 0
        ? rowSelectionModel[0].toString()
        : undefined,
    );
    setIsModalOpen(true);
  };
  const handleDelete = () => setDeleteOpen(true);
  const createButton = <Button onClick={handleCreate}>追加</Button>;
  const isSelected = rowSelectionModel.length === 0;
  const editButon = (
    <Button onClick={handleEdit} disabled={isSelected}>
      修正
    </Button>
  );
  const deleteButton = (
    <Button onClick={handleDelete} disabled={isSelected}>
      削除
    </Button>
  );
  const funcButtons = [createButton, editButon, deleteButton];

  return (
    <DefaultLayout title="製品マスター画面">
      {imagePreviewDialog}
      {deleteConfirmDialog}
      <div className="h-full flex flex-col">
        <ProductFilters filter={filter} setFilter={setFilter} />
        <DataGrid
          loading={isLoading}
          getRowId={(row: Product) => row.product_no}
          rows={data?.data}
          columns={columns}
          paginationMode="server"
          rowCount={count}
          paginationModel={paginationModel}
          onPaginationModelChange={(model) => {
            setFilter((prevState) => ({
              ...prevState,
              pageNo: model.page + 1, // 最初のページは1にする
              pageSize: model.pageSize,
            }));
          }}
          onRowSelectionModelChange={(newRowSelectionModel) => {
            setRowSelectionModel(newRowSelectionModel);
          }}
          rowSelectionModel={rowSelectionModel}
          pageSizeOptions={[10, 15, 20]}
          sortingMode="server"
          sortModel={sortModel}
          onSortModelChange={(model) => {
            setSortModel(model);
            setFilter((prevState) => ({
              ...prevState,
              orderBy: model?.[0]?.field,
              order: model?.[0]?.sort?.toString(),
            }));
          }}
          rowHeight={40}
          checkboxSelection
          disableRowSelectionOnClick
          disableMultipleRowSelection
          sx={{ marginBottom: 1 }}
        />
        <CreateUpdateProductModal
          open={isModalOpen}
          onClose={() => {
            setSelectedProductNo(undefined);
            setIsModalOpen(false);
          }}
          initialProductNo={selectedProductNo}
        />
        <div id="func_buttons_container" className="flex flex-row item-center">
          <Grid container spacing={2} alignItems="center">
            {funcButtons.map((btn, index) => (
              <Grid key={`func_buttons_id_${index}`} item xs={2}>
                {btn}
              </Grid>
            ))}
            <Grid item xs={6} container justifyContent="flex-end">
              <Grid item xs={4}>
                <Button
                  onClick={() =>
                    navigate(
                      `/dataset-register?productNo=${rowSelectionModel[0].toString()}`,
                    )
                  }
                  disabled={isSelected}
                >
                  データセット登録
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </div>
      </div>
    </DefaultLayout>
  );
};

export default ProductsPage;
