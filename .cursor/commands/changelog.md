---
description: >-
  Package the current chat session into bilingual CHANGELOG.ru.md and
  CHANGELOG.md release sections.
---

# Changelog from session

Turn the work discussed in this chat into a Keep a Changelog release for Dochive.

## What to collect from the chat

Review the conversation and current git diff. Extract only user-visible outcomes:

- new features or CLI flags → `### Added`
- behavior or doc updates → `### Changed`
- bug fixes → `### Fixed`
- removals → `### Removed`

Skip refactors, test-only edits, and internal planning unless they matter to users.

## Version and placement

- Pick the next semver **not already present** in [CHANGELOG.md](CHANGELOG.md).
- Use today's date (`YYYY-MM-DD`) unless the user specifies another date.
- Add the new release **before** the first existing `## [version]` block in each changelog file.
- Keep the file header and `[Русский] | [English]` language links unchanged.

## English block for CHANGELOG.md

Insert after the intro paragraph and before the previous latest release:

```markdown
## [0.0.0] — YYYY-MM-DD

Branch `branch-name`.

### Added

- English bullet.

### Fixed

- English bullet.

```

Omit empty sections. Omit the `Branch ...` line if there is no meaningful branch context.

## Russian block for CHANGELOG.ru.md

Mirror the same version and date in [CHANGELOG.ru.md](CHANGELOG.ru.md):

```markdown
## [0.0.0] — YYYY-MM-DD

Ветка `branch-name`.

### Added

- Русский пункт.

### Fixed

- Русский пункт.

```

Section headings stay in English (`### Added`, `### Fixed`, ...). Bullets are in Russian.

## Before editing

1. Read both changelog files and confirm the version is new.
2. Show the user a short preview of both release blocks.
3. Edit only after confirmation unless the user asks to apply immediately.

## After editing

- Confirm both changelog files were updated.
- Remind the user that GitHub shows the **Changelog** tab from root `CHANGELOG.md` after merge to `main`.
- Offer to commit the changelog files; do not commit unless asked.

## Do not

- Edit the plan file if one exists in `.cursor/plans/`.
- Invent changes that are not supported by the chat or git diff.
- Replace entire changelog files or remove older releases.
