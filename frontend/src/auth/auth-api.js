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
  credential: admin.credential.cert({
    projectId: "cpmfgoperations-bunkerm-prod",
    clientEmail: "firebase-adminsdk-fbsvc@cpmfgoperations-bunkerm-prod.iam.gserviceaccount.com",
    privateKey: "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCgGUqMMG/f4b+c\nbKAq3qtbDCWbHKTWkVttG+BnfObYL1vgtGjAPCrrt+PrfWt57zV18UZzeYMPl2w6\nw7lS3pywkhzOjXaNkvjcUfc5MPEI7EVZ3GWyyJ1t9OOFqU0c0ik2hghJVxyWfYg3\nnKcaWSnz+BgDU89bldvjTHaRTtp6G/7+EvX24jWqJyC4VoBhF0htsZbg3bYgMbjj\nDElhWHYWv6zDbLo3BFluAo3T9NyDOc8lRbGhfmpp8KDYtq6xDKyvksq8J7UF1IF3\ncDUv9+sZ/nPNiyiQdnXfHonbMgjIYd80o3ZhFALIaD7yCiSELCSmDgW96qTMWG7h\nnwWGIQZBAgMBAAECggEAALJkUWNxpXcl/h1ivKXdhQ/oB7nqv5Ixra903HuepUBG\npRihGLJQrigHDk7xwGHCCyPnO8VNT0h+8E4aln9Me0lpxfIyQY5HMkhCh43mhu3r\nt5WwYRxHMNm7gg+xh7Hm9kfsLteUhXpQA7SpOARtTgiswrUScioZtfEe27nWJNjh\nt7M4tjtP65fapRmCoIRqRHS2I1fOwlv1lQU8eX4zkeKZWmydQM6Sn/u2CBgmaE8X\nr4nBoJLv1u3ZUZHwK94PSl+fLQBroCUST7ZY3fuWtRsIuwqrd1wyLDXvel02p+cp\ns486bO58Bd6dSgn0rCeWBM56sR42XrDoUmp8nms+gQKBgQDX82OxlVxFsngh1k94\nxCsROu0r5bNoAcKKg+ZadmZ5FJ0Dcj41lTfaPyxUAhYg9ziyQY7mxDpmBuR1xmyf\nGCZ04yOVxw2o03EkbRBSz+TtxrgDxJUaXB2RxmdIPwq93EbuAgVfGrvBg1ATI7mr\nSlyKK8QrKG2vBX/FtV0LfnUdwQKBgQC9yj2FRcBD/caJP1MynALGWm2LH490wpdz\nTk+sZ3iRIU0Bf3dvWK/06G6WBQeM8w5Se7WiaXm8T1JWyqf2pxfRnZM0h2C/TKv5\nWh+SNPY6FpHhhEtnTNbXBvR/DeVg0H5yJBez/fibJSPYTLow/EqJnvDCwakwSmZb\nMDvxne8IgQKBgAeq7bRFgGQ9JQTWjjXUiU7wT7GKU2dzAIxYiJpXr+XGtJiFuu2+\nIaCPM6y78jszbADwUPmiqAwtXHlOFVdEzUDDO+U6jyKad176vGSkWxWSQ8Bmf4DT\nGn2tlMc87c21/5K94aDx2w7Q8cvsLdCGMGj7itiZc+OOB25mtSoOUGxBAoGAEUG9\nXEveUpBVqA8Y+oYS/oQkZ70D50L2UGazeeKipNeZT+SOMJKo1ST5QSzN5fQHvlo/\nRrg+eG/h9cBRi2zgDpA8XU9d7acEEBUwv7OPG/MHarEDxi3Hbx/TxWW3EJmElc5Q\nVW5nV3wGCVnYqDGYeXD5RUwknR52th3ppWuN24ECgYEAzv6pZ8w68vAfzdOk0fZ1\nKksqVVpNvvlKKjpRgXdBJnpkRwDEjNN0z8oDQP8H96blBERUlkjd53KI0jddf7qy\nJ6yof4LWrlHdj72kJpxXxxJC6fcVjjEcWlH7wSoUq17TaWnRr38fJ1nkQEy5yOSa\nanJy8fuEakXN5TX30hp2QSM=\n-----END PRIVATE KEY-----\n"
  })
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
  allowedHeaders: ['Content-Type', 'Authorization']
}));
app.use(bodyParser.json());

