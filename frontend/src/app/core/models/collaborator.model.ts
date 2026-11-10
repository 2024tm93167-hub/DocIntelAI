export type CollaboratorRole = 'owner' | 'editor' | 'viewer';

export interface Collaborator {
  id: string;
  document_id: string;
  user_id: string;
  role: CollaboratorRole;
  email: string | null;
  name: string | null;
  created_at: string | null;
  created_by: string | null;
}

export interface CollaboratorInvite {
  email: string;
  role: 'editor' | 'viewer';
}
