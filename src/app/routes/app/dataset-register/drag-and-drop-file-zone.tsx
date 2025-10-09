import React, { useState } from 'react';

const DragAndDropFileZone: React.FC<{
  onFileSelected: (files: File[], label?: number) => void;
}> = ({ onFileSelected }) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };
  const processEntries = (entries: FileSystemEntry[], label?: number) => {
    entries.forEach((entry) => {
      if (entry.isFile) {
        (entry as FileSystemFileEntry).file((file) => {
          if (file.type.startsWith('image/')) {
            onFileSelected([file], label);
          }
        });
      } else if (entry.isDirectory) {
        let label1: number;
        if (entry.name === 'OK') label1 = 0;
        else if (entry.name === 'NG') label1 = 1;
        const reader = (entry as FileSystemDirectoryEntry).createReader();
        reader.readEntries((entries) => {
          // if (entry.isFile) // フォルダの中のフォルダは無視
          // とりあえず全部読み込み
          processEntries(entries, label1);
        });
      }
    });
  };
  const handleFileDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.items);
    const fileEntries: FileSystemEntry[] = [];
    for (let i = 0; i < droppedFiles.length; i++) {
      const entry = droppedFiles[i].webkitGetAsEntry();
      if (entry) fileEntries.push(entry);
    }
    processEntries(fileEntries);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      onFileSelected(Array.from(files));
    }
  };
  const cn =
    'flex items-center min-h-[200px] justify-center text-3xl ' +
    'border-4 border-dashed border-gray-400 rounded-lg ' +
    'cursor-pointer hover:border-blue-500 hover:bg-blue-100';

  return (
    <div className="">
      <label
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleFileDrop}
        className={`${cn} ${isDragging ? 'border-blue-500 bg-blue-100' : ''}`}
      >
        <input
          type="file"
          className="hidden"
          onChange={handleFileSelect}
          multiple
          accept="image/*"
        />
        <div>画像またはフォルダをドロップ</div>
      </label>
    </div>
  );
};

export default DragAndDropFileZone;
