import React, { useState } from 'react';
import Modal from '@/components/modal/Modal';
import CameraModal from '@/components/modal/CameraModal';

const CameraPage: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleOpenModal = () => setIsModalOpen(true);
  const handleCloseModal = () => setIsModalOpen(false);

  return (
    <div className="p-4 text-center">
      <h1 className="text-2xl font-bold mb-4">カメラページ</h1>
      <button
        onClick={handleOpenModal}
        className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded"
      >
        カメラを開く
      </button>

      <Modal isOpen={isModalOpen} onClose={handleCloseModal}>
        <CameraModal onClose={handleCloseModal} />
      </Modal>
    </div>
  );
};

export default CameraPage;
