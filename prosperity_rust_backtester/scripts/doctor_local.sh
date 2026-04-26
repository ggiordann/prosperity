#!/bin/sh
set -eu

os_name="$(uname -s)"
clean_path="${HOME}/.cargo/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

printf 'os: %s\n' "${os_name}"
printf 'pwd: %s\n' "$(pwd)"
printf 'target_dir: %s\n' "${CARGO_TARGET_DIR-${HOME}/Library/Caches/rust_backtester/target}"
printf 'clean_path: %s\n' "${clean_path}"

if [ "${os_name}" = "Darwin" ]; then
    printf 'xcode-select: '
    xcode-select -p 2>/dev/null || printf 'missing\n'
    printf 'python3: '
    command -v python3 2>/dev/null || printf 'missing\n'
    printf 'cargo: '
    command -v cargo 2>/dev/null || printf 'missing\n'
    printf 'rustc: '
    command -v rustc 2>/dev/null || printf 'missing\n'
    printf 'syspolicyd: '
    ps aux | grep syspolicyd | grep -v grep || printf 'not running or not visible\n'
else
    printf 'python3: '
    command -v python3 2>/dev/null || printf 'missing\n'
    printf 'cargo: '
    command -v cargo 2>/dev/null || printf 'missing\n'
    printf 'rustc: '
    command -v rustc 2>/dev/null || printf 'missing\n'
fi
