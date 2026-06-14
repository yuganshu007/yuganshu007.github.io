# Applying this project to `yuganshu007/rynova-data-platform`

This directory is a self-contained compliance project for the **Rynova
Softwares (Nov 2022 – Aug 2024)** resume bullets.  In this portfolio
repository it lives at `projects/rynova-data-platform/`.

To install it into the actual
[`yuganshu007/rynova-data-platform`](https://github.com/yuganshu007/rynova-data-platform)
repository (where it should live at the top-level `rynova/`
directory), follow one of the two recipes below.

---

## Option A — Apply the bundled patch (preserves authorship)

```bash
git clone https://github.com/yuganshu007/rynova-data-platform.git
cd rynova-data-platform
git checkout -b rynova-bullet-compliance
git am < /path/to/APPLY_TO_RYNOVA_DATA_PLATFORM.patch
```

The patch was generated with `git format-patch` against the
`rynova-data-platform` upstream `main` and lands the project at
`rynova/` plus the CI workflow at `.github/workflows/rynova.yml`.

---

## Option B — Copy the directory

```bash
git clone https://github.com/yuganshu007/rynova-data-platform.git
cd rynova-data-platform
git checkout -b rynova-bullet-compliance

# Drop the project at rynova/ (top level)
cp -r /path/to/projects/rynova-data-platform ./rynova

# Drop the CI workflow at .github/workflows/
mkdir -p .github/workflows
cp ./rynova/ci/rynova.yml .github/workflows/rynova.yml

git add rynova .github/workflows/rynova.yml
git commit -m "feat(rynova): add resume-bullet compliance project"
git push -u origin rynova-bullet-compliance
```

---

## Verify it works

```bash
cd rynova
make install-dev
make data
make test       # 102 passing
make bench      # 4/4 PASS
```

See `COMPLIANCE.md` for the bullet-by-bullet mapping of every claim to a
file, line, and runnable command.
