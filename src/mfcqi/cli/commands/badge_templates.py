"""Templates for badge generation."""

MARKDOWN_TEMPLATE = """# MFCQI Badge

![MFCQI Score]({url})

## Score Details
- **Score**: {score:.3f}
- **Rating**: {rating}
- **Path**: {path}

## Usage Options

### Option 1: Static Badge (Simplest)
Add this to your README.md:
```markdown
![MFCQI Score]({url})
```

### Option 2: Badge with Link
```markdown
[![MFCQI Score]({url})](https://github.com/integrallis/mfcqi-python)
```

### Option 3: Dynamic Badge via GitHub Actions
Create `.github/workflows/mfcqi-badge.yml`:

```yaml
name: Update MFCQI Badge
on: [push, pull_request]

jobs:
  update-badge:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install MFCQI
        run: pip install mfcqi

      - name: Generate Badge JSON
        run: |
          mfcqi-py badge . -f json -o .github/badges/mfcqi.json

      - name: Commit Badge
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add .github/badges/mfcqi.json
          git diff --quiet && git diff --staged --quiet || git commit -m "Update MFCQI badge"
          git push
```

Then use in README:
```markdown
![MFCQI Score](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/.github/badges/mfcqi.json)
```

### Option 4: Use in CI/CD Status Checks
```yaml
- name: Check Code Quality
  run: |
    SCORE=$(mfcqi-py analyze . --format json | jq -r .mfcqi)
    if (( $(echo "$SCORE < 0.7" | bc -l) )); then
      echo "Code quality score $SCORE is below threshold"
      exit 1
    fi
```
"""
