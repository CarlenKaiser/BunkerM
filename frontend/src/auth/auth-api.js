import express from 'express';
import path from 'path';
import cors from 'cors';
import bodyParser from 'body-parser';
import { fileURLToPath } from 'url';
import fs from 'fs';
import admin from 'firebase-admin';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.AUTH_API_PORT || 3001;

// Initialize Firebase Admin SDK
admin.initializeApp({
  credential: admin.credential.applicationDefault(),
});

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
}

// Middleware
app.use(cors({
  origin: process.env.NODE_ENV === 'production' 
    ? ['https://bunkerm.cpmfgoperations.com']
    : '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-API-Key']
}));
app.use(bodyParser.json());

// Verify Firebase ID token middleware
async function verifyFirebaseToken(req, res, next) {
  const authHeader = req.headers.authorization || '';
  const token = authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : null;

  if (!token) {
    return res.status(401).json({ error: 'Unauthorized: No token provided' });
  }

  try {
    const decodedToken = await admin.auth().verifyIdToken(token);
    req.firebaseUser = decodedToken;
    next();
  } catch (error) {
    log(`Firebase token verification error: ${error.message}`);
    return res.status(401).json({ error: 'Unauthorized: Invalid token' });
  }
}

// Require admin role middleware - FIXED
async function requireAdmin(req, res, next) {
  try {
    // Fetch the user record to get fresh custom claims
    const userRecord = await admin.auth().getUser(req.firebaseUser.uid);
    const customClaims = userRecord.customClaims || {};
    
    if (!customClaims.role || customClaims.role !== 'admin') {
      return res.status(403).json({ error: 'Forbidden: Admin access required' });
    }
    
    // Attach user record for potential use in routes
    req.userRecord = userRecord;
    next();
  } catch (error) {
    log(`Error checking admin role: ${error.message}`);
    return res.status(500).json({ error: 'Error verifying permissions' });
  }
}

