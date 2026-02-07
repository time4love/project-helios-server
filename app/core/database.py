import os
from supabase import create_client, Client

# Supabase configuration from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")  # Use the service_role key for server-side

# Create Supabase client (uses REST API over HTTPS)
supabase: Client | None = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_supabase() -> Client:
    """
    Dependency that provides the Supabase client.
    Raises error if not configured.
    """
    if supabase is None:
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY environment variables."
        )
    return supabase
