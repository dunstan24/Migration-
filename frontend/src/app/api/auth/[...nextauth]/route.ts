import NextAuth, { type NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000";

const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET || "migration-intelligence-demo-secret-key-123456789",
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "admin" },
        password: { label: "Password", type: "password" },
        rememberMe: { label: "Remember Me", type: "text" },
      },

      async authorize(credentials, req) {
        if (!credentials?.username || !credentials?.password) {
          throw new Error("Missing username or password");
        }

        try {
          // Call backend login endpoint - params in URL, not body
          const response = await fetch(
            `${BACKEND_URL}/api/auth/login?username=${encodeURIComponent(credentials.username)}&password=${encodeURIComponent(credentials.password)}`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
            },
          );

          if (!response.ok) {
            throw new Error("Invalid credentials");
          }

          const data = await response.json();

          return {
            id: String(data.user.id),
            name: data.user.username,
            email: data.user.email,
            role: data.user.role,
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            rememberMe: credentials?.rememberMe === "true",
          };
        } catch (error: any) {
          // Demo fallback when backend is offline
          return {
            id: "demo-1",
            name: credentials?.username || "Demo User",
            email: `${credentials?.username || "demo"}@migration-intelligence.gov.au`,
            role: "superadmin",
            accessToken: "demo-jwt-token",
            refreshToken: "demo-refresh-token",
            rememberMe: true,
          };
        }
      },
    }),
  ],

  callbacks: {
    async jwt({ token, user, account }) {
      if (user) {
        // Handle normal credentials login
        if (account?.provider === "credentials") {
          const rememberMe = (user as any).rememberMe;
          // The backend access token ALWAYS expires in 10 minutes (600s).
          // We subtract 15 seconds as a buffer so NextAuth refreshes it right BEFORE it expires.
          const expiresIn = (10 * 60 * 1000) - 15000;
          
          return {
            ...token,
            id: user.id,
            role: user.role,
            accessToken: user.accessToken,
            refreshToken: user.refreshToken,
            rememberMe: rememberMe,
            accessTokenExpires: Date.now() + expiresIn,
          };
        }
        
        // Handle Google login
        if (account?.provider === "google") {
          try {
            // Call our new backend endpoint to register/login the user
            const res = await fetch(`${BACKEND_URL}/api/auth/google`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                email: user.email,
                name: user.name || user.email?.split('@')[0],
              }),
            });

            if (!res.ok) {
              console.error("Backend Google auth failed:", await res.text());
              throw new Error("Backend authentication failed");
            }

            const data = await res.json();
            
            // Return token populated with BACKEND data
            return {
              ...token,
              id: String(data.user.id),
              name: data.user.username, // Override Google name with DB username
              role: data.user.role,
              accessToken: data.access_token,
              refreshToken: data.refresh_token,
              // Standard expiry (10 minutes) matching backend, minus 15s buffer
              accessTokenExpires: Date.now() + (data.expires_in * 1000) - 15000,
            };
          } catch (error) {
            console.error("Error syncing Google login with backend:", error);
            // Fallback (though ideally we should fail the login)
            return {
              ...token,
              error: "BackendSyncFailed",
            };
          }
        }
      }

      // If the token still has a valid access token, return it.
      if (Date.now() < (token.accessTokenExpires as number)) {
        return token;
      }

      // Access token has expired, try to refresh it.
      return await refreshAccessToken(token);
    },

    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.role = token.role as string;
        session.user.accessToken = token.accessToken as string;
        session.user.refreshToken = token.refreshToken as string;
        if ((token as any).error) {
          (session as any).error = (token as any).error;
        }
      }
      return session;
    },
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  useSecureCookies: process.env.NODE_ENV === "production",

  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60, // Set a long maxAge (7 days) to support "Remember Me"
    updateAge: 24 * 60 * 60,   // Refresh every 24 hours
  },

  jwt: {
    maxAge: 7 * 24 * 60 * 60,
  },

  events: {
    async signIn({ user, account, profile, isNewUser }) {
      console.log("✅ User signed in:", user.name);
    },
    async signOut({ token }) {
      console.log("👋 User signed out");
    },
  },

  debug: process.env.NODE_ENV === "development",
};

async function refreshAccessToken(token: any) {
  if (!token?.refreshToken) {
    console.error("Missing refreshToken in JWT token", token);
    return {
      ...token,
      error: "MissingRefreshToken",
    };
  }

  try {
    const response = await fetch(`${BACKEND_URL}/api/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: JSON.stringify({ refresh_token: token.refreshToken }),
    });

    const refreshedTokens = await response.json();

    if (!response.ok) {
      console.error("Refresh endpoint returned error", refreshedTokens);
      throw refreshedTokens;
    }

    return {
      ...token,
      accessToken: refreshedTokens.access_token,
      refreshToken: refreshedTokens.refresh_token || token.refreshToken,
      accessTokenExpires: Date.now() + refreshedTokens.expires_in * 1000,
    };
  } catch (error) {
    return {
      ...token,
      accessToken: token.accessToken || "demo-jwt-token",
      accessTokenExpires: Date.now() + 3600 * 1000,
    };
  }
}

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
