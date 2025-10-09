import { useEffect, useState } from 'react';

import { DefaultLayout } from '@/components/layouts';
import { CircularProgress, Grid, MenuItem, Select } from '@mui/material';
import Button from '@/components/ui/button';
import { UseDatasets } from '@/features/datasets/api/get-datasets';
import { useLocation } from 'react-router-dom';
import { Datasets } from '@/types/api';
import AddImageModal from './add-image-modal';
import DatasetItem from './dataset-item';
import ImagePreviewDialog from '@/components/ui/image-preview-dialog';
import {
  DatasetsPostData,
  useUpdateDatasets,
} from '@/features/datasets/api/update-datasets';
import { useNotifications } from '@/components/ui/notifications';
import useNavigate from '@/hooks/use-navigate';
import ConfirmationModal from './confirm-save-modal';

type DatasetEdit = {
  unique_id: string; // 管理用
  file?: File; // 追加データセットのファイル、API用
  isDeleted?: boolean; // 削除状態 既存データ用
} & Datasets;
const DatasetRegister = () => {
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const productNo = queryParams.get('productNo');
  const { data, isFetching } = UseDatasets({
    productNo: productNo!,
    queryConfig: {
      enabled: productNo !== '' && productNo !== null,
    },
  });
  const [editData, setEditData] = useState<DatasetEdit[]>([]);

  let backButtonPressed = false;
  window.addEventListener('popstate', function (event) {
      backButtonPressed = true;
  });
  window.addEventListener('beforeunload', function (event) {
      if (backButtonPressed) {
          event.stopImmediatePropagation();
      }
  });
  
  useEffect(() => {
    if (data?.result) {
      const converted = data.data.map<DatasetEdit>((item) => ({
        ...item,
        unique_id: crypto.randomUUID(),
        file_path: `http://localhost:8000/${item.file_path}`,
        isDeleted: false,
      }));
      setEditData(converted);
    }
  }, [data]);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const handleFiles = (files: File[], label: number = -1) => {
    files.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          const src = event.target.result as string;
          setEditData((prev) => [
            ...prev,
            {
              id: -1,
              label,
              file_path: src,
              file: file,
              unique_id: crypto.randomUUID(),
            },
          ]);
        }
      };
      reader.readAsDataURL(file);
    });
    setIsModalOpen(false);
  };
  const addImageModal = (
    <AddImageModal
      open={isModalOpen}
      onFileSelected={handleFiles}
      onClose={() => {
        setIsModalOpen(false);
      }}
    />
  );
  // イメージプレビューダイアログ
  const [openPreview, setOpenPreview] = useState(false);
  const [selectedImage, setSelectedImage] = useState('');
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
  const handleDeleteDataset = (unique_id: string) => {
    setEditData((prev) => {
      const index = prev.findIndex((item) => item.unique_id === unique_id);
      if (index !== -1) {
        if (prev[index].id === -1)
          prev = prev.filter((item) => item.unique_id !== unique_id);
        else {
          const temp = [...prev];
          temp[index] = { ...temp[index], isDeleted: !prev[index].isDeleted };
          prev[index].isDeleted = !prev[index].isDeleted;
          return temp;
        }
      }
      return prev;
    });
  };
  const handleLabelChange = (unique_id: string, label: number) => {
    setEditData((prev) => {
      const index = prev.findIndex((item) => item.unique_id === unique_id);
      if (index !== -1) {
        const temp = [...prev];
        temp[index] = { ...temp[index], label: label };
        prev[index].isDeleted = !prev[index].isDeleted;
        return temp;
      }
      return prev;
    });
  };
  const { addNotification } = useNotifications();
  const updateDatasetsMutation = useUpdateDatasets({
    mutationConfig: {
      onError: () => {
        // ファイル読み込み失敗時
        addNotification({
          type: 'error',
          title: 'エラー発生',
        });
      },
      onSuccess: ({ result, message }) => {
        if (!result) {
          addNotification({
            type: 'error',
            title: message,
          });
        }
      },
    },
  });
  const handleUpdate = () => {
    updateDatasetsMutation.mutate({ data: postData });
  };
  const [postData, setPostData] = useState<DatasetsPostData>({
    product_no: productNo || '',
    datasets: [],
    files: [],
  });
  useEffect(() => {
    const changedPostData: DatasetsPostData = {
      product_no: productNo || '',
      datasets: [],
      files: [],
    };
    let file_index = 0;
    editData.forEach((item) => {
      if (item.id !== -1) {
        const defaultData = data?.data.find((dat) => dat.id === item.id);
        if (item.isDeleted) {
          changedPostData.datasets.push({
            action: 'delete',
            id: item.id,
          });
        } else if (defaultData?.label !== item.label) {
          changedPostData.datasets.push({
            action: 'update',
            id: item.id,
            label: item.label,
          });
        }
      } else {
        changedPostData.datasets.push({
          action: 'add',
          label: item.label,
          file_index: file_index,
        });
        changedPostData.files.push(item.file as File);
        file_index++;
      }
    });
    setPostData(changedPostData);
  }, [productNo, data?.data, editData]);
  const { setBlocking } = useNavigate();

  useEffect(() => {
    if (postData.datasets.length > 0) {
      setBlocking(true);
    } else {
      setBlocking(false);
    }
  }, [postData.datasets.length, setBlocking]);

  const isDisabled = isFetching || updateDatasetsMutation.isPending;
  const [displayData, setDisplayData] = useState<DatasetEdit[]>([]);
  const [label, setLabel] = useState<number | ''>('');
  useEffect(() => {
    setDisplayData(
      label === '' ? editData : editData.filter((item) => item.label === label),
    );
  }, [editData, label]);

  // Show saving confirmation modal before back to the pevious page
  const [showModal, setShowModal] = useState(false);
  useEffect(() => {
    window.history.pushState({ name: "browserBack" }, "on browser back click", window.location.href);
    window.history.pushState({ name: "browserBack" }, "on browser back click", window.location.href);
    const handlePopState = (event: any) => {
      console.log('Datasets length:', postData.datasets.length);
      if (event.state && !showModal && postData.datasets.length > 0) {
        setShowModal(true);
      } else if (event.state && showModal) {
        return;
      } else {
        window.location.href = '/products';
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [showModal, postData.datasets.length]);

  const handleConfirmBack = async () => {
    try {
      await new Promise((resolve, reject) => {
        updateDatasetsMutation.mutate(
          { data: postData },
          {
            onSuccess: () => resolve(true),
            onError: (error) => reject(error),
          }
        );
      });
  
      window.location.href = '/products';
    } catch (error) {
      console.error('Error updating datasets:', error);
    }
  };

  const handleCancelBack = () => {
    setShowModal(false);
    window.location.href = '/products';
  };

  return (
    <DefaultLayout title="データセット登録画面">
      <div className="flex flex-col h-full">
        {imagePreviewDialog}
        {addImageModal}
        <ConfirmationModal open={showModal} onConfirm={handleConfirmBack} onCancel={handleCancelBack} />
        <Grid container alignItems="center" gap={2} marginBottom={2}>
          <Grid item xs={3}>
            <h2 className="text-4xl">品番: {productNo}</h2>
          </Grid>
          <Grid item xs={2}>
            <Select
              fullWidth
              sx={{ fontSize: 24 }}
              value={label === '' ? '' : label}
              onChange={(ev) => setLabel(ev.target.value as number | '')}
            >
              <MenuItem value="" sx={{ fontSize: 24 }}>
                フィルターなし
              </MenuItem>
              <MenuItem value={0} sx={{ fontSize: 24 }}>
                OK
              </MenuItem>
              <MenuItem value={1} sx={{ fontSize: 24 }}>
                NG
              </MenuItem>
              <MenuItem value={-1} sx={{ fontSize: 24 }}>
                未指定
              </MenuItem>
            </Select>
          </Grid>
        </Grid>
        <Grid
          container
          marginBottom={2}
          gap={2}
          padding={2}
          sx={{
            border: '1px solid lightgray',
            borderRadius: 1,
            flex: 1,
            overflowY: 'auto',
          }}
        >
          {isDisabled ? (
            <Grid
              item
              className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"
            >
              <CircularProgress />
            </Grid>
          ) : (
            displayData.map((item) => (
              <Grid key={item.unique_id} item xs={6} sm={4} md={1.9}>
                <DatasetItem
                  imgSrc={item.file_path}
                  label={item.label}
                  unique_id={item.unique_id}
                  onImageClick={handleImageClick}
                  onClose={handleDeleteDataset}
                  isDeleted={item.isDeleted}
                  onLabelChange={handleLabelChange}
                />
              </Grid>
            ))
          )}
        </Grid>
        <Grid container alignItems="center" gap={2}>
          <Grid item xs={2}>
            <Button onClick={() => setIsModalOpen(true)} disabled={isDisabled}>
              画像アップロード
            </Button>
          </Grid>
          <Grid item xs={2}>
            <Button
              onClick={handleUpdate}
              disabled={isDisabled || postData.datasets.length === 0}
            >
              登録
            </Button>
          </Grid>
        </Grid>
      </div>
    </DefaultLayout>
  );
};

export default DatasetRegister;