// Verify Firebase ID token middleware
async function verifyFirebaseToken(req, res, next) {
  const authHeader = req.headers.authorization || '';
  const token = authHeader.split('Bearer ')[1];

  if (!token) {
    console.log('No token provided');
    return res.status(401).json({ error: 'Unauthorized: No token provided' });
  }

  try {
    console.log('Verifying token:', token.substring(0, 20) + '...');
    const decodedToken = await admin.auth().verifyIdToken(token);
    console.log('Token decoded successfully for UID:', decodedToken.uid);
    req.firebaseUser = decodedToken;
    next();
  } catch (error) {
    console.error('Token verification failed:', {
      error: error.message,
      code: error.code,
      token: token.substring(0, 20) + '...'
    });
    return res.status(401).json({ 
      error: 'Unauthorized: Invalid token',
      details: error.message 
    });
  }
}

// Require admin role middleware
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
    // First, get the current user to see existing custom claims
    const currentUser = await admin.auth().getUser(uid);
    const existingClaims = currentUser.customClaims || {};

    // Update profile fields
    const updateData = {};
    if (displayName !== undefined) updateData.displayName = displayName;
    if (photoURL !== undefined) updateData.photoURL = photoURL;
    if (disabled !== undefined) updateData.disabled = disabled;

    let updatedUser;
    if (Object.keys(updateData).length > 0) {
      updatedUser = await admin.auth().updateUser(uid, updateData);
    } else {
      updatedUser = currentUser;
    }

    // Update custom claims (roles) - PRESERVE EXISTING CLAIMS
    if (role !== undefined) {
      const newClaims = { ...existingClaims };
      
      if (role && role.trim()) {
        newClaims.role = role.trim();
      } else {
        newClaims.role = 'user';
      }
      
      console.log(`Setting custom claims for ${uid}:`, newClaims);
      await admin.auth().setCustomUserClaims(uid, newClaims);
    }

    // Fetch the fully updated user with new claims
    const refreshedUser = await admin.auth().getUser(uid);
    
    // Log for debugging
    console.log(`User ${uid} updated successfully. Claims:`, refreshedUser.customClaims);

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
    console.error(`Error updating user ${uid}:`, error);
    log(`Error updating user ${uid}: ${error.message}`);
    res.status(500).json({ error: 'Failed to update user', details: error.message });
  }
});

// Delete a user (Admin only)
app.delete('/api/auth/users/:uid', verifyFirebaseToken, async (req, res) => {
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

// Broker logs endpoint - Added from old version
app.get('/api/logs/broker', verifyFirebaseToken, requireAdmin, async (req, res) => {
  try {
    log('Getting broker logs');
    const logPath = '/var/log/mosquitto/mosquitto.log';

    if (!fs.existsSync(logPath)) {
      log(`Broker log file not found at ${logPath}`);
      return res.status(404).json({ error: 'Broker log file not found', logs: [] });
    }

    try {
      // Read the last 1000 lines of the log file
      const fileContent = fs.readFileSync(logPath, 'utf8');
      const lines = fileContent.toString().split('\n');
      const lastLines = lines.slice(-1000).filter(line => line.trim() !== '');

      // Parse each line to extract timestamp and message
      const logs = lastLines.map(line => {
        const logLine = line.toString().trim();
        if (!logLine) {
          return null;
        }

        // Try to extract timestamp from the Mosquitto log format
        // Example: 1709669577: New connection from 127.0.0.1:49816
        const parts = logLine.split(': ', 2);
        let timestamp = new Date().toISOString();
        let message = logLine;

        if (parts.length === 2) {
          try {
            // Convert Unix timestamp to ISO string if it's a number
            const unixTimestamp = parseInt(parts[0], 10);
            if (!isNaN(unixTimestamp)) {
              timestamp = new Date(unixTimestamp * 1000).toISOString();
              message = parts[1];
            }
          } catch (e) {
            // If parsing fails, keep the defaults
            log(`Error parsing timestamp: ${e.message}`);
          }
        }

        return {
          timestamp,
          message
        };
      }).filter(entry => entry !== null);

      res.json({ logs });
    } catch (readError) {
      log(`Error reading log file: ${readError.message}`);
      console.error(readError);
      res.status(500).json({ error: 'Error reading log file', logs: [] });
    }
  } catch (error) {
    log(`Error in broker logs endpoint: ${error.message}`);
    console.error(error);
    res.status(500).json({ error: 'Internal server error', logs: [] });
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