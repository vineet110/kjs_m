// Firebase Authentication in the browser: it checks staff passwords and sends the "verify your email" and
// "reset your password" emails. After signing in, the page sends the ID token (a short, signed proof of who
// it is) to our API, which starts the normal session (kjs_session). We then sign out of Firebase in this
// browser: the API's session is the only login that lasts, so logging out stays one step.
// Only for 'use client' pages (Firebase runs in the browser).
import { FirebaseError, getApps, initializeApp } from 'firebase/app';
import { getAuth, signOut, type Auth } from 'firebase/auth';

// The web app's settings from the Firebase console (Project settings > General > Your apps). They are
// public by design (every visitor's browser gets them); what protects accounts is Firebase itself, plus
// "Authorized domains" in the console. NEXT_PUBLIC_FIREBASE_* can point at another project (e.g. a test one).
const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || 'AIzaSyDsfGtTwtgeX6U1aIZDr-Iq03x8kyp80zc',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || 'kjs-m-6e0bb.firebaseapp.com',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'kjs-m-6e0bb',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '1:1088274331644:web:3f20b57584e17f1e016479',
};

export function firebaseAuth(): Auth {
  return getAuth(getApps()[0] ?? initializeApp(config));
}

/** Leaves Firebase in this browser (the API session is separate). Never throws. */
export async function leaveFirebase() {
  await signOut(firebaseAuth()).catch(() => undefined);
}

/** Where the links in Firebase's emails send people back to, after verifying or resetting. */
export function backToLogin() {
  return { url: `${window.location.origin}/employee/login` };
}

/** Firebase said "wrong email or password" (it doesn't say which, so nobody can probe who has an account). */
export function isWrongPassword(err: unknown): boolean {
  return err instanceof FirebaseError
    && ['auth/invalid-credential', 'auth/wrong-password', 'auth/user-not-found', 'auth/invalid-email'].includes(err.code);
}

/** Accounts from before Firebase (13 Nov 2026) have no Firebase login yet: their old password fails there. */
export const OLD_ACCOUNT_HINT =
  'Had a staff account before 13 Nov 2026? Use "Sign up" once with the same email to move it to the new login (an admin approves it again).';

/** A plain sentence for a Firebase error (its own messages are technical). */
export function firebaseMessage(err: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (!(err instanceof FirebaseError)) return fallback;
  switch (err.code) {
    case 'auth/invalid-credential':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
    case 'auth/invalid-email':
      return 'Email or password is wrong.';
    case 'auth/too-many-requests':
      return 'Too many tries. Please wait a few minutes, or reset your password.';
    case 'auth/network-request-failed':
      return 'Could not reach the login service. Please check your internet and try again.';
    case 'auth/weak-password':
    case 'auth/password-does-not-meet-requirements':
      return 'Please choose a stronger password (at least 10 characters).';
    case 'auth/user-disabled':
      return 'Your account is disabled. Please contact the admin.';
    case 'auth/email-already-in-use':
      return 'An account with this email already exists. Please log in, or use "Forgot password?".';
    case 'auth/operation-not-allowed':
      return 'Email login is not switched on yet. Please tell the admin (Firebase > Authentication > Sign-in method).';
    case 'auth/unauthorized-continue-uri':
    case 'auth/unauthorized-domain':
      return 'This website is not allowed in Firebase yet. Please tell the admin (Authentication > Settings > Authorized domains).';
    default:
      return fallback;
  }
}
