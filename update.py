import json
import re
import sys


ALLOWED_SECTIONS = {
    "recompilation",
}

SECTION_HEADER_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9 _/-]*?)\s*(?:\[[^\]]*\])?\s*:?\s*$"
)

SEPARATOR_LINE_RE = re.compile(r"^\s*[-=~_*]{3,}\s*$")

# Splits concatenated entries like "...win64.zipXenogears [1998]..." when needed
CONCATENATED_ENTRY_RE = re.compile(
    r"(\.(?:zip|7z|rar|tar\.gz|tgz|exe|msi))([A-Za-z0-9][^\[\r\n]*?\[)",
    re.IGNORECASE,
)

# Captures everything before the first '[' and an optional '[YYYY]' immediately after it
GAME_TITLE_AND_YEAR_RE = re.compile(
    r"^\s*(.+?)\s*(?:\[(\d{4})\])?(?:\s*\[|$)"
)

ANY_URL_RE = re.compile(r"https?://[^\s\]>]+", re.IGNORECASE)

GITHUB_REPO_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?=[/?#]|$)",
    re.IGNORECASE,
)


def normalize_section_name(raw_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", raw_name.lower())


def clean_section_title(raw_name: str) -> str:
    return re.sub(r"\s+", " ", (raw_name or "").strip())


def title_key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).lower()


def repo_key(owner: str, repo: str) -> tuple[str, str]:
    return (owner.lower(), repo.lower())


def normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def default_settings() -> dict:
    return {
        "token": "",
        "check_on_launch": False,
        "theme": "",
        "sort_col": "",
        "sort_asc": True,
    }


def unique_case_tweaked_target(
    owner: str, repo: str, used_urls: set[str]
) -> tuple[str, str, str]:
    """Return (owner, repo, html_url) by flipping the next letter on collision."""
    base_url = f"https://github.com/{owner}/{repo}"
    if base_url not in used_urls:
        used_urls.add(base_url)
        return owner, repo, base_url

    for i, ch in enumerate(owner):
        if ch.isalpha():
            new_owner = owner[:i] + ch.upper() + owner[i + 1 :]
            url = f"https://github.com/{new_owner}/{repo}"
            if url not in used_urls:
                used_urls.add(url)
                return new_owner, repo, url

    for i, ch in enumerate(repo):
        if ch.isalpha():
            new_repo = repo[:i] + ch.upper() + repo[i + 1 :]
            url = f"https://github.com/{owner}/{new_repo}"
            if url not in used_urls:
                used_urls.add(url)
                return owner, new_repo, url

    used_urls.add(base_url)
    return owner, repo, base_url


def make_project_entry(
    owner: str, repo: str, title: str, html_url: str | None = None
) -> dict:
    resolved_url = html_url or f"https://github.com/{owner}/{repo}"
    return {
        "owner": owner,
        "repo": repo,
        "title": title or repo,
        "description": "",
        "html_url": resolved_url,
        "include_prereleases": True,
        "fmt": 2,
        "latest": {
            "id": "",
            "tag": "",
            "name": "",
            "published_at": "",
            "url": "",
            "prerelease": False,
            "source": "",
        },
        "seen_id": "",
        "seen_tag": "",
        "last_checked": "",
        "error": None,
    }


def extract_game_title(entry_text: str, fallback: str = "") -> str:
    match = GAME_TITLE_AND_YEAR_RE.match(entry_text)
    if match:
        base_name = (match.group(1) or "").strip()
        year = (match.group(2) or "").strip()
        if base_name:
            return f"{base_name} [{year}]" if year else base_name
    return fallback


def split_concatenated_entries(line: str) -> list[str]:
    normalized = CONCATENATED_ENTRY_RE.sub(r"\1\n\2", line)
    return normalized.splitlines()


