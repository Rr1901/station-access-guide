// Public settings for the browser. The Supabase publishable key is meant to be public:
// database security rules decide what it can do. Never put a secret or service-role key here.
export const CONFIG = {
  supabaseUrl: "https://uqocpkpaploskwavrppb.supabase.co",
  supabaseKey: "sb_publishable_XIxKv8rYg6K1VF6uq4_MXQ_6xG-HO69",
  // Switch on once the backend is set up (docs/phase-2-setup.md). While false, station pages
  // look exactly as before and nothing is sent to Supabase.
  visitorReports: false,
  contactEmail: "railclub.support@gmail.com",
};
