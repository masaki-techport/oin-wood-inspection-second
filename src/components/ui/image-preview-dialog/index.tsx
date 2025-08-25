import { Dialog, DialogContent, DialogTitle } from '@mui/material';

const ImagePreviewDialog: React.FC<{
  open: boolean;
  src: string;
  onClose: () => void;
}> = ({ open, src, onClose }) => (
  <Dialog open={open} onClose={onClose}>
    <DialogTitle>画像プレビュー</DialogTitle>
    <DialogContent>
      <img src={src} alt="画像" className="w-full h-auto shadow-md" />
    </DialogContent>
  </Dialog>
);

export default ImagePreviewDialog;