def load_game_locations(locations_path: str) -> dict[str, str]:
    """Maps normalized game title (with or without year) -> section/drive title."""
    game_to_section: dict[str, str] = {}
    current_section: str | None = None

    with open(locations_path, "r", encoding="utf-8") as f:
        text = f.read()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or SEPARATOR_LINE_RE.match(line):
            continue

        if "->" not in line and "http://" not in line and "https://" not in line:
            sec_match = SECTION_HEADER_RE.match(line)
            if sec_match:
                sec_title = clean_section_title(sec_match.group(1))
                if sec_title:
                    current_section = sec_title
                continue

        if not current_section:
            continue

        for chunk in split_concatenated_entries(line):
            game_name = extract_game_title(chunk, fallback="")
            if game_name:
                gk = title_key(game_name)
                if gk and gk not in game_to_section:
                    game_to_section[gk] = current_section

                base_only = re.sub(r"\s*\[\d{4}\]\s*$", "", game_name).strip()
                bk = title_key(base_only)
                if bk and bk not in game_to_section:
                    game_to_section[bk] = current_section

    return game_to_section


def format_titled_game_name(game_title: str, game_locations: dict[str, str]) -> str:
    prefix_section = game_locations.get(title_key(game_title))
    if not prefix_section:
        base_only = re.sub(r"\s*\[\d{4}\]\s*$", "", game_title).strip()
        prefix_section = game_locations.get(title_key(base_only))

    if not prefix_section:
        return game_title

    prefix = f"[{prefix_section}]"
    if game_title.lower().startswith(prefix.lower()):
        return game_title
    return f"{prefix} {game_title}"


def scan_recompilation_section(
    text: str,
    game_locations: dict[str, str] | None = None,
    deduplicate: bool = True,
    debug: bool = False,
    reserved_urls: set[str] | None = None,
) -> dict:
    locations = game_locations or {}
    unmatched_entries = []
    # Preserves first-seen order of base game title_key -> list of GitHub candidates
    candidates_by_title: dict[str, list[dict]] = {}

    in_recompilation = False

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or SEPARATOR_LINE_RE.match(line):
            continue

        if "->" not in line and "http://" not in line and "https://" not in line:
            sec_match = SECTION_HEADER_RE.match(line)
            if sec_match:
                norm_section = normalize_section_name(sec_match.group(1))
                in_recompilation = norm_section in ALLOWED_SECTIONS
                if debug:
                    print(
                        f"[DEBUG L{line_no}] Section '{sec_match.group(1)}' "
                        f"-> allowed={in_recompilation}"
                    )
                continue

        if not in_recompilation:
            continue

        for chunk in split_concatenated_entries(line):
            urls = [u.rstrip(".,;:") for u in ANY_URL_RE.findall(chunk)]
            gh_match = next(
                (GITHUB_REPO_RE.match(u) for u in urls if GITHUB_REPO_RE.match(u)),
                None,
            )

            raw_game_title = extract_game_title(chunk, fallback=chunk)
            display_title = format_titled_game_name(raw_game_title, locations)

            if not gh_match:
                first_link = urls[0] if urls else "(no link)"
                unmatched_entries.append((display_title, first_link))
                if debug:
                    print(f"[DEBUG L{line_no}] UNMATCHED: '{display_title}' -> {first_link}")
                continue

            owner = gh_match.group(1)
            repo = gh_match.group(2)
            matched_url = gh_match.group(0)
            title = format_titled_game_name(
                extract_game_title(chunk, fallback=repo), locations
            )
            tk = title_key(title)

            candidates_by_title.setdefault(tk, []).append(
                {
                    "line_no": line_no,
                    "title": title,
                    "owner": owner,
                    "repo": repo,
                    "repo_key": repo_key(owner, repo),
                    "url": matched_url,
                    "norm_url": normalize_url(matched_url),
                }
            )

    projects = []
    conflicting_github_games = []
    used_urls: set[str] = set(reserved_urls or ())

    for tk, occs in candidates_by_title.items():
        # Deduplicate identical GitHub target (repo_key + norm_url) for the same game
        distinct_occs = []
        seen_targets = set()
        for occ in occs:
            target = (occ["repo_key"], occ["norm_url"])
            if deduplicate and target in seen_targets:
                if debug:
                    print(
                        f"[DEBUG L{occ['line_no']}] DUPLICATE TARGET SKIPPED for '{occ['title']}': "
                        f"{occ['owner']}/{occ['repo']}"
                    )
                continue
            seen_targets.add(target)
            distinct_occs.append(occ)

        if not distinct_occs:
            continue

        if len(distinct_occs) > 1:
            part_entries = []
            for part_idx, occ in enumerate(distinct_occs, start=1):
                part_title = f"{occ['title']} [PART {part_idx}]"
                adj_owner, adj_repo, adj_url = unique_case_tweaked_target(
                    occ["owner"], occ["repo"], used_urls
                )
                projects.append(
                    make_project_entry(adj_owner, adj_repo, part_title, adj_url)
                )
                part_entries.append(
                    {
                        **occ,
                        "owner": adj_owner,
                        "repo": adj_repo,
                        "url": adj_url,
                        "part_number": part_idx,
                        "part_title": part_title,
                    }
                )
                if debug:
                    print(
                        f"[DEBUG L{occ['line_no']}] CONFLICT PART {part_idx}: "
                        f"'{part_title}' -> {adj_owner}/{adj_repo} ({adj_url})"
                    )

            conflicting_github_games.append(
                {
                    "title_key": tk,
                    "title": distinct_occs[0]["title"],
                    "occurrences": part_entries,
                }
            )
        else:
            only_occ = distinct_occs[0]
            adj_owner, adj_repo, adj_url = unique_case_tweaked_target(
                only_occ["owner"], only_occ["repo"], used_urls
            )
            projects.append(
                make_project_entry(adj_owner, adj_repo, only_occ["title"], adj_url)
            )
            if debug:
                print(
                    f"[DEBUG L{only_occ['line_no']}] MATCHED: "
                    f"'{only_occ['title']}' -> {adj_owner}/{adj_repo} ({adj_url})"
                )

    return {
        "projects": projects,
        "unmatched_entries": unmatched_entries,
        "conflicting_github_games": conflicting_github_games,
    }


