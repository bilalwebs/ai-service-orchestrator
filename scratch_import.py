import traceback
try:
    from routers.requests import router
    print("Success importing router!")
except Exception as e:
    print("Error importing router:")
    traceback.print_exc()
