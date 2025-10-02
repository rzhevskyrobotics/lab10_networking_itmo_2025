# app/asn_lookup.py
import asyncio, ipaddress, re
from typing import Optional, Dict

WHOIS_PORT = 43
CYMRU_HOST = "whois.cymru.com"
RADB_HOST  = "whois.radb.net"
TIMEOUT = 6.0

async def _whois(host: str, query: str) -> str:
    r, w = await asyncio.wait_for(asyncio.open_connection(host, WHOIS_PORT), TIMEOUT)
    try:
        w.write(query.encode()); await w.drain()
        data = await asyncio.wait_for(r.read(-1), TIMEOUT)
        return data.decode(errors="replace")
    finally:
        try: w.close(); await w.wait_closed()
        except Exception: pass

def _norm_ip(s: str) -> str:
    return str(ipaddress.ip_address(s))

async def cymru_one(ip: str) -> Dict:
    ip = _norm_ip(ip)
    # Bulk-режим с verbose: begin/verbose/end — корректнее для формата
    raw = await _whois(CYMRU_HOST, f"begin\nverbose\n{ip}\nend\n")
    # ожидаем строку вида: "AS | IP | BGP Prefix | CC | Registry | Allocated | AS Name"
    for line in raw.splitlines():
        if "|" not in line or line.lower().startswith("as |"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 7: continue
        asn = None
        try: asn = int(parts[0])
        except: pass
        return {
            "asn": asn,
            "ip": parts[1],
            "prefix": parts[2] or None,
            "as_name": parts[6] or None
        }
    return {}

async def radb_one(ip: str) -> Dict:
    ip = _norm_ip(ip)
    raw = await _whois(RADB_HOST, ip + "\n")
    # ищем блоки route/route6 и origin: ASxxxx, берём самый специфичный префикс
    route_re  = re.compile(r'^(route|route6):\s+([0-9a-fA-F\.:/]+)\s*$', re.I)
    origin_re = re.compile(r'^origin:\s+(AS\d+)\s*$', re.I)
    best = None
    for block in raw.split("\n\n"):
        route = origin = None
        for ln in block.splitlines():
            m = route_re.match(ln);  route  = m.group(2) if m else route
            m = origin_re.match(ln); origin = m.group(1) if m else origin
        if route and origin:
            try:
                net = ipaddress.ip_network(route, strict=False)
                cand = {"prefix": str(net), "asn": int(origin[2:])}
                if best is None or net.prefixlen > ipaddress.ip_network(best["prefix"]).prefixlen:
                    best = cand
            except: pass
    return best or {}

async def ip_to_asn(ip: str) -> Dict:
    ip = _norm_ip(ip)
    try:
        cymru = await cymru_one(ip)
    except Exception:
        cymru = {}
    if cymru.get("asn"):
        return {
            "ip": ip,
            "best": {"source": "cymru", "asn": cymru["asn"], "as_name": cymru.get("as_name"), "prefix": cymru.get("prefix")},
            "cymru": cymru, "radb": None
        }
    try:
        radb = await radb_one(ip)
    except Exception:
        radb = {}
    best = None
    if radb.get("asn"):
        best = {"source": "radb", "asn": radb["asn"], "as_name": None, "prefix": radb.get("prefix")}
    return {"ip": ip, "best": best, "cymru": cymru or None, "radb": radb or None}
