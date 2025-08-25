import React from 'react';

import { DefaultLayout } from '@/components/layouts';
import HomeButton from './home-button';

const HomePage = () => {
  return (
    <DefaultLayout title="ホーム画面">
      <HomeButton />
    </DefaultLayout>
  );
};

export default HomePage;
