import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

import { Provider } from 'react-redux';
import { store } from './store'; // yahi jo pehle bhi use kar rahe the

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <Provider store={store}>
      {/* Router already inside App.tsx, so no BrowserRouter here */}
      <App />
    </Provider>
  </React.StrictMode>
);
