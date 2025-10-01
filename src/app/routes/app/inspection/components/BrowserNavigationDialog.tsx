import React from 'react';

type BrowserNavigationDialogProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  content: string;
};

const BrowserNavigationDialog: React.FC<BrowserNavigationDialogProps> = ({
  open,
  onClose,
  onConfirm,
  title,
  content,
}) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h2 className="text-lg font-semibold mb-4 text-gray-900">{title}</h2>
        <p className="text-gray-700 mb-6">{content}</p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors duration-200 border border-gray-300"
          >
            キャンセル
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors duration-200"
          >
            移動
          </button>
        </div>
      </div>
    </div>
  );
};

export default BrowserNavigationDialog;
