# Public repository hygiene

This repository starts with a new history. It does not contain the personal
workshop repository, administration scripts, network configuration, logs,
backups, credentials, private photos or manufacturer PDF manuals.

The initial public commit uses the maintainer's GitHub handle and GitHub noreply
email address. Changing the author in a later commit would not remove identity
information from earlier commits; keep public author settings local to this repo.
Do not merge or push a personal repository's history into it.

Release archives are built from explicit runtime/document file lists. Generated
installers calculate the installing user's paths at runtime. Build outputs and
local configuration/credential files are ignored by Git.

Before publishing a change, inspect staged files and author/committer metadata,
scan both the working tree and Git history with a local secret scanner, and scan
the generated archives too. These checks reduce accidental exposure; they do not
make unreviewed future files safe. Review diagnostic logs before sharing them.

Example checks with Gitleaks installed:

```bash
git diff --cached --stat
git log --all --format='%h %an <%ae> | %cn <%ce>'
gitleaks dir . --redact --max-archive-depth 3
gitleaks git . --redact
```
