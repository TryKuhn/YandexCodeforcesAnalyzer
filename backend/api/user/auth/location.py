import httpx


async def get_location(ip: str) -> str:
    if ip in ("127.0.0.1", "localhost", "testclient") or ip.startswith("172."):
        return "Локальная сеть"

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(
                f"https://ip-api.com/json/{ip}?fields=status,country,city"
            )
            data = response.json()
            if data.get("status") == "success":
                return f"{data.get('city')}, {data.get('country')}"
    except Exception:
        pass
    return "Неизвестное местоположение"
