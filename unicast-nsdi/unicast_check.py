#!/usr/bin/env python3
import re
import ipaddress

# --- Имя лога BIND (можно поменять под себя)
LOGFILE = "/var/log/named/query.log"

# --- Подсети НСДИ (AS41740 и смежные)
NSDI_NETS = [
    ipaddress.ip_network("193.232.147.0/24"),
    ipaddress.ip_network("193.232.253.0/24"),
    ipaddress.ip_network("195.208.4.0/24"),
    ipaddress.ip_network("195.208.5.0/24"),
    ipaddress.ip_network("195.208.6.0/24"),
    ipaddress.ip_network("195.208.7.0/24"),
    ipaddress.ip_network("193.223.132.0/24"),
]

# --- Регулярка для IP из строки лога BIND
LOG_RE = re.compile(r"client @\S+ (\S+)#")

def ip_in_nsdi(ip_str):
    """Проверяет, принадлежит ли IP подсетям НСДИ"""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in NSDI_NETS)
    except ValueError:
        return False

def filter_log():
    with open(LOGFILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = LOG_RE.search(line)
            if m:
                ip = m.group(1)
                if ip_in_nsdi(ip):
                    print(line.strip())

if __name__ == "__main__":
    filter_log()
