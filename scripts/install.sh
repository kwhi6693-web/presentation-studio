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
destination_container="$(dirname "${destination_parent}")"
mkdir -p "${destination_parent}"
backup_root="${destination_container}/skill-backups/${destination_leaf}"
staging_root="${destination_container}/.skill-staging/${destination_leaf}"
staging_path="${staging_root}/$(date +%Y%m%d-%H%M%S)-$$"
backup_path=""

if [[ -e "${destination_path}" ]]; then
  if [[ "${force}" != "1" ]]; then
    printf 'Destination exists. Re-run with FORCE=1 to preserve it outside the skill discovery directory first: %s\n' "${destination_path}" >&2
    exit 1
  fi
fi

python_executable="${PRESENTATION_STUDIO_PYTHON:-}"
node_executable="${PRESENTATION_STUDIO_NODE:-}"
if [[ -z "${python_executable}" ]]; then
  python_executable="$(command -v python3 || command -v python || true)"
fi
if [[ -z "${node_executable}" ]]; then
  node_executable="$(command -v node || true)"
fi
for executable in "${python_executable}" "${node_executable}"; do
  if [[ -z "${executable}" || "${executable,,}" == *windowsapps* || ! -f "${executable}" ]]; then
    printf 'Python and Node.js are required. Set PRESENTATION_STUDIO_PYTHON and PRESENTATION_STUDIO_NODE to absolute executable paths.\n' >&2
    exit 1
  fi
done

mkdir -p "${staging_root}"
cleanup() {
  status=$?
  if [[ -e "${staging_path}" && "${staging_path}" == "${staging_root}/"* ]]; then
    rm -rf -- "${staging_path}"
  fi
  rmdir "${staging_root}" 2>/dev/null || true
  rmdir "$(dirname "${staging_root}")" 2>/dev/null || true
  if [[ ${status} -ne 0 && -n "${backup_path}" && -e "${backup_path}" && ! -e "${destination_path}" ]]; then
    mv "${backup_path}" "${destination_path}"
    printf 'Previous installation restored.\n' >&2 || true
  fi
  exit ${status}
}
trap cleanup EXIT

cp -a "${source_path}" "${staging_path}"
source_count="$(find "${source_path}" -type f | wc -l | tr -d ' ')"
staged_count="$(find "${staging_path}" -type f | wc -l | tr -d ' ')"
if [[ "${source_count}" != "${staged_count}" ]]; then
  printf 'Installed package copy is incomplete: expected %s files, found %s.\n' "${source_count}" "${staged_count}" >&2
  exit 1
fi

for required_file in \
  SKILL.md \
  catalog/products.json \
  catalog/styles.json \
  engines/manifest.json \
  scripts/self_check.py \
  source-lock.json; do
  if [[ ! -f "${staging_path}/${required_file}" ]]; then
    printf 'Installed package is incomplete: %s\n' "${required_file}" >&2
    exit 1
  fi
done

self_check_output="$("${python_executable}" "${staging_path}/scripts/self_check.py" \
  --root "${staging_path}" \
  --python "${python_executable}" \
  --node "${node_executable}" \
  --json)"

if [[ -e "${destination_path}" ]]; then
  mkdir -p "${backup_root}"
  backup_path="${backup_root}/$(date +%Y%m%d-%H%M%S)"
  if [[ -e "${backup_path}" ]]; then
    backup_path="${backup_path}-$$"
  fi
  mv "${destination_path}" "${backup_path}"
fi
mv "${staging_path}" "${destination_path}"
rmdir "${staging_root}" 2>/dev/null || true
rmdir "$(dirname "${staging_root}")" 2>/dev/null || true
trap - EXIT

installed_count="$(find "${destination_path}" -type f | wc -l | tr -d ' ')"
printf 'Presentation Studio installed successfully.\n'
printf 'Destination: %s\n' "${destination_path}"
printf 'Files: %s\n' "${installed_count}"
printf 'Self-check: PASS\n'
printf 'Python: %s\n' "${python_executable}"
printf 'Node.js: %s\n' "${node_executable}"
if [[ -n "${backup_path}" ]]; then
  printf 'Previous installation backup: %s\n' "${backup_path}"
fi
printf 'Reload your Agent/Harness Skill registry, then invoke $presentation-studio or describe a presentation/image request naturally.\n'

