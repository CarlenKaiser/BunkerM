// @/types/user.ts
export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role?: string;
  createdAt: string;
}

export type UserRole = 'admin' | 'moderator' | 'user';

export interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
}