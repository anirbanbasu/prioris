plugin_json := ".claude-plugin/plugin.json"
marketplace_json := ".claude-plugin/marketplace.json"

# Install pre-commit hooks using 'prek'
install-pre-commit-hooks:
    @echo "Installing pre-commit hooks using prek..."
    @prek install
    @echo "Pre-commit hooks installed."

# Update pre-commit hooks using 'prek'
pre-commit-update:
    @echo "Updating pre-commit hooks using prek..."
    @prek auto-update
    @echo "Pre-commit hooks updated."

# Validate plugin.json, marketplace.json, and every skill's evals.json and frontmatter
validate:
    @echo "Validating plugin manifest..."
    @claude plugin validate --strict {{plugin_json}}
    @echo "Validating marketplace manifest..."
    @claude plugin validate --strict {{marketplace_json}}
    @echo "Validating evals.json files..."
    @for f in skills/*/evals/evals.json; do jq empty "$f" && echo "  ok: $f"; done
    @just check-skills
    @echo "Validation complete."

# Sanity-check every SKILL.md has frontmatter with 'name' and 'description'
check-skills:
    #!/usr/bin/env bash
    set -euo pipefail
    fail=0
    for f in skills/*/SKILL.md; do
        frontmatter=$(awk '/^---$/{c++; next} c==1' "$f")
        grep -q '^name:' <<< "$frontmatter" || { echo "✘ $f: missing 'name' in frontmatter"; fail=1; }
        grep -q '^description:' <<< "$frontmatter" || { echo "✘ $f: missing 'description' in frontmatter"; fail=1; }
    done
    if [ "$fail" -eq 0 ]; then
        echo "All SKILL.md files have required frontmatter fields."
    else
        exit 1
    fi

# Bump the patch version of the plugin (kept in sync across plugin.json and marketplace.json)
bump-patch:
    @just _bump patch

# Bump the minor version of the plugin (kept in sync across plugin.json and marketplace.json)
bump-minor:
    @just _bump minor

# Bump the major version of the plugin (kept in sync across plugin.json and marketplace.json)
bump-major:
    @just _bump major

_bump part:
    #!/usr/bin/env bash
    set -euo pipefail
    current=$(jq -r '.version' {{plugin_json}})
    IFS='.' read -r major minor patch <<< "$current"
    case "{{part}}" in
        patch) patch=$((patch + 1));;
        minor) minor=$((minor + 1)); patch=0;;
        major) major=$((major + 1)); minor=0; patch=0;;
        *) echo "Unknown part: {{part}}"; exit 1;;
    esac
    new="$major.$minor.$patch"
    echo "Bumping version: $current -> $new"
    tmp=$(mktemp) && jq --arg v "$new" '.version = $v' {{plugin_json}} > "$tmp" && mv "$tmp" {{plugin_json}}
    tmp=$(mktemp) && jq --arg v "$new" '(.plugins[] | select(.name == "prioris") | .version) = $v' {{marketplace_json}} > "$tmp" && mv "$tmp" {{marketplace_json}}
    echo "Updated plugin.json and marketplace.json to $new"

# Preview the release tag without creating it
tag-dry-run:
    @claude plugin tag --dry-run .

# Create a {name}--v{version} git tag for the current version (validates manifests first)
tag:
    @just validate
    @claude plugin tag .

# Create and push the release tag to origin
release:
    @just validate
    @claude plugin tag --push .

# Run everything worth checking before a release: manifests, skills, and a tag preview
pre-release-check:
    @echo "Running pre-release checks..."
    @just validate
    @echo "Previewing release tag..."
    @just tag-dry-run
    @echo "Pre-release checks complete."
