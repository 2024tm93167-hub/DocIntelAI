import { FirebaseApp, initializeApp } from 'firebase/app';
import { Auth, getAuth } from 'firebase/auth';

import { environment } from '../../../environments/environment';

let app: FirebaseApp | undefined;
let authInstance: Auth | undefined;

/** Lazily initializes (once) and returns the Firebase app instance used for client-side Authentication only. */
export function getFirebaseApp(): FirebaseApp {
  if (!app) {
    app = initializeApp(environment.firebase);
  }
  return app;
}

/** Lazily initializes (once) and returns the Firebase Auth instance. */
export function getFirebaseAuth(): Auth {
  if (!authInstance) {
    authInstance = getAuth(getFirebaseApp());
  }
  return authInstance;
}
