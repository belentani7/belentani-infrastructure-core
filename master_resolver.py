#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BELENTANI MASTER RESOLVER — un solo archivo, determinista y honesto.

Resuelve (audita → repara → indexa → publica) el ecosistema Belentani:
  - Universidades: secure-t-university, secure-t, ux-academy, open-school
  - Impacto social + idiomas: ManosAbiertas, manos-abiertas, lingua-aberta, linguaforge, Cruzando-el-charco
  - Enterprise/SaaS: saas-plasma, nexus-workforce, belentani-*experience
  - Motor central: belentani-unified

Principios (no negociables):
  1. NUNCA escribe contenido falso (sin "PRODUCTION READY" si no lo es).
  2. Dry-run por defecto: nada se modifica ni se pushea sin --apply.
  3. Solo añade archivos que FALTAN; nunca pisa lo existente.
  4. Solo hace push a repos con remote y con cambios reales.
  5. Idempotente: ejecutarlo N veces produce el mismo estado.

Uso:
  python master_resolver.py --help
  python master_resolver.py --dry-run                 # audita y reporta (por defecto)
  python master_resolver.py --apply --limit 20        # repara + commit (sin push)
  python master_resolver.py --apply --push            # repara + commit + push
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = Path.home()
INFRA_DIR = Path(__file__).resolve().parent
MASTER_DIR = HOME / "belentani-unified-master"
REPOS_DIR = MASTER_DIR / "repos"
OUTPUT_DIR = HOME / "Documents" / "BELENTANI-OS" / "09_REPORTES"

# ---- Dominios lógicos (fuente: REPO_UNIFICATION_MAP.md) -------------------
DOMAINS = [
    "BELENTANI-CORE", "PRODUCTS", "EXPERIMENTS", "SKILLS-INFRA", "JUDAS-ERA",
    "AION-WORKFORCE", "DUCK-ECOSYSTEM", "BOOKS-DOCS", "AI-COMPUTE",
    "VOICE-AI", "FORGE-OPS",
]

# ---- Familias + etiquetas (real: repos que existen en el ecosistema) ------
FAMILIES: dict[str, tuple[str, str]] = {
    # educación / universidades
    "secure-t-university": ("PRODUCTS", "Universidad ciberseguridad + IA"),
    "secure-t": ("PRODUCTS", "Seguridad + auditoría"),
    "ux-academy-professional-program": ("PRODUCTS", "UX Academy profesional"),
    "open-school": ("PRODUCTS", "Instituto educativo universal"),
    "lingua-aberta": ("PRODUCTS", "Lingua Aberta (PT/ES)"),
    "linguaforge": ("PRODUCTS", "Linguaforge"),
    # impacto social
    "ManosAbiertas": ("PRODUCTS", "Portal migrantes LGBT+"),
    "Cruzando-el-charco": ("PRODUCTS", "Acogida migrantes"),
    # enterprise / SaaS
    "saas-plasma": ("PRODUCTS", "SaaS Plasma"),
    "nexus-workforce-enterprise": ("AION-WORKFORCE", "Nexus Workforce"),
    "belentani-unified": ("BELENTANI-CORE", "Motor central eduforge"),
    "belentani-core": ("BELENTANI-CORE", "Backend core"),
}

# ---- Helpers --------------------------------------------------------------
def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           cwd=str(cwd) if cwd else None, timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return False, str(e)


# ---- Fuentes de repos -----------------------------------------------------
def github_repos(limit: int) -> list[dict]:
    """Devuelve los repos de belentani7 vía gh (parse JSON correcto, no por líneas)."""
    ok, out = sh(["gh", "repo", "list", "belentani7", "--limit", str(limit),
                  "--json", "name,url,visibility,isArchived,primaryLanguage,pushedAt"])
    if not ok:
        log(f"gh repo list falló: {out.strip()[:200]}")
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        log("gh no devolvió JSON válido")
        return []
    return [r for r in data if not r.get("isArchived")]


