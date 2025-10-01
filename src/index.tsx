import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './app/'; // appディレクトリ配下のindex.tsxのAppをインポート
import reportWebVitals from './reportWebVitals'; // 動作の速さなどを測るための道具をインポート

// public/index.htmlの中の<div id="root"></div>にReactのアプリを差し込む
const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode> {/* 開発中の間違いを見つけやすくするための囲い */}
    <App /> {/* アプリの本体を画面に表示する */}
  </React.StrictMode>
);

reportWebVitals(); // アプリの動作の速さなどを測る（使わなくてもOK）
