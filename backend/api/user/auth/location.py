"""IP-to-location lookup for labelling user sessions."""
import httpx


async def get_location(ip: str) -> str:
    """Resolve an IP address to a human-readable "City, Country" string.

    Treats loopback/private addresses as a local network and returns a fallback
    label when the lookup fails or times out.
    """
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
