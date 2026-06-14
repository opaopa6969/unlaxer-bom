#!/usr/bin/env bash
#
# create-vacant-workspace.sh
#
# カレントディレクトリに vacant-workspace/ を作り、その中へ vacant プロジェクト群を clone する。
# 対象は issue-runner と vacant-allinone を除いた 6 リポジトリ。
# develop ブランチがあれば develop を、無ければデフォルトブランチ(main/master)を checkout する。
# 既に clone 済みのディレクトリはスキップする(冪等)。
#
# 使い方:
#   ./create-vacant-workspace.sh            # ./vacant-workspace に clone
#   WORKSPACE_DIR=foo ./create-vacant-workspace.sh   # 任意のディレクトリ名で作成
#
set -euo pipefail

WORKSPACE_DIR="${WORKSPACE_DIR:-vacant-workspace}"

# repo<TAB>cloneURL。org は opaopa6969 / caulis が混在する。
REPOS=(
  "ABRUtils|git@github.com:opaopa6969/ABRUtils.git"
  "building-hierarchy|git@github.com:opaopa6969/building-hierarchy.git"
  "japanpost-history|git@github.com:opaopa6969/japanpost-history.git"
  "municipality-history|git@github.com:opaopa6969/municipality-history.git"
  "onigiri-parser|git@github.com:opaopa6969/onigiri-parser.git"
  "vacant-service|git@github.com:caulis/vacant-service.git"
)

mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

for entry in "${REPOS[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"

  if [ -d "$name/.git" ]; then
    echo "skip   : $name (already cloned)"
    continue
  fi

  echo "clone  : $name"
  git clone --quiet "$url" "$name"

  # develop があれば develop 優先、無ければデフォルトブランチのまま
  if git -C "$name" show-ref --verify --quiet refs/remotes/origin/develop; then
    git -C "$name" checkout --quiet develop
    echo "       -> develop"
  else
    echo "       -> $(git -C "$name" rev-parse --abbrev-ref HEAD) (default)"
  fi
done

echo
echo "done: $(pwd)"
