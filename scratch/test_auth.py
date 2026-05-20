import requests

BASE_URL = "http://127.0.0.1:8000"

def test_auth():
    print("1. Registering user...")
    res = requests.post(f"{BASE_URL}/register", json={
        "name": "Test User",
        "email": "test@test.com",
        "password": "password123"
    })
    print("Register Response:", res.status_code, res.json())

    print("\n2. Logging in...")
    res = requests.post(f"{BASE_URL}/token", data={
        "username": "test@test.com",
        "password": "password123"
    })
    print("Login Response:", res.status_code, res.json())
    
    if res.status_code != 200:
        return
        
    token = res.json().get("access_token")
    
    print("\n3. Accessing profile...")
    res = requests.get(f"{BASE_URL}/profile", headers={
        "Authorization": f"Bearer {token}"
    })
    print("Profile Response:", res.status_code, res.json())

if __name__ == "__main__":
    test_auth()
