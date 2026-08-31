#!/usr/bin/env python3
"""
One-command setup and run script.
This script will:
1. Check if refresh token exists
2. If not, get one using device flow
3. Save it to .env file
4. Run the transfer
"""

import os
import globus_sdk
import time
from dotenv import load_dotenv, set_key

def setup_and_run():
    """Setup authentication and run transfer in one command"""
    
    # Load current .env
    load_dotenv(".env")
    
    GLOBUS_CLIENT_ID = os.getenv("GLOBUS_CLIENT_ID", "cf15eb47-ac2b-442a-9dfa-d9fe4d91cf98")
    GLOBUS_REFRESH_TOKEN = os.getenv("GLOBUS_REFRESH_TOKEN", "")
    
    # Check if we already have a refresh token
    if GLOBUS_REFRESH_TOKEN:
        print("✅ Refresh token found. Running transfer...")
        os.system("python to_dfdr_headless.py")
        return
    
    print("🔐 No refresh token found. Setting up authentication...")
    
    # Get refresh token using device flow
    client = globus_sdk.NativeAppAuthClient(GLOBUS_CLIENT_ID)
    
    try:
        # Start device flow
        flow = client.oauth2_device_flow(requested_scopes=[
            "openid",
            "profile", 
            "email",
            "urn:globus:auth:scope:auth.globus.org:view_identity_set",
            "urn:globus:auth:scope:transfer.api.globus.org:all",
            "urn:globus:auth:scope:groups.api.globus.org:all",
            "urn:globus:auth:scope:search.api.globus.org:all"
        ])
        
        print(f"🌐 Please visit: {flow['verification_uri']}")
        print(f"🔑 And enter code: {flow['user_code']}")
        print("⏳ Waiting for authorization...")
        
        # Poll for completion
        while True:
            try:
                token_response = client.oauth2_device_flow_wait(flow)
                break
            except globus_sdk.AuthAPIError as e:
                if e.code == "authorization_pending":
                    time.sleep(5)  # Wait 5 seconds before trying again
                    continue
                else:
                    raise
        
        # Get refresh token
        if "transfer.api.globus.org" not in token_response.by_resource_server:
            raise Exception("Transfer API tokens not received")
        
        tokens = token_response.by_resource_server["transfer.api.globus.org"]
        refresh_token = tokens["refresh_token"]
        
        # Save refresh token to .env file
        set_key(".env", "GLOBUS_REFRESH_TOKEN", refresh_token)
        print("✅ Refresh token saved to .env file")
        
        # Run the transfer
        print("🚀 Running transfer...")
        os.system("python to_dfdr_headless.py")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPlease try again or run 'python get_refresh_token.py' manually")

if __name__ == "__main__":
    setup_and_run()
