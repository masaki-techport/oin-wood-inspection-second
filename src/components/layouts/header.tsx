const Header = ({ text }: { text: string }) => (
  <div className="bg-cyan-800 text-white text-3xl font-bold py-4 w-full relative flex items-center px-8">
    <div className="w-32 flex-shrink-0 flex items-center justify-start">
      <img src="/OINlogo.png" alt="OiN Logo" className="h-8" />
    </div>
    <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 whitespace-nowrap">
      {text}
    </div>
    <div className="w-32 flex-shrink-0" />
  </div>
);
export default Header;