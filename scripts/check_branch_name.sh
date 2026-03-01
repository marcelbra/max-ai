#!/usr/bin/env bash
# Enforces the branch naming convention before pushing.
# Valid prefixes: feat, fix, opt, ref
# Format: "prefix/description"

current_branch=$(git symbolic-ref --short HEAD 2>/dev/null)

if [[ "$current_branch" == "main" ]]; then
    exit 0
fi

if [[ ! "$current_branch" =~ ^(feat|fix|opt|ref)/.+ ]]; then
    echo "ERROR: Branch '$current_branch' does not follow the naming convention."
    echo "Required format: feat/<name>, fix/<name>, opt/<name>, or ref/<name>"
    echo "Examples:"
    echo "  git checkout -b feat/wake-word"
    echo "  git checkout -b fix/recording-delay"
    exit 1
fi

exit 0
