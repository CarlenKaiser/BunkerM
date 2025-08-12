/**
 * Local Authentication Service
 * 
 * Provides methods for managing local authentication using localStorage.
 * Includes initialization with a default user, user management, and password hashing.
 */

import type { User } from '@/services/auth';
import { hashPassword } from './auth';

// Default user for testing purposes
const DEFAULT_USER: User = {
  id: '1',
  email: 'admin@example.com',
  firstName: 'Admin',
  lastName: 'User',
  createdAt: new Date().toISOString()
};

// Default password for the default user
const DEFAULT_PASSWORD = 'password123';

/**
 * Initialize the local authentication system
 * Ensures localStorage contains required data and a default user/password exists.
 */
export async function initLocalAuth() {
  console.log('Starting initLocalAuth...');

  // Load users from localStorage or initialize empty
  let users: User[] = [];
  const usersJson = localStorage.getItem('users');

  if (usersJson) {
    try {
      users = JSON.parse(usersJson);
      console.log(`Loaded ${users.length} existing users`);
    } catch (err) {
      console.error('Failed to parse users from localStorage:', err);
      users = [];
    }
  }

  // If no users exist, add the default user
  if (users.length === 0) {
    console.log('No users found, adding default user');
    users.push(DEFAULT_USER);
    localStorage.setItem('users', JSON.stringify(users));
  }

  // Load passwords from localStorage or initialize empty
  let passwords: Record<string, string> = {};
  const passwordsJson = localStorage.getItem('passwords');

  if (passwordsJson) {
    try {
      passwords = JSON.parse(passwordsJson);
      console.log('Loaded existing passwords');
    } catch (err) {
      console.error('Failed to parse passwords from localStorage:', err);
      passwords = {};
    }
  }

  // If default user password missing, hash and save it
  if (!passwords[DEFAULT_USER.id]) {
    try {
      console.log('Hashing default user password...');
      const hashed = await hashPassword(DEFAULT_PASSWORD);
      passwords[DEFAULT_USER.id] = hashed;
      localStorage.setItem('passwords', JSON.stringify(passwords));
      console.log('Default user password hashed and saved');
    } catch (err) {
      console.error('Error hashing default password:', err);
    }
  }

  console.log('Local auth initialization complete');
}

/**
 * Retrieve the currently authenticated user from localStorage
 */
export function getCurrentUser(): User | null {
  const userJson = localStorage.getItem('user');
  if (!userJson) {
    console.log('No authenticated user found');
    return null;
  }

  try {
    const user = JSON.parse(userJson);
    return user;
  } catch (err) {
    console.error('Error parsing authenticated user:', err);
    return null;
  }
}

/**
 * Returns true if there is a currently authenticated user and a token stored
 */
export function isAuthenticated(): boolean {
  const user = getCurrentUser();
  const token = localStorage.getItem('auth_token');
  return !!user && !!token;
}

/**
 * Clears all authentication-related data from localStorage and reinitializes default user
 */
export async function clearAuthData() {
  console.log('Clearing authentication data...');
  localStorage.removeItem('user');
  localStorage.removeItem('users');
  localStorage.removeItem('passwords');
  localStorage.removeItem('auth_token');

  await initLocalAuth();
  console.log('Authentication data cleared and reset');
}

/**
 * Add a demo user to localStorage with hashed password
 */
export async function addDemoUser(
  email: string,
  password: string,
  firstName: string,
  lastName: string
): Promise<User> {
  // Load existing users
  const usersJson = localStorage.getItem('users') || '[]';
  const users: User[] = JSON.parse(usersJson);

  // Prevent duplicate email
  if (users.some(u => u.email === email)) {
    throw new Error('User with this email already exists');
  }

  // Create new user object
  const newUser: User = {
    id: Date.now().toString(),
    email,
    firstName,
    lastName,
    createdAt: new Date().toISOString()
  };

  // Save new user
  users.push(newUser);
  localStorage.setItem('users', JSON.stringify(users));

  // Hash and save password
  const hashedPassword = await hashPassword(password);
  const passwordsJson = localStorage.getItem('passwords') || '{}';
  const passwords = JSON.parse(passwordsJson);
  passwords[newUser.id] = hashedPassword;
  localStorage.setItem('passwords', JSON.stringify(passwords));

  return newUser;
}
