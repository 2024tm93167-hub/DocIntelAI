import { Injectable, computed, signal } from '@angular/core';
import {
  User,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
} from 'firebase/auth';

import { getFirebaseAuth } from '../firebase/firebase.config';

/**
 * Wraps the Firebase Authentication client SDK. This is the ONLY place in the
 * frontend allowed to talk to Firebase directly (application data always goes
 * through the FastAPI backend).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly auth = getFirebaseAuth();
  private readonly currentUserSignal = signal<User | null>(null);
  private resolveReady!: () => void;

  /** Resolves once Firebase has reported the initial auth state (used by guards). */
  readonly ready: Promise<void> = new Promise((resolve) => {
    this.resolveReady = resolve;
  });

  readonly currentUser = this.currentUserSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.currentUserSignal() !== null);

  constructor() {
    let firstEmission = true;
    onAuthStateChanged(this.auth, (user) => {
      this.currentUserSignal.set(user);
      if (firstEmission) {
        firstEmission = false;
        this.resolveReady();
      }
    });
  }

  async register(name: string, email: string, password: string): Promise<void> {
    const credential = await createUserWithEmailAndPassword(this.auth, email, password);
    if (name) {
      await updateProfile(credential.user, { displayName: name });
    }
  }

  async login(email: string, password: string): Promise<void> {
    await signInWithEmailAndPassword(this.auth, email, password);
  }

  async logout(): Promise<void> {
    await signOut(this.auth);
  }

  async getIdToken(forceRefresh = false): Promise<string | null> {
    const user = this.auth.currentUser;
    if (!user) {
      return null;
    }
    return user.getIdToken(forceRefresh);
  }
}
