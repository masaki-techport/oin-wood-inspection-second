import React from 'react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    children: React.ReactNode;
}

const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children }) => {
    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
            onClick={onClose}
        >
            <div
                className="bg-white rounded-lg p-4 relative max-w-[90vw] max-h-[90vh] overflow-auto"
                onClick={(e) => e.stopPropagation()}
            >
                {children}
            </div>
        </div>

    );
};

export default Modal;
