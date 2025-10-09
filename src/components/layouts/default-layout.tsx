import React from 'react';
import { Helmet, HelmetData } from 'react-helmet-async';
import Header from './header';

type Props = {
  title: string;
  children: React.ReactNode;
};

const helmetData = new HelmetData({});

export const DefaultLayout = ({ title, children }: Props) => {
  return (
    <>
      <Helmet helmetData={helmetData} title={title} defaultTitle={title} />
      <div className="w-screen h-screen flex flex-col">
        <Header />
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </>
  );
};
