#!/usr/bin/env python3
"""
Helper script to get a refresh token for non-interactive authentication.
Run this once to get a refresh token, then add it to your .env file.
"""

import os
import globus_sdk
from dotenv import load_dotenv

# Load environment variables
load_dotenv("globus/.env")

GLOBUS_CLIENT_ID = os.getenv("GLOBUS_CLIENT_ID", "cf15eb47-ac2b-442a-9dfa-d9fe4d91cf98")

def get_refresh_token():
    """Get a refresh token for non-interactive authentication"""
    print("Getting refresh token for non-interactive authentication...")
    print(f"Using client ID: {GLOBUS_CLIENT_ID}")
    
    # Create client
    client = globus_sdk.NativeAppAuthClient(GLOBUS_CLIENT_ID)
    
    # Start OAuth flow with refresh tokens enabled
    client.oauth2_start_flow(requested_scopes=[
        "openid",
        "profile", 
        "email",
        "urn:globus:auth:scope:auth.globus.org:view_identity_set",
        "urn:globus:auth:scope:transfer.api.globus.org:all",
        "urn:globus:auth:scope:groups.api.globus.org:all",
        "urn:globus:auth:scope:search.api.globus.org:all"
    ])
    
    # Get authorization URL
    authorize_url = client.oauth2_get_authorize_url()
    print(f"\nPlease go to this URL in your browser:")
    print(f"{authorize_url}")
    print("\nAfter authorizing, you'll get an authorization code.")
    
    # Get authorization code from user
    auth_code = input("Enter the authorization code: ").strip()
    
    if not auth_code:
        print("No authorization code provided. Exiting.")
        return None
    
    try:
        # Exchange code for tokens
        print("Exchanging authorization code for tokens...")
        token_response = client.oauth2_exchange_code_for_tokens(auth_code)
        
        # Check if we got transfer tokens
        if "transfer.api.globus.org" not in token_response.by_resource_server:
            print("Error: Transfer API tokens not received.")
            return None
        
        tokens = token_response.by_resource_server["transfer.api.globus.org"]
        refresh_token = tokens["refresh_token"]
        
        print(f"\n✅ Success! Here's your refresh token:")
        print(f"GLOBUS_REFRESH_TOKEN={refresh_token}")
        print(f"\nAdd this line to your .env file to enable non-interactive authentication.")
        
        return refresh_token
        
    except Exception as e:
        print(f"Error getting refresh token: {e}")
        return None

if __name__ == "__main__":
    get_refresh_token()
