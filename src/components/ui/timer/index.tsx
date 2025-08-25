import { dateToString } from '@/utils/cn';
import { useEffect, useState } from 'react';

const INTERVAL = 1000;
const Timer = () => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => {
      setTime(new Date());
    }, INTERVAL);

    return () => clearInterval(interval);
  }, []);
  return <>{dateToString(time)}</>;
};

export default Timer;
