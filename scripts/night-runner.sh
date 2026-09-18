#!/usr/bin/env bash
# night-runner.sh — token-aware queue drainer for the dev-go pipeline.
#
# The outer loop that makes unattended production survive plan limits: it invokes
# Claude Code non-interactively on the next piece of work, and when the plan's
# usage limit is hit it PAUSES (sleeps) and re-invokes after the limit refreshes.
# dev-go resumes from its artifact checkpoints, so a pause mid-feature loses
# nothing. The model cannot do this for itself — once the limit is hit, every
# request fails — which is exactly why this loop lives outside the model.
#
# Usage:
#   scripts/night-runner.sh                          # drain queue + in-flight work
#   RUNNER_NOTIFY_URL=https://ntfy.sh/<topic> scripts/night-runner.sh   # + pings
#
# Constant production: queue briefs anytime with dev-po ("queue task X"), then
# schedule this hourly — it exits immediately when there is no work.
#   cron:  0 * * * *  cd /path/to/project && scripts/night-runner.sh >> .runner-logs/cron.log 2>&1
#
# Permissions for unattended runs: copy what you trust from the Agents repo's
# scripts/settings-unattended.json into the project's .claude/settings.json, or
# (trusted machine only) export RUNNER_CLAUDE_FLAGS="--dangerously-skip-permissions".
#
# Tuning: the usage-limit detection greps Claude Code's error text. If your CLI
# version words it differently, the raw output is in .runner-logs/<slug>.out —
# adjust LIMIT_REGEX below and consider proposing the fix upstream (Agents repo).

set -uo pipefail

QUEUE_DIR="${RUNNER_QUEUE_DIR:-queue}"
FEATURES_DIR="${RUNNER_FEATURES_DIR:-docs/features}"
LOG_DIR="${RUNNER_LOG_DIR:-.runner-logs}"
SLEEP_MIN="${RUNNER_SLEEP_MIN:-30}"            # pause length when the usage limit is hit
MAX_STALLS="${RUNNER_MAX_STALLS:-3}"           # clean exits with no progress before giving up
CLAUDE_FLAGS="${RUNNER_CLAUDE_FLAGS:---permission-mode acceptEdits}"
LIMIT_REGEX='usage limit|rate.?limit|limit (will )?reset|out of (usage|tokens)'

mkdir -p "$LOG_DIR"
run_log="$LOG_DIR/night-$(date -u +%Y%m%dT%H%M%SZ).log"

log()    { printf '[%s] %s\n' "$(date -u +%H:%M:%SZ)" "$*" | tee -a "$run_log"; }
notify() { [ -n "${RUNNER_NOTIFY_URL:-}" ] && curl -fsS -m 10 -d "$1" "$RUNNER_NOTIFY_URL" >/dev/null 2>&1 || true; }

# Work = queued briefs, or an in-flight feature dir (has 00-brief.md, no 08-signoff.md).
# Parked runs HAVE a signoff and are never auto-resumed — they wait for Joost.
work_state() {
  ls "$QUEUE_DIR"/[0-9]*.md 2>/dev/null | sort
  for d in "$FEATURES_DIR"/[0-9]*/; do
    [ -e "${d}00-brief.md" ] && [ ! -e "${d}08-signoff.md" ] && echo "in-flight:${d}"
  done 2>/dev/null
}

# Best-effort: pick up briefs queued remotely (e.g. from Cowork via GitHub).
sync_repo() {
  [ -n "$(git status --porcelain 2>/dev/null)" ] && return 0   # dirty tree: don't touch
  git fetch --quiet origin 2>/dev/null && git merge --ff-only --quiet FETCH_HEAD 2>/dev/null || true
}

stalls=0
cycle=0
while :; do
  sync_repo
  state_before="$(work_state)"
  if [ -z "$state_before" ]; then
    log "No queued or in-flight work — done."
    notify "night-runner: queue empty, done"
    exit 0
  fi

  cycle=$((cycle + 1))
  out="$LOG_DIR/cycle-$cycle.out"
  log "Cycle $cycle — work: $(echo "$state_before" | tr '\n' ' ')"

  claude -p "/dev-go next" $CLAUDE_FLAGS >"$out" 2>&1
  status=$?
  state_after="$(work_state)"

  if grep -qiE "$LIMIT_REGEX" "$out"; then
    log "Usage limit hit (exit $status). Pausing ${SLEEP_MIN}m, then resuming — checkpoints preserve the run."
    notify "night-runner: usage limit — paused ${SLEEP_MIN}m, will auto-resume"
    sleep $(( SLEEP_MIN * 60 ))
    stalls=0
    continue
  fi

  if [ "$state_after" != "$state_before" ]; then
    stalls=0
    # Report any run that just closed (newest signoff).
    last_signoff="$(ls -t "$FEATURES_DIR"/[0-9]*/08-signoff.md 2>/dev/null | head -1)"
    verdict="$(grep -m1 -oE 'SHIPPED|PARKED[^*]*|READY FOR REVIEW' "${last_signoff:-/dev/null}" 2>/dev/null)"
    log "Progress made (exit $status). Latest close: ${verdict:-none yet}."
    [ -n "$verdict" ] && notify "night-runner: $(dirname "${last_signoff#$FEATURES_DIR/}") — $verdict"
    continue
  fi

  stalls=$((stalls + 1))
  if [ "$stalls" -ge "$MAX_STALLS" ]; then
    log "No progress after $stalls cycles and no usage-limit signature — stopping. See $out"
    notify "night-runner: STOPPED — no progress, human needed (see $out)"
    exit 1
  fi
  log "No progress (exit $status, attempt $stalls/$MAX_STALLS) — retrying in 2m."
  sleep 120
done
