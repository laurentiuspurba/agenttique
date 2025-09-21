

import urllib.request

url = "http://34.73.19.6/"

try:
    with urllib.request.urlopen(url) as response:
        content = response.read().decode('utf-8')
        print(f"Successfully fetched content from {url}.\n")
        print("--- First 500 characters of the response ---")
        print(content[:500])
        print("---------------------------------------------")
except Exception as e:
    print(f"Error fetching content from {url}: {e}")