def print_scan_report(scan_result: dict) -> None:
    unmatched = scan_result["unmatched_entries"]
    conflicts = scan_result.get("conflicting_github_games") or []

    print("\n--- Recompilation Scan Report ---")
    print(f"Matched GitHub projects: {len(scan_result['projects'])}")

    print(f"\nUnmatched ({len(unmatched)}):")
    if unmatched:
        for game_title, link in unmatched:
            print(f"  - {game_title} -> {link}")
    else:
        print("  (none)")

    print(f"\nConflicting GitHub links ({len(conflicts)}):")
    if conflicts:
        for item in conflicts:
            print(f"  - {item['title']} (split into {len(item['occurrences'])} parts)")
            for occ in item["occurrences"]:
                print(
                    f"      * [PART {occ['part_number']}] L{occ['line_no']}: "
                    f"{occ['owner']}/{occ['repo']} ({occ['url']})"
                )
    else:
        print("  (none)")


def load_existing_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at root of {path}")

    settings = data.get("settings")
    if not isinstance(settings, dict):
        settings = default_settings()

    projects = data.get("projects")
    if not isinstance(projects, list):
        projects = []

    return {"settings": settings, "projects": projects}


def _existing_urls(projects: list[dict]) -> set[str]:
    urls: set[str] = set()
    for p in projects:
        raw_url = (p.get("html_url") or "").strip().rstrip("/")
        if raw_url:
            urls.add(raw_url)
        elif p.get("owner") and p.get("repo"):
            urls.add(f"https://github.com/{p['owner']}/{p['repo']}")
    return urls


def plan_partial_update(
    existing_projects: list[dict], extracted_projects: list[dict]
) -> dict:
    extracted_by_title: dict[str, dict] = {}
    for proj in extracted_projects:
        tk = title_key(proj.get("title", ""))
        if tk and tk not in extracted_by_title:
            extracted_by_title[tk] = proj

    matched_title_keys = set()
    updated_projects = []
    removed_projects = []
    replaced_projects = []  # tuples of (old_proj, new_proj)

    kept_existing = []
    for proj in existing_projects:
        tk = title_key(proj.get("title", ""))
        if tk and tk in extracted_by_title:
            kept_existing.append((tk, proj))
        else:
            removed_projects.append(proj)

    used_urls = _existing_urls([p for _, p in kept_existing])

    for tk, proj in kept_existing:
        new_proj = extracted_by_title[tk]
        matched_title_keys.add(tk)

        old_rk = repo_key(proj.get("owner", ""), proj.get("repo", ""))
        new_rk = repo_key(new_proj.get("owner", ""), new_proj.get("repo", ""))
        old_url = normalize_url(proj.get("html_url") or "")
        new_url = normalize_url(new_proj.get("html_url") or "")

        entry = dict(proj)
        if old_rk != new_rk or old_url != new_url:
            entry["owner"] = new_proj["owner"]
            entry["repo"] = new_proj["repo"]
            entry["title"] = new_proj["title"]
            entry["html_url"] = new_proj["html_url"]
            replaced_projects.append((proj, entry))

        updated_projects.append(entry)

    added_projects = []
    for tk, proj in extracted_by_title.items():
        if tk not in matched_title_keys:
            adj_owner, adj_repo, adj_url = unique_case_tweaked_target(
                proj.get("owner", ""), proj.get("repo", ""), used_urls
            )
            added_entry = dict(proj)
            added_entry["owner"] = adj_owner
            added_entry["repo"] = adj_repo
            added_entry["html_url"] = adj_url
            added_projects.append(added_entry)

    updated_projects.extend(added_projects)

    return {
        "updated_projects": updated_projects,
        "added": added_projects,
        "removed": removed_projects,
        "replaced": replaced_projects,
    }


