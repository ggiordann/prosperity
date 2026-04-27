#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
cargo_wrapper="${repo_root}/scripts/cargo_local.sh"
os_name="$(uname -s)"

print_heading() {
    printf '\n%s\n' "$1"
}

print_heading "Environment"
printf 'os: %s\n' "${os_name}"
printf 'shell: %s\n' "${SHELL-unknown}"
printf 'path: %s\n' "${PATH}"
printf 'cargo wrapper: %s\n' "${cargo_wrapper}"
printf 'wrapper PATH: %s\n' "$("${cargo_wrapper}" --print-clean-path)"

target_dir="$("${cargo_wrapper}" --print-target-dir)"
if [ -n "${target_dir}" ]; then
    printf 'effective CARGO_TARGET_DIR: %s\n' "${target_dir}"
else
    printf 'effective CARGO_TARGET_DIR: cargo default (repo-local target/)\n'
fi

print_heading "Toolchain"
printf 'rustc: '
rustc --version || true
printf 'cargo: '
cargo --version || true
printf 'python3: '
python3 --version || true

if [ "${os_name}" != "Darwin" ]; then
    print_heading "macOS Checks"
    printf 'not running on macOS; execution-policy checks skipped\n'
    exit 0
fi

print_heading "macOS Checks"
if pgrep syspolicyd >/dev/null 2>&1; then
    printf 'syspolicyd:\n'
    ps -o pid,%cpu,%mem,etime,command -p "$(pgrep syspolicyd | tr '\n' ',' | sed 's/,$//')" || true
else
    printf 'syspolicyd: not running\n'
fi

if [ -d /private/var/db/DetachedSignatures ]; then
    printf 'DetachedSignatures: present\n'
else
    printf 'DetachedSignatures: missing (/private/var/db/DetachedSignatures)\n'
fi

print_heading "Recent Execution Policy Logs"
if command -v log >/dev/null 2>&1; then
    /usr/bin/log show --last 10m --style compact --predicate '(process == "syspolicyd") OR (process == "amfid") OR (eventMessage CONTAINS[c] "build-script-build") OR (eventMessage CONTAINS[c] "build-script-test")' | tail -n 60 || true
else
    printf 'log command not available\n'
fi
