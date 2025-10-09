import { useLocation } from 'react-router-dom';
import Timer from '../ui/timer';
import useNavigate from '@/hooks/use-navigate';

const Header = () => {
  const { navigate } = useNavigate();
  const location = useLocation();
  return (
    <header className={'min-h-16 px-4 border-b border-gray-300 shadow-md'}>
      <nav className="h-full">
        <ul className="flex h-full">
          <li>
            <div
              onClick={() => location.pathname !== '/' && navigate('/')}
              className={`${location.pathname === '/' ? 'bg-gray-300 ' : ''}text-3xl cursor-pointer flex items-center justify-center h-full hover:bg-gray-300 rounded transition duration-300 px-4`}
            >
              ホーム
            </div>
          </li>
          <li>
            <div
              onClick={() =>
                location.pathname !== '/products' && navigate('/products')
              }
              className={`${location.pathname === '/products' ? 'bg-gray-300 ' : ''}text-3xl cursor-pointer flex items-center justify-center h-full hover:bg-gray-300 rounded transition duration-300 px-4`}
            >
              品番マスタ
            </div>
          </li>
          <li className="ml-auto">
            <div className="text-3xl flex items-center justify-center h-full hover:bg-gray-300 rounded transition duration-300 px-4">
              <Timer />
            </div>
          </li>
        </ul>
      </nav>
    </header>
  );
};

export default Header;
