#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "${script_dir}/.." && pwd)"
source_path="${repository_root}/presentation-studio"
destination_path="${1:-${HOME}/.agents/skills/presentation-studio}"
force="${FORCE:-0}"

if [[ ! -f "${source_path}/SKILL.md" ]]; then
  printf 'Invalid package: presentation-studio/SKILL.md is missing.\n' >&2
  exit 1
fi

case "${destination_path}" in
  /|"${HOME}"|"${source_path}")
    printf 'Unsafe destination: %s\n' "${destination_path}" >&2
    exit 1
    ;;
esac

destination_parent="$(dirname "${destination_path}")"
destination_leaf="$(basename "${destination_path}")"
mkdir -p "${destination_parent}"
backup_path=""

if [[ -e "${destination_path}" ]]; then
  if [[ "${force}" != "1" ]]; then
    printf 'Destination exists. Re-run with FORCE=1 to create a timestamped backup first: %s\n' "${destination_path}" >&2
    exit 1
  fi
  backup_path="${destination_parent}/${destination_leaf}.backup-$(date +%Y%m%d-%H%M%S)"
  if [[ -e "${backup_path}" ]]; then
    printf 'Backup path already exists: %s\n' "${backup_path}" >&2
    exit 1
  fi
  mv "${destination_path}" "${backup_path}"
fi

if ! cp -a "${source_path}" "${destination_path}"; then
  failed_path="${destination_path}.failed-$(date +%Y%m%d-%H%M%S)"
  if [[ -e "${destination_path}" ]]; then
    mv "${destination_path}" "${failed_path}"
    printf 'Incomplete copy moved to: %s\n' "${failed_path}" >&2
  fi
  if [[ -n "${backup_path}" && -e "${backup_path}" ]]; then
    mv "${backup_path}" "${destination_path}"
    printf 'Previous installation restored.\n' >&2
  fi
  exit 1
fi

for required_file in \
  SKILL.md \
  catalog/products.json \
  catalog/styles.json \
  engines/manifest.json \
  source-lock.json; do
  if [[ ! -f "${destination_path}/${required_file}" ]]; then
    printf 'Installed package is incomplete: %s\n' "${required_file}" >&2
    exit 1
  fi
done

installed_count="$(find "${destination_path}" -type f | wc -l | tr -d ' ')"
printf 'Presentation Studio installed successfully.\n'
printf 'Destination: %s\n' "${destination_path}"
printf 'Files: %s\n' "${installed_count}"
if [[ -n "${backup_path}" ]]; then
  printf 'Previous installation backup: %s\n' "${backup_path}"
fi
printf 'Restart Codex, then invoke $presentation-studio or describe a presentation/image request naturally.\n'