def local_repos() -> list[Path]:
    """Clones locales conocidos (bounded, sin recursión salvaje)."""
    roots = [
        HOME / "Documents", HOME / "Desktop", HOME,
    ]
    names = {
        "secure-t-university", "secure-t", "secure-t-platform", "lingua-aberta",
        "linguaforge", "noiacore-lab", "belentani-unified", "belentani-core",
        "belentani-v2", "belentani-judas-web", "belentani-the-judas-experience",
        "belentani-campaign-repo", "BELENTANI-OS", "BELENTANI_OS",
        "Belentani-Agency-AI-Omega", "belentani7-profile", "saas-plasma",
    }
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            cand = root / name
            if (cand / ".git").exists():
                found.append(cand)
    return found


# ---- Auditoría ------------------------------------------------------------
def audit_repo(path: Path) -> dict:
    name = path.name
    _, remote = sh(["git", "-C", str(path), "remote", "get-url", "origin"])
    _, dirty = sh(["git", "-C", str(path), "status", "--porcelain"])

    checks = {
        "README": (path / "README.md").exists(),
        "LICENSE": (path / "LICENSE").exists() or (path / "LICENSE.md").exists(),
        ".gitignore": (path / ".gitignore").exists(),
        "SECURITY": (path / "SECURITY.md").exists(),
        "CI": (path / ".github" / "workflows").exists(),
        "remote": bool(remote.strip()),
    }
    score = sum(20 for v in checks.values() if v)  # 6×20 = 120 -> cap 100
    score = min(score, 100)
    return {
        "name": name, "score": score, "remote": remote.strip(),
        "dirty_files": len([l for l in dirty.splitlines() if l.strip()]),
        "missing": [k for k, v in checks.items() if not v],
    }


# ---- Contenido honesto ----------------------------------------------------
_README = """# {name}

**{label}** · dominio **{domain}**

Parte del [Ecosistema Belentani]({index_url}).

## Acerca de
{label}.

## Desarrollo
```bash
git clone {url}
cd {name}
```

Ver `SECURITY.md` para reportar vulnerabilidades.

---
Índice generado por `master_resolver.py` ({ts}).
"""

_GITIGNORE_PY = """__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.env
*.log
build/
dist/
"""

_GITIGNORE_NODE = """node_modules/
.next/
dist/
build/
.env
.env.local
*.log
.DS_Store
"""

_SECURITY = """# Security Policy

## Reporte de vulnerabilidades

Reporta privadamente en https://github.com/{repo}/security/advisories/new

No publiques 0-days de forma pública.

## Versiones soportadas

| Rama | Soportada |
|------|-----------|
| main | Sí |
"""


def _detect_stack(path: Path) -> str:
    if (path / "package.json").exists():
        return "node"
    for pat in ("*.py", "requirements.txt", "pyproject.toml"):
        if list(path.glob(pat)):
            return "python"
    return "none"


def repair(path: Path, repo: dict, apply: bool, push: bool, owner: str) -> dict:
    """Añade SOLO lo que falta. Nunca pisa archivos existentes."""
    name = repo["name"]
    domain, label = FAMILIES.get(name, ("BELENTANI-CORE", "Proyecto Belentani"))
    index_url = f"https://github.com/{owner}/belentani-infrastructure-core/blob/main/ECOSYSTEM.md"
    changes: list[str] = []

    readme = path / "README.md"
    if not readme.exists():
        changes.append("README.md")
    gitignore = path / ".gitignore"
    if not gitignore.exists():
        changes.append(".gitignore")
    sec = path / "SECURITY.md"
    if not sec.exists():
        changes.append("SECURITY.md")

    if not changes:
        return {"name": name, "changes": [], "committed": False, "pushed": False}

    result: dict = {"name": name, "changes": changes, "committed": False, "pushed": False}
    if not apply:  # dry-run: solo reporta lo que cambiaría, no escribe nada
        return result

    if "README.md" in changes:
        readme.write_text(_README.format(
            name=name, label=label, domain=domain, index_url=index_url,
            url=repo["remote"] or f"https://github.com/{owner}/{name}",
            ts=datetime.now().isoformat(timespec="seconds")), encoding="utf-8")
    if ".gitignore" in changes:
        stack = _detect_stack(path)
        text = _GITIGNORE_NODE if stack == "node" else _GITIGNORE_PY
        (path / ".gitignore").write_text(text, encoding="utf-8")
    if "SECURITY.md" in changes:
        sec.write_text(_SECURITY.format(repo=f"{owner}/{name}"), encoding="utf-8")

    if repo["remote"]:
        ok, _ = sh(["git", "-C", str(path), "add"] + changes)
        ok2, _ = sh(["git", "-C", str(path), "commit", "-m",
                     "chore(resolver): añadir " + ", ".join(changes)])
        result["committed"] = bool(ok and ok2)
        if result["committed"] and push:
            result["pushed"], _ = sh(["git", "-C", str(path), "push", "origin", "HEAD"])
    return result


