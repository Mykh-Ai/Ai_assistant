#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-/bot/repo}"
BRANCH="${2:-main}"

cd "$ROOT_DIR"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
