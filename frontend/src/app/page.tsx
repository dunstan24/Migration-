import { redirect } from "next/navigation";

/**
 * Root page component that automatically redirects to the dashboard.
 * This complements the next.config.js redirect for a seamless experience.
 */
export default function RootPage() {
  redirect("/dashboard");
}
