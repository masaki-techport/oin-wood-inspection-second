import React from 'react';

import { DefaultLayout } from '@/components/layouts';
import SensorStatus from './components/sensor-status';

const InspectionPage = () => {
  return (
    <DefaultLayout title="挽材面検査システム 検査">
      < SensorStatus/>
    </DefaultLayout>
  );
};

export default InspectionPage;
