# Changelog

## [1.2.0]
- Double-click a project **name** to rename it (same as the pencil). Double-clicking any other column still opens the release page.
- "Mark as seen" now has a checkbox icon.
- The dark / light button moved to the bottom right (icon only). The status bar says "Dark mode." or "Light mode." when you switch.
- Resizing the window does less work: the row lines are no longer re-placed when only the width changes, and the separator lines are redrawn once after a burst of resize events. (Not benchmarked on Windows; please report if the list still feels slow.)
- Brought in line with the Rust edition 2.0.0 (<https://github.com/santosasarno-code/github-release-tracker-rs>); both read and write the same `projects.json`.

## [1.1.1]
- Thin separator lines between columns, in the same colour as the row lines.
- Column headers are left-aligned and bold.
- The horizontal scrollbar only appears when the columns do not fit; the vertical one stays visible.
- Fix: making a column narrower no longer leaves an empty strip on the right; the last column takes the freed space.

## [1.1.0]
- Release-tag app icon (window, taskbar and the `.exe` file).
- Version number in the window title, and an About box (Settings > About) with a Copy version button.
- Small icons next to the toolbar buttons; the theme button is now a moon / sun icon with a tooltip.
- Thin separator lines between rows.
- Rename a project: hover a row and click the pencil, press F2, or right-click > Rename. Reset name restores the GitHub name. Custom names are saved and exported.
- Fix: when the window is stretched sideways, all columns now grow in proportion (before, only Status grew). Shrinking works the same way, and a column you drag keeps your width until the window is resized.
- Fix: a project with an empty About box on GitHub no longer shows another project's description; it shows "No description, website, or topics provided."
- Fix: status messages such as "Renamed to ..." or "Marked 1 project(s) as seen." are no longer replaced right away by the project description.
- `build.bat` now checks Python and tkinter, reads the version, adds the icon and writes ready-to-paste release notes with the SHA-256.
- The GitHub Actions workflow (manual run) now also writes the release notes, with the SHA-256 and a link to the public build log. It never touches a Release by itself.

## [1.0.1]
- Right-click menus in text boxes (Cut / Copy / Paste / Select all) and on the status bar (Copy).

## [1.0.0]
- First release: add GitHub projects, check for new releases (feed first, API as fallback), sortable list, import / export, light and dark theme, portable `.exe`.
