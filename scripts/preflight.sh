#!/usr/bin/env bash
set -euo pipefail
phase="${1:?before|before-pull|after}"
case "$phase" in before|before-pull|after) ;; *) exit 2 ;; esac
mkdir -p evidence/environment
if [ "${GITHUB_REPOSITORY_VISIBILITY:-}" != public ]; then
  echo 'STOP: this policy requires a public repository' >&2
  exit 1
fi
if [ "$phase" = before ]; then
  uname -a > evidence/environment/uname-a.txt
  uname -m > evidence/environment/uname-m.txt
  lscpu > evidence/environment/lscpu.txt
  docker --version > evidence/environment/docker-cli.txt
  docker version > evidence/environment/docker-version.txt 2>&1
  docker info > evidence/environment/docker-info.txt 2>&1
fi
free -h > "evidence/environment/free-$phase.txt"
df -h > "evidence/environment/df-$phase.txt"
total_kib="$(awk '/^MemTotal:/ {printf "%.0f", $2}' /proc/meminfo)"
available_kib="$(awk '/^MemAvailable:/ {printf "%.0f", $2}' /proc/meminfo)"
docker_root="$(docker info --format '{{.DockerRootDir}}')"
workspace_free="$(df -PB1 "$GITHUB_WORKSPACE" | awk 'NR==2 {print $4}')"
docker_free="$(df -PB1 "$docker_root" | awk 'NR==2 {print $4}')"
minimum_disk=$((10 * 1024 * 1024 * 1024))
if [ "$phase" = after ]; then minimum_disk=$((4 * 1024 * 1024 * 1024)); fi
printf 'phase=%s\nCPU_ARCH=%s\nRAM_TOTAL_KIB=%s\nRAM_AVAILABLE_KIB=%s\nWORKSPACE_FREE_BYTES=%s\nDOCKER_FREE_BYTES=%s\nMIN_DISK_BYTES=%s\n' \
  "$phase" "$(uname -m)" "$total_kib" "$available_kib" "$workspace_free" "$docker_free" "$minimum_disk" \
  > "evidence/environment/resources-$phase.txt"
test "$(uname -m)" = x86_64
test "$total_kib" -ge $((14 * 1024 * 1024))
test "$available_kib" -ge $((6 * 1024 * 1024))
test "$workspace_free" -ge "$minimum_disk"
test "$docker_free" -ge "$minimum_disk"
echo "RESOURCE_GATE_$phase=PASS"
