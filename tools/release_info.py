"""Release helper used by build.bat (standard library only).

    python tools/release_info.py version              print APP_VERSION (checks it looks like 1.2.3)
    python tools/release_info.py notes <path-to-exe> [--run-url URL]
                                                      write release-notes-vX.Y.Z.md next to the exe with the
                                                      SHA-256 and this version's section from CHANGELOG.md.
                                                      With --run-url (used by the GitHub workflow) the notes say
                                                      the exe was built by GitHub Actions and link to that run.
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "github_release_tracker.py")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")


def read_version():
    with open(SOURCE, "r", encoding="utf-8") as f:
        m = re.search(r'^APP_VERSION\s*=\s*"([^"]*)"', f.read(), re.M)
    if not m:
        sys.exit("ERROR: APP_VERSION not found in github_release_tracker.py")
    version = m.group(1)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit('ERROR: APP_VERSION is "%s" but must look like 1.2.3 (digits and dots only).' % version)
    return version


def changelog_section(version):
    """The text under '## [version]' in CHANGELOG.md, or '' if there is none."""
    try:
        with open(CHANGELOG, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    m = re.search(r"^##\s*\[?v?%s\]?[^\n]*\n(.*?)(?=^##\s|\Z)" % re.escape(version), text, re.M | re.S)
    return m.group(1).strip() if m else ""


def built_by(run_url):
    if run_url:
        return ("This `.exe` was built by GitHub Actions (the \"Build Windows exe\" workflow) on a GitHub-hosted Windows machine "
                "from the source in this repository. Public build log of this exact run: %s" % run_url)
    return "This `.exe` was built by the author on their own PC with `build.bat` from the source in this repository."


def write_notes(exe, run_url=None):
    version = read_version()
    if not os.path.isfile(exe):
        sys.exit("ERROR: %s not found" % exe)
    digest = hashlib.sha256(open(exe, "rb").read()).hexdigest()
    size = os.path.getsize(exe)
    changes = changelog_section(version)
    out = os.path.join(os.path.dirname(os.path.abspath(exe)), "release-notes-v%s.md" % version)
    body = ["## GitHub Release Tracker v%s" % version, ""]
    body.append(changes if changes else "_(Describe what changed in this release. Tip: add a `## [%s]` section to CHANGELOG.md and it appears here next time.)_" % version)
    body += ["",
             "### Verify your download",
             "",
             "SHA-256 of `GitHubReleaseTracker.exe` (%d bytes):" % size,
             "",
             "```",
             digest,
             "```",
             "",
             "In PowerShell: `Get-FileHash .\\GitHubReleaseTracker.exe -Algorithm SHA256`",
             "",
             built_by(run_url),
             ""]
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(body))
    print(digest)
    print(out)


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "version":
        print(read_version())
    elif len(sys.argv) in (3, 5) and sys.argv[1] == "notes":
        url = None
        if len(sys.argv) == 5:
            if sys.argv[3] != "--run-url" or not sys.argv[4].startswith("https://github.com/"):
                sys.exit("ERROR: --run-url must be followed by an https://github.com/ link")
            url = sys.argv[4]
        write_notes(sys.argv[2], url)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
