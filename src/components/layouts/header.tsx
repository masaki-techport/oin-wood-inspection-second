import { useLocation } from 'react-router-dom';
import StandardHeader from '@/components/ui/StandardHeader';

const Header = () => {

  return (
    <header className="border-b border-gray-300 shadow-md">
      <StandardHeader
        title="木材検査システム TOP​"
        variant="primary"
        showLogo={true}
      />
    </header>
  );
};

export default Header;
