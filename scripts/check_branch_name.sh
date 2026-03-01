#!/usr/bin/env bash
# Enforces the branch naming convention before pushing.
# Valid prefixes: FEAT, OPT, FIX, REF
# Format: "PREFIX: description"

current_branch=$(git symbolic-ref --short HEAD 2>/dev/null)

if [[ "$current_branch" == "main" ]]; then
    exit 0
fi

if [[ ! "$current_branch" =~ ^(FEAT|OPT|FIX|REF):\ .+ ]]; then
    echo "ERROR: Branch '$current_branch' does not follow the naming convention."
    echo "Required format: FEAT: <name>, OPT: <name>, FIX: <name>, or REF: <name>"
    echo "Examples:"
    echo "  git checkout -b \"FEAT: wake-word\""
    echo "  git checkout -b \"FIX: recording-delay\""
    exit 1
fi

exit 0
