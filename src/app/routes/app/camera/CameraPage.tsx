// pages/CameraPage.tsx
import React, { useState } from 'react';
import Modal from '@/components/modal/Modal';
import CameraModal from '@/components/modal/CameraModal';
import BaslerModal from '@/components/modal/BaslerModal';
import DirectionCameraModal from '@/components/modal/DirectionCameraModal';

type CameraType = 'basler' | 'webcam' | 'direction';

const CameraPage: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isBaslerModalOpen, setIsBaslerModalOpen] = useState(false);
  const [isDirectionModalOpen, setIsDirectionModalOpen] = useState(false);
  const [selectedCameraType, setSelectedCameraType] = useState<CameraType>('webcam');

  const openCameraModal = () => {
    switch (selectedCameraType) {
      case 'basler':
        setIsBaslerModalOpen(true);
        break;
      case 'webcam':
        setIsModalOpen(true);
        break;
      case 'direction':
        setIsDirectionModalOpen(true);
        break;
    }
  };

  const getCameraLabel = (type: CameraType) => {
    switch (type) {
      case 'basler':
        return 'Basler Camera';
      case 'webcam':
        return 'Web Camera';
      case 'direction':
        return 'Direction Camera';
    }
  };

  return (
    <div className="text-center">
      <h1 className="text-2xl font-bold mb-4">カメラページ</h1>

      <div className="flex justify-center items-center gap-4 mb-4">
        {/* Camera Type Dropdown */}
        <div className="flex flex-col items-start">
          <label htmlFor="camera-select" className="text-sm font-medium text-gray-700 mb-1">
            カメラタイプを選択:
          </label>
          <select
            id="camera-select"
            value={selectedCameraType}
            onChange={(e) => setSelectedCameraType(e.target.value as CameraType)}
            className="border border-gray-300 rounded-md px-3 py-2 bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="webcam">Web Camera</option>
            <option value="basler">Basler Camera</option>
            <option value="direction">Direction Camera</option>
          </select>
        </div>

        {/* Open Camera Button */}
        <button
          onClick={openCameraModal}
          className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-md font-medium transition-colors duration-200"
        >
          📹 {getCameraLabel(selectedCameraType)}を開く
        </button>
      </div>

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)}>
        <CameraModal onClose={() => setIsModalOpen(false)} />
      </Modal>

      <Modal isOpen={isBaslerModalOpen} onClose={() => setIsBaslerModalOpen(false)}>
        <BaslerModal onClose={() => setIsBaslerModalOpen(false)} />
      </Modal>

      <Modal isOpen={isDirectionModalOpen} onClose={() => setIsDirectionModalOpen(false)}>
        <DirectionCameraModal onClose={() => setIsDirectionModalOpen(false)} />
      </Modal>
    </div>
  );
};

export default CameraPage;
