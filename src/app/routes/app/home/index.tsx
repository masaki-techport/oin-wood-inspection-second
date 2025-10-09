import React from 'react';

import { DefaultLayout } from '@/components/layouts';
import ProductDetails from './product-details';

const HomePage = () => {
  return (
    <DefaultLayout title="ホーム画面">
      <ProductDetails />
    </DefaultLayout>
  );
};

export default HomePage;
