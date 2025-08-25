import React from 'react';
import { Link } from 'react-router-dom';

export const NotFoundRoute = () => {
  return (
    <div>
      <h1>404 - Not Found</h1>
      <p>ご指定のページが見つかりません。</p>
      <Link to="/" replace>
        ホーム画面へ戻る
      </Link>
    </div>
  );
};