# ---- Índice interconectado ------------------------------------------------
def build_index(results: list[dict], owner: str, write: bool = False) -> Path:
    """Genera ECOSYSTEM.md que interconecta todas las familias."""
    by_domain: dict[str, list[dict]] = {}
    for r in results:
        domain, _label = FAMILIES.get(r["name"], ("BELENTANI-CORE", "Proyecto"))
        by_domain.setdefault(domain, []).append(r)

    lines = ["# Ecosistema Belentani — índice interconectado", "",
             f"Generado por `master_resolver.py` · {datetime.now().isoformat(timespec='seconds')}",
             ""]
    for domain in DOMAINS:
        repos = by_domain.get(domain, [])
        if not repos:
            continue
        lines.append(f"## {domain} ({len(repos)})")
        for r in repos:
            label = FAMILIES.get(r["name"], ("", "Proyecto"))[1]
            url = r["remote"] or f"https://github.com/{owner}/{r['name']}"
            lines.append(f"- [{r['name']}]({url}) — {label} · score {r['score']}/100")
        lines.append("")
    out = INFRA_DIR / "ECOSYSTEM.md"
    if write:
        out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---- Main ----------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Belentani Master Resolver (un archivo)")
    ap.add_argument("--local", action="store_true", help="solo clones locales (sin gh/red)")
    ap.add_argument("--limit", type=int, default=100, help="máx repos de gh")
    ap.add_argument("--apply", action="store_true", help="escribir + commit (sin esto: dry-run)")
    ap.add_argument("--push", action="store_true", help="push tras commit (requiere --apply)")
    ap.add_argument("--owner", default="belentani7", help="cuenta GitHub")
    ap.add_argument("--json", action="store_true", help="reporte JSON en vez de texto")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.local:
        src = local_repos()
        repos = [{"name": p.name, "url": "", "visibility": "PRIVATE",
                  "isArchived": False, "primaryLanguage": None,
                  "pushedAt": None, "_local": p} for p in src]
    else:
        repos = github_repos(args.limit)

    if not repos:
        log("0 repos encontrados. Usa --local si gh no está autenticado.")
        return 2

    log(f"Auditando {len(repos)} repos ({'local' if args.local else 'gh'})"
        + (" [dry-run]" if not args.apply else " [apply]" + (" + push" if args.push else "")))

    results: list[dict] = []
    for i, repo in enumerate(repos, 1):
        name = repo["name"]
        if args.local:
            path = repo["_local"]
            audit = audit_repo(path)
        else:
            # solo remote: no clonamos por defecto; se auditan clonadas
            repodir = REPOS_DIR / name
            if not (repodir / ".git").exists():
                continue
            audit = audit_repo(repodir)
            path = repodir
        outcome = repair(path, audit, apply=args.apply, push=args.push, owner=args.owner)
        merged = {**audit, **outcome}
        results.append(merged)
        msg = f"[{i:3}/{len(repos)}] {name:<32} score={audit['score']:>3}/100"
        if audit["missing"]:
            msg += f"  faltan={audit['missing']}"
        log(msg)

    report = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "perfect": sum(1 for r in results if r["score"] == 100),
        "repaired": sum(1 for r in results if r.get("changes")),
        "pushed": sum(1 for r in results if r.get("pushed")),
        "repos": results,
    }
    idx = build_index(results, args.owner, write=args.apply)

    if args.json:
        rf = OUTPUT_DIR / f"resolver_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        rf.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Reporte: {rf}")
        return 0

    print("\n=== RESUMEN ===")
    print(f"Repos auditados : {report['total']}")
    print(f"Perfectos (100) : {report['perfect']}")
    print(f"Reparados       : {report['repaired']}")
    print(f"Pusheados       : {report['pushed']}")
    print(f"Índice          : {idx}")
    print("(dry-run: nada se escribió ni pusheó; usa --apply para materializar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())