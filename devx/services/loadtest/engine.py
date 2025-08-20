import asyncio
import time
import httpx

async def run_load(url, rps, duration, method, timeout, headers, body, verify_ssl):
    async with httpx.AsyncClient(
        timeout=timeout, verify=verify_ssl, follow_redirects=True
    ) as client:
        latencies, codes, errors = [], [], 0
        start = time.perf_counter()
        for sec in range(duration):
            t0 = time.perf_counter()
            tasks = [
                client.request(
                    method,
                    url,
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    content=None if isinstance(body, dict) else body,
                )
                for _ in range(rps)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    errors += 1
                else:
                    codes.append(r.status_code)
                    latencies.append(time.perf_counter() - t0)
            sleep = (sec + 1) - (time.perf_counter() - start)
            if sleep > 0:
                await asyncio.sleep(sleep)
        return latencies, codes, errors
