import { Dialog, DialogContent, DialogTitle, Grid } from '@mui/material';
import DragAndDropFileZone from './drag-and-drop-file-zone';
import Button from '@/components/ui/button';
import { useRef } from 'react';
type productModalProps = {
  open: boolean;
  onClose: () => void;
  onFileSelected?: (files: File[], label?: number) => void;
};

const AddImageModal = ({
  open,
  onClose,
  onFileSelected,
}: productModalProps) => {
  const handleFiles = (files: File[], label?: number) => {
    onFileSelected?.(files, label);
  };
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const filesArray = Array.from(files).filter((file) =>
        file.type.startsWith('image/'),
      );
      const nonArray: File[] = [];
      const okArray: File[] = [];
      const ngArray: File[] = [];
      filesArray.forEach((file) => {
        const folders = file.webkitRelativePath.split('/');
        // 親フォルダ名が"OK","NG"の場合
        if (folders.length > 1) {
          if (folders[folders.length - 2] === 'OK') {
            okArray.push(file);
          } else if (folders[folders.length - 2] === 'NG') {
            ngArray.push(file);
          } else nonArray.push(file);
        } else nonArray.push(file);
      });
      if (nonArray.length > 0) onFileSelected?.(nonArray);
      if (okArray.length > 0) onFileSelected?.(okArray, 0);
      if (ngArray.length > 0) onFileSelected?.(ngArray, 1);
    }
  };
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xl">
      <DialogTitle fontSize={24}>{'画像アップロード'}</DialogTitle>
      <DialogContent>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          style={{ display: 'none' }}
          multiple
          accept="image/*"
        />
        <input
          type="file"
          ref={folderInputRef}
          onChange={handleFileChange}
          style={{ display: 'none' }}
          {...{ webkitdirectory: '', mozdirectory: '', directory: '' }}
        />
        <DragAndDropFileZone onFileSelected={handleFiles} />
        <Grid container alignItems="center" spacing={2} marginTop={2}>
          <Grid item xs={3}>
            <Button
              onClick={() => {
                if (fileInputRef.current) {
                  fileInputRef.current.click();
                }
              }}
            >
              ファイル選択
            </Button>
          </Grid>
          <Grid item xs={3}>
            <Button
              onClick={() => {
                if (folderInputRef.current) {
                  folderInputRef.current.click();
                }
              }}
            >
              フォルダ選択
            </Button>
          </Grid>
          <Grid item xs={6} container justifyContent="flex-end">
            <Grid item xs={4}>
              <Button onClick={onClose}>閉じる</Button>
            </Grid>
          </Grid>
        </Grid>
      </DialogContent>
    </Dialog>
  );
};

export default AddImageModal;
