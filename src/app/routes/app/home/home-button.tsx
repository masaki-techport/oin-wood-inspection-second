import useNavigate from '@/hooks/use-navigate';
import { useDebugMode } from '@/hooks/use-settings';

const HomeListButton = () => {
  const { navigate } = useNavigate();
  const { isDebugMode } = useDebugMode();

  return (
    <div id="wrapper" className="flex flex-row h-full">
      <div className="flex-1 h-full flex justify-center items-center">
        <div className="flex flex-wrap gap-4 p-4 justify-center">

          <button onClick={() => navigate('/inspection')} style={{ backgroundColor: '#0f9ed5' }} className="flex flex-row  items-center justify-center w-80 h-80 rounded-xl text-white shadow-md px-1 border-[2px] border border-black">
            <img src="/top-search.png" alt="検査" className="w-40 h-40 invert" />
            <span className="text-3xl font-bold">検査</span>
          </button>

          <button onClick={() => navigate('/inspection-history')} style={{ backgroundColor: '#0f9ed5' }} className="flex flex-row items-center justify-center w-80 h-80 rounded-xl text-white shadow-md px-1 border-[2px] border border-black">
            <img src="/top-db.png" alt="検査履歴" className="w-30 h-30 mr-2" />
            <span className="text-3xl font-bold">検査履歴</span>
          </button>

          {isDebugMode && (
            <button onClick={() => navigate('/inference')} style={{ backgroundColor: '#e74c3c' }} className="flex flex-row items-center justify-center w-80 h-80 rounded-xl text-white shadow-md px-1 border-[2px] border border-black">
              <span className="text-6xl font-bold">推論</span>
            </button>
          )}

          <button onClick={() => navigate('/camera-view')} style={{ backgroundColor: '#0f9ed5' }} className="flex flex-row items-center justify-center w-80 h-80 rounded-xl text-white shadow-md px-1 border-[2px] border border-black">
            <img src="/top-camera.png" alt="ピント調整​" className="w-40 h-40"/>
            <span className="text-3xl font-bold">ピント<br />調整​</span>
          </button>

        </div>
      </div>
    </div>
  );
};

export default HomeListButton;