def confirm_write(output_path: str, plan: dict) -> bool:
    added = plan["added"]
    removed = plan["removed"]
    replaced = plan["replaced"]

    print(f"\nProposed changes for '{output_path}':")

    print(f"  + Add ({len(added)}):")
    for p in added:
        print(f"      {p.get('title')} ({p.get('owner')}/{p.get('repo')})")

    print(f"  - Remove ({len(removed)}):")
    for p in removed:
        print(f"      {p.get('title')} ({p.get('owner')}/{p.get('repo')})")

    print(f"  ~ Replace ({len(replaced)}):")
    for old_p, new_p in replaced:
        final_title = new_p.get("title") or old_p.get("title")
        print(
            f"      [{final_title}] "
            f"{old_p.get('owner')}/{old_p.get('repo')} -> {new_p.get('owner')}/{new_p.get('repo')}"
        )

    if not added and not removed and not replaced:
        print("\nNo changes detected.")
        return False

    while True:
        answer = (
            input(f"\nUpdate '{output_path}' with these changes? [y/N]: ")
            .strip()
            .lower()
        )
        if answer in ("y", "yes"):
            return True
        if answer in ("", "n", "no"):
            return False
        print("Please enter 'y' or 'n'.")


def write_config(output_path: str, config: dict) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def main() -> None:
    debug = "--debug" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--debug"]

    if len(args) < 1:
        print(
            "Usage: python Update.py <mods_file> [locations_file] [output_file] [--debug]",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = args[0]
    locations_path = None
    output_path = "projects.json"

    if len(args) == 2:
        if args[1].lower().endswith(".json"):
            output_path = args[1]
        else:
            locations_path = args[1]
    elif len(args) >= 3:
        locations_path = args[1]
        output_path = args[2]

    game_locations = load_game_locations(locations_path) if locations_path else {}

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    existing_config: dict | None = None
    try:
        existing_config = load_existing_config(output_path)
    except FileNotFoundError:
        existing_config = None
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Error reading existing '{output_path}': {exc}", file=sys.stderr)
        sys.exit(1)

    reserved = _existing_urls(existing_config["projects"]) if existing_config else set()

    scan_result = scan_recompilation_section(
        content,
        game_locations=game_locations,
        deduplicate=True,
        debug=debug,
        reserved_urls=reserved,
    )
    print_scan_report(scan_result)
    extracted_projects = scan_result["projects"]

    if existing_config is None:
        new_config = {
            "settings": default_settings(),
            "projects": extracted_projects,
        }
        write_config(output_path, new_config)
        print(f"\nCreated '{output_path}'.")
        print(f"Summary -> Added: {len(extracted_projects)}, Removed: 0, Replaced: 0")
        return

    plan = plan_partial_update(existing_config["projects"], extracted_projects)

    if not confirm_write(output_path, plan):
        print("Update cancelled. File was not modified.")
        return

    updated_config = {
        **existing_config,
        "projects": plan["updated_projects"],
    }
    write_config(output_path, updated_config)

    print(f"\nUpdated '{output_path}' (total projects: {len(plan['updated_projects'])}).")
    print(
        f"Summary -> Added: {len(plan['added'])}, "
        f"Removed: {len(plan['removed'])}, "
        f"Replaced: {len(plan['replaced'])}"
    )


if __name__ == "__main__":
    main()