// Health check endpoint
app.get('/api/auth/health', (req, res) => {
  log('Health check requested');
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Get current user's profile
app.get('/api/auth/profile', verifyFirebaseToken, async (req, res) => {
  try {
    const userRecord = await admin.auth().getUser(req.firebaseUser.uid);
    res.json({
      uid: userRecord.uid,
      email: userRecord.email,
      displayName: userRecord.displayName,
      photoURL: userRecord.photoURL,
      emailVerified: userRecord.emailVerified,
      disabled: userRecord.disabled,
      metadata: userRecord.metadata,
      providerData: userRecord.providerData,
      customClaims: userRecord.customClaims || {},
    });
  } catch (error) {
    log(`Error fetching user profile: ${error.message}`);
    res.status(500).json({ error: 'Failed to fetch user profile' });
  }
});

// List all Firebase users (paginated) — Admin only
app.get('/api/auth/users', verifyFirebaseToken, requireAdmin, async (req, res) => {
  const maxResults = 1000;
  const pageToken = req.query.pageToken || undefined;

  try {
    const listUsersResult = await admin.auth().listUsers(maxResults, pageToken);
    const users = listUsersResult.users.map(user => ({
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
      emailVerified: user.emailVerified,
      disabled: user.disabled,
      customClaims: user.customClaims || {},
      metadata: user.metadata,
      providerData: user.providerData,
    }));
    res.json({
      users,
      nextPageToken: listUsersResult.pageToken || null,
    });
  } catch (error) {
    log(`Error listing users: ${error.message}`);
    res.status(500).json({ error: 'Failed to list users' });
  }
});

// Update user profile and roles (Admin only)
app.put('/api/auth/users/:uid', verifyFirebaseToken, requireAdmin, async (req, res) => {
  const { uid } = req.params;
  const { displayName, photoURL, disabled, role } = req.body;

  // Validate role if provided
  if (role !== undefined && !['admin', 'moderator', 'user', null, ''].includes(role)) {
    return res.status(400).json({ error: 'Invalid role. Must be admin, moderator, user, or empty' });
  }

  // Prevent admin from removing their own admin role
  if (uid === req.firebaseUser.uid && role && role !== 'admin') {
    return res.status(400).json({ error: 'Cannot remove your own admin privileges' });
  }

  try {
    const updateData = {};
    if (displayName !== undefined) updateData.displayName = displayName;
    if (photoURL !== undefined) updateData.photoURL = photoURL;
    if (disabled !== undefined) updateData.disabled = disabled;

    const updatedUser = await admin.auth().updateUser(uid, updateData);

    // Update custom claims (roles)
    if (role !== undefined) {
      if (role && role.trim()) {
        await admin.auth().setCustomUserClaims(uid, { role: role.trim() });
      } else {
        await admin.auth().setCustomUserClaims(uid, { role: 'user' });
      }
    }

    // Fetch updated claims to return
    const refreshedUser = await admin.auth().getUser(uid);

    res.json({
      message: 'User updated successfully',
      uid: refreshedUser.uid,
      email: refreshedUser.email,
      displayName: refreshedUser.displayName,
      photoURL: refreshedUser.photoURL,
      disabled: refreshedUser.disabled,
      customClaims: refreshedUser.customClaims || {},
    });
  } catch (error) {
    log(`Error updating user ${uid}: ${error.message}`);
    res.status(500).json({ error: 'Failed to update user', details: error.message });
  }
});

// Delete a user (Admin only)
app.delete('/api/auth/users/:uid', verifyFirebaseToken, requireAdmin, async (req, res) => {
  const { uid } = req.params;

  if (uid === req.firebaseUser.uid) {
    return res.status(400).json({ error: 'Cannot delete currently authenticated user' });
  }

  try {
    await admin.auth().deleteUser(uid);
    log(`Deleted user with UID: ${uid}`);
    res.json({ message: `User ${uid} deleted successfully` });
  } catch (error) {
    log(`Error deleting user ${uid}: ${error.message}`);
    res.status(500).json({ error: 'Failed to delete user' });
  }
});

// Set initial admin user (one-time setup endpoint)
app.post('/api/auth/setup-admin', verifyFirebaseToken, async (req, res) => {
  try {
    console.log('Request received:', {
      uid: req.firebaseUser.uid,
      email: req.firebaseUser.email,
      headers: req.headers
    });

    const listResult = await admin.auth().listUsers(1000);
    const hasAdmin = listResult.users.some(user => 
      user.customClaims && user.customClaims.role === 'admin'
    );
    
    if (hasAdmin) {
      console.log('Admin exists check failed - admin already exists');
      return res.status(400).json({ error: 'Admin user already exists' });
    }
    
    await admin.auth().setCustomUserClaims(req.firebaseUser.uid, { role: 'admin' });
    
    console.log(`Successfully set admin claims for ${req.firebaseUser.uid}`);
    res.json({ message: 'Initial admin user created successfully' });
  } catch (error) {
    console.error('Full error details:', {
      message: error.message,
      stack: error.stack,
      code: error.code,
      fullError: JSON.stringify(error, Object.getOwnPropertyNames(error))
    });
    res.status(500).json({ 
      error: 'Failed to setup admin user',
      details: error.message 
    });
  }
});

// Reset all users except current user (Admin only)
app.delete('/api/auth/reset', verifyFirebaseToken, requireAdmin, async (req, res) => {
  try {
    let nextPageToken = undefined;
    const allUserUids = [];

    do {
      const result = await admin.auth().listUsers(1000, nextPageToken);
      result.users.forEach(user => allUserUids.push(user.uid));
      nextPageToken = result.pageToken;
    } while (nextPageToken);

    const currentUid = req.firebaseUser.uid;
    const uidsToDelete = allUserUids.filter(uid => uid !== currentUid);

    const BATCH_SIZE = 1000;
    for (let i = 0; i < uidsToDelete.length; i += BATCH_SIZE) {
      const batch = uidsToDelete.slice(i, i + BATCH_SIZE);
      await admin.auth().deleteUsers(batch);
    }

    log(`Reset all users except current user (${currentUid}), deleted ${uidsToDelete.length} users.`);
    res.json({ message: `Deleted ${uidsToDelete.length} users. Current user preserved.` });
  } catch (error) {
    log(`Error resetting all users: ${error.message}`);
    res.status(500).json({ error: 'Failed to reset all users', details: error.message });
  }
});

// Error handling middleware (should be last)
app.use((err, req, res, next) => {
  log(`Error: ${err.message}`);
  console.error(err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
app.listen(PORT, () => {
  log(`Auth API server running on port ${PORT}`);
});

export default app;