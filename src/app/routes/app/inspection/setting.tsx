import { useState } from 'react';
import { useSaveImage } from '@/features/inspections/api/save-image';
import { useNotifications } from '@/components/ui/notifications';
import useNavigate from '@/hooks/use-navigate';
import { useLocation } from 'react-router-dom';

const SettingScreen = () => {
    const { navigate } = useNavigate();
    const location = useLocation();
    const ButtonCancelClick = () => {
        if (location.pathname === '/') {
        // previous page Top Page
        window.scrollTo({ top: 0, behavior: 'smooth' });
        } else if (location.pathname === '/specpage') {
        // previous page # Page
        navigate('/#');
        } else {
        // default top page
        navigate('/');
        }
    };

    const [status, setStatus] = useState('待機中');
    const [mode, setMode] = useState('研磨前検査');
    const [count, setCount] = useState(2);
    const [total] = useState(300);
    const { addNotification } = useNotifications();

    return (
        <div className="min-h-screen w-full bg-white text-center overflow-auto px-4 py-8 relative">
            {/* back to top page */}
            <button
                onClick={() => navigate('/')} 
                className="absolute top-4 right-4 text-white bg-gray-500 hover:bg-gray-600 px-4 py-2 rounded"
            >
            TOP
            </button>

            {/* Title */}
            <h1 className="text-4xl font-bold text-center text-cyan-800 mb-8">Page Setting</h1>

            <div className="space-y-6 max-w-3xl mx-auto mb-12">

                <div className="flex items-center gap-2 max-w-3xl mx-auto mb-4">
                    <div className="text-xl font-semibold w-32 text-right">カメラ露光​</div>
                    <input type="text" className="border px-4 py-2 rounded flex-grow max-w-md" />
                </div>
                <div className="flex items-center gap-2 max-w-3xl mx-auto mb-4">
                    <div className="text-xl font-semibold w-32 text-right">照明強度​</div>
                    <input type="text" className="border px-4 py-2 rounded flex-grow max-w-md" />
                </div>
                <div className="flex items-center gap-2 max-w-3xl mx-auto mb-4">
                    <div className="text-xl font-semibold w-32 text-right">AI閾値​</div>
                    <input type="text" className="border px-4 py-2 rounded flex-grow max-w-md" />
                </div>

            </div>


            {/* button Save / Cancel */}
            <div className="flex justify-center gap-8 mt-4">
            <button className="bg-green-600 text-white px-6 py-2 rounded hover:bg-green-700">
                保存
            </button>
            <button
                onClick={ButtonCancelClick}
                className="bg-gray-500 text-white px-6 py-2 rounded hover:bg-gray-600"
                >
                キャンセル
            </button>

            </div>
        </div>
    );
};

export default SettingScreen;
