# CI/CD Integration

Integrate documentation coverage checks into your continuous integration pipeline.

## GitHub Actions

### Basic Coverage Check

```yaml
name: Documentation Coverage

on:
  pull_request:
    paths:
      - 'src/**'
      - 'lib/**'

jobs:
  doc-coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Analyze documentation
        run: |
          python code-docs/scripts/analyze.py src/ --output analysis.json
          python code-docs/scripts/audit.py analysis.json --format json > audit.json
      
      - name: Check coverage threshold
        run: |
          COVERAGE=$(jq '.summary.coverage' audit.json)
          echo "Documentation coverage: $COVERAGE%"
          if (( $(echo "$COVERAGE < 70" | bc -l) )); then
            echo "::error::Documentation coverage $COVERAGE% is below 70% threshold"
            exit 1
          fi
```

### With Staleness Check

```yaml
      - name: Check for stale documentation
        run: |
          STALE=$(jq '.summary.stale_count' audit.json)
          if [ "$STALE" -gt 0 ]; then
            echo "::warning::Found $STALE stale documentation entries"
            jq '.stale_issues[]' audit.json
          fi
```

### PR Comment with Report

```yaml
      - name: Generate markdown report
        if: always()
        run: |
          python code-docs/scripts/audit.py analysis.json --format markdown > report.md
      
      - name: Comment on PR
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '## 📚 Documentation Coverage Report\n\n' + report
            });
```

## GitLab CI

```yaml
doc-coverage:
  stage: test
  image: python:3.11
  script:
    - python code-docs/scripts/analyze.py src/ --output analysis.json
    - python code-docs/scripts/audit.py analysis.json --format json > audit.json
    - |
      COVERAGE=$(jq '.summary.coverage' audit.json)
      echo "Documentation coverage: $COVERAGE%"
      if (( $(echo "$COVERAGE < 70" | bc -l) )); then
        echo "Documentation coverage below threshold"
        exit 1
      fi
  artifacts:
    reports:
      metrics: audit.json
    paths:
      - audit.json
  rules:
    - changes:
        - src/**/*
```

## Azure DevOps

```yaml
trigger:
  paths:
    include:
      - src/*

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'
  
  - script: |
      python code-docs/scripts/analyze.py src/ --output analysis.json
      python code-docs/scripts/audit.py analysis.json --format json > audit.json
    displayName: 'Analyze documentation'
  
  - script: |
      COVERAGE=$(jq '.summary.coverage' audit.json)
      echo "##vso[task.setvariable variable=docCoverage]$COVERAGE"
      if (( $(echo "$COVERAGE < 70" | bc -l) )); then
        echo "##vso[task.logissue type=error]Documentation coverage $COVERAGE% below threshold"
        exit 1
      fi
    displayName: 'Check coverage threshold'
  
  - task: PublishBuildArtifacts@1
    inputs:
      pathToPublish: 'audit.json'
      artifactName: 'doc-coverage'
```

## Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: doc-coverage
        name: Check documentation coverage
        entry: bash -c 'python code-docs/scripts/analyze.py src/ --output /tmp/analysis.json && python code-docs/scripts/audit.py /tmp/analysis.json --format json | jq -e ".summary.coverage >= 70"'
        language: system
        pass_filenames: false
        files: \.(py|js|ts|cs|go|rs|c|cpp|h)$
```

## Makefile Target

```makefile
.PHONY: doc-check doc-report

doc-check:
	@python code-docs/scripts/analyze.py src/ --output /tmp/analysis.json
	@python code-docs/scripts/audit.py /tmp/analysis.json --format json > /tmp/audit.json
	@COVERAGE=$$(jq '.summary.coverage' /tmp/audit.json); \
	echo "Documentation coverage: $$COVERAGE%"; \
	if [ $$(echo "$$COVERAGE < 70" | bc -l) -eq 1 ]; then \
		echo "Error: Coverage below 70%"; \
		exit 1; \
	fi

doc-report:
	@python code-docs/scripts/analyze.py src/ --output analysis.json
	@python code-docs/scripts/audit.py analysis.json --format markdown --output doc-report.md
	@python code-docs/scripts/score_readme.py . >> doc-report.md
	@echo "Report generated: doc-report.md"
```

## Recommended Thresholds

| Project Type | Minimum Coverage | Stale Tolerance |
|--------------|------------------|-----------------|
| Public library | 90% | 0 |
| Internal API | 80% | 2 |
| Application code | 70% | 5 |
| Prototype/MVP | 50% | 10 |

## Tips

- **Start low, increase gradually** — Set achievable thresholds initially
- **Exclude generated code** — Use `--exclude` patterns for auto-generated files
- **Focus on public APIs** — Prioritize exported functions and classes
- **Block on stale, warn on missing** — Stale docs are worse than none
- **Generate templates in CI** — Output suggestions for undocumented code
