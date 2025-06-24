# test_supabase.py - Updated with authentication
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Get your credentials
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')  # Use service key instead of anon key

print(f"Testing connection to: {SUPABASE_URL}")

try:
    # Create client with service key (bypasses RLS)
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    
    # Test database connection
    response = supabase.table('rooms').select('name').execute()
    
    print("✅ Connection successful!")
    print(f"✅ Found {len(response.data)} rooms:")
    for room in response.data:
        print(f"   - {room['name']}")
    
    # Test other tables
    clients = supabase.table('clients').select('id').execute()
    addons = supabase.table('addons').select('id').execute()
    categories = supabase.table('addon_categories').select('id').execute()
    
    print(f"✅ Found {len(clients.data)} clients")
    print(f"✅ Found {len(addons.data)} add-ons") 
    print(f"✅ Found {len(categories.data)} categories")
        
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nCheck your .env file has the correct:")
    print("- SUPABASE_URL")
    print("- SUPABASE_SERVICE_KEY")