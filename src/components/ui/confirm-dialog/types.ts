export type ConfirmDialogProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  content: string;
  confirmButtonText?: string;
  cancelButtonText?: string;
};
