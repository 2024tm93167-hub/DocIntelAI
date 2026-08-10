/** User profile as returned by the FastAPI backend (Firestore users/{uid}). */
export interface AppUser {
  uid: string;
  name: string | null;
  email: string | null;
  createdAt: string | null;
  lastLoginAt: string | null;
}
