import httpx

def client(timeout=10.0, verify=True, follow_redirects=True):
    return httpx.Client(
        timeout=timeout, verify=verify, follow_redirects=follow_redirects
    )
