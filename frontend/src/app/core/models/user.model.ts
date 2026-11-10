/** User profile as returned by the FastAPI backend (Firestore users/{uid}). */
export interface AppUser {
  uid: string;
  name: string | null;
  email: string | null;
  created_at: string | null;
  last_login_at: string | null;
}
