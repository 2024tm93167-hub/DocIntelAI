// Production build: the Angular app and the FastAPI backend are served from the
// same origin (nginx proxies /api/* to the backend on 127.0.0.1:8000), so the API
// base URL is derived from the current origin at runtime.
const apiOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8000';

export const environment = {
  production: true,
  apiBaseUrl: `${apiOrigin}/api`,
  firebase: {
    apiKey: 'AIzaSyBSkFx4LxUsonXaMpQ3nTzL4ksxmcGAdrg',
    authDomain: 'intellidoc-187c8.firebaseapp.com',
    projectId: 'intellidoc-187c8',
    storageBucket: 'intellidoc-187c8.firebasestorage.app',
    messagingSenderId: '169127174469',
    appId: '1:169127174469:web:7ee47a08e4cc14578c1e2c',
  },
};
