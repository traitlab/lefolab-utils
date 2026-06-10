"""
check_sftp_sync.py
Vérifie que les dossiers locaux YYYYMMDD_site_sensor sont bien présents sur le serveur SFTP,
avec tous leurs fichiers/sous-dossiers et les mêmes tailles.
"""

import os
import re
import paramiko
import getpass
from pathlib import Path
from collections import defaultdict

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
LOCAL_ROOT   = r"G:\LEFO\2024_BCI\lefodata"   # ← à modifier
REMOTE_ROOT  = "/data/drone_missions"             # ← à modifier si besoin
SFTP_HOST    = "lefodata-irbv.irbv.umontreal.ca"                 # ← à modifier
SFTP_PORT    = 22
SFTP_USER    = "acaronguay"                         # ← à modifier
# ──────────────────────────────────────────────────────────────────────────────

FOLDER_PATTERN = re.compile(r"^\d{8}_.+_.+$")


def get_local_tree(folder_path: Path) -> dict[str, int]:
    """Retourne {chemin_relatif: taille} pour tous les fichiers sous folder_path."""
    tree = {}
    for root, _, files in os.walk(folder_path):
        for f in files:
            full = Path(root) / f
            rel  = full.relative_to(folder_path).as_posix()
            tree[rel] = full.stat().st_size
    return tree


def get_remote_tree(sftp, remote_path: str) -> dict[str, int]:
    """Retourne {chemin_relatif: taille} pour tous les fichiers sous remote_path via SFTP."""
    tree = {}

    def walk(path, prefix=""):
        try:
            entries = sftp.listdir_attr(path)
        except FileNotFoundError:
            return
        for entry in entries:
            rel  = f"{prefix}{entry.filename}" if not prefix else f"{prefix}/{entry.filename}"
            full = f"{path}/{entry.filename}"
            import stat
            if stat.S_ISDIR(entry.st_mode):
                walk(full, rel)
            else:
                tree[rel] = entry.st_size

    walk(remote_path)
    return tree


def compare(local_tree: dict, remote_tree: dict) -> dict:
    """Compare deux arbres et retourne les différences."""
    local_files  = set(local_tree.keys())
    remote_files = set(remote_tree.keys())

    missing_on_remote = local_files - remote_files
    extra_on_remote   = remote_files - local_files
    size_mismatch     = {
        f for f in local_files & remote_files
        if local_tree[f] != remote_tree[f]
    }

    return {
        "missing":  sorted(missing_on_remote),
        "extra":    sorted(extra_on_remote),
        "mismatch": sorted(size_mismatch),
    }


def format_size(n: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"


def main():
    local_root = Path(LOCAL_ROOT)

    # Trouver les dossiers mission locaux
    missions = sorted([
        d for d in local_root.iterdir()
        if d.is_dir() and FOLDER_PATTERN.match(d.name)
    ])

    if not missions:
        print("Aucun dossier mission trouvé dans", LOCAL_ROOT)
        return

    print(f"{len(missions)} dossier(s) mission trouvé(s) localement.\n")

    password = getpass.getpass(f"Mot de passe SFTP pour {SFTP_USER}@{SFTP_HOST} : ")

    # Connexion SFTP
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SFTP_HOST, port=SFTP_PORT, username=SFTP_USER, password=password)
    sftp = ssh.open_sftp()
    print("Connecté au serveur SFTP.\n")

    summary = defaultdict(list)

    for mission in missions:
        year        = mission.name[:4]
        remote_path = f"{REMOTE_ROOT}/{year}/{mission.name}"

        print(f"── {mission.name}")

        # Vérifier l'existence du dossier distant
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            print(f"   ✗ DOSSIER ABSENT sur le serveur ({remote_path})\n")
            summary["absent"].append(mission.name)
            continue

        local_tree  = get_local_tree(mission)
        remote_tree = get_remote_tree(sftp, remote_path)
        diff        = compare(local_tree, remote_tree)

        has_issues = any(diff.values())

        if not has_issues:
            print(f"   ✓ OK — {len(local_tree)} fichier(s), tailles identiques\n")
            summary["ok"].append(mission.name)
        else:
            summary["issues"].append(mission.name)

            if diff["missing"]:
                print(f"   ✗ Fichiers manquants sur le serveur ({len(diff['missing'])}) :")
                for f in diff["missing"]:
                    print(f"      - {f}  ({format_size(local_tree[f])})")

            if diff["mismatch"]:
                print(f"   ⚠ Tailles différentes ({len(diff['mismatch'])}) :")
                for f in diff["mismatch"]:
                    print(f"      - {f}  local={format_size(local_tree[f])}  "
                          f"distant={format_size(remote_tree[f])}")

            if diff["extra"]:
                print(f"   ℹ Fichiers supplémentaires sur le serveur ({len(diff['extra'])}) :")
                for f in diff["extra"]:
                    print(f"      - {f}")
            print()

    sftp.close()
    ssh.close()

    # Résumé final
    print("═" * 50)
    print("RÉSUMÉ")
    print(f"  ✓ OK         : {len(summary['ok'])}")
    print(f"  ✗ Absent     : {len(summary['absent'])}")
    print(f"  ⚠ Différences: {len(summary['issues'])}")
    if summary["absent"]:
        print("\nDossiers absents :", ", ".join(summary["absent"]))
    if summary["issues"]:
        print("Dossiers avec différences :", ", ".join(summary["issues"]))


if __name__ == "__main__":
    main()
