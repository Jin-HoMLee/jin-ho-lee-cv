#!/usr/bin/env bash
# install.sh - get/refresh the framework payload in an instance.
#
# Part of the distributable payload (listed in framework/FILES), so installed
# instances self-update with their own copy. Distribution ONLY: copies exactly
# the framework/FILES set from the SOURCE CLONE'S GIT CONTENT AT A REF (never
# the working tree) and stamps the pin. It wires no symlinks - adapter wiring
# stays doctor.sh fix-mode's job, so exactly one place creates symlinks.
#
# Refusals are report-never-clobber:
#   SHADOWED  (--into)  destination exists and differs - kept, instance-owned
#   MODIFIED  (--sync)  destination differs from install's own record of what
#                       it last put there - kept, override per file with
#                       --force-file <landing>
#   ORPHANED  (--sync)  a previously-installed landing dropped upstream -
#                       kept, remove with --prune (unmodified orphans only)
#   TAINTED ORPHAN (--sync) a previously-installed landing is itself
#                       untrustworthy ('..' component, or outside .agents/) -
#                       ignored, never touched, not even with --prune
#
# framework_ref (the pin, in the instance's manifest) and
# .agents/framework-receipt (install's own record of every landing it put
# there, one "<path><TAB><blob oid>" line per file) are deliberately separate
# concerns - the pin says which release is current, the receipt says what
# install did and provides the modified-vs-pristine baseline, the same split
# dpkg's .list+md5sums and pip's RECORD use. Splitting them lets the pin
# always advance on every apply run, refusals and all: an ORPHANED or
# MODIFIED ORPHAN landing stays discoverable and prunable through its
# receipt entry no matter where framework_ref currently points, and a
# MODIFIED (non-orphan) landing stays flagged because the receipt keeps its
# last-installed oid until --force-file overwrites it. The receipt is
# install-owned: written atomically once at the end of an apply run, never
# touched by --check.
#
# Exit: 0 clean/up-to-date; 1 refusals or pending --check changes; 2 fatal.

set -u

usage() {
  cat <<'EOF'
Usage:
  install.sh --into <target> [--ref <ref>] [--check]
  install.sh --sync [--ref <ref>] [--check] [--force-file <landing>]... [--prune]

  --into <target>    First install. Run from inside a framework clone; copies
                     the framework/FILES set into <target>/.agents/... and
                     stamps framework_source + framework_ref in the target's
                     .agents/manifest.
  --sync             Update. Run from inside an installed instance; re-resolves
                     the framework source, re-copies the declared set at the
                     new ref, updates framework_ref (and nothing else).
  --check            Dry-run: report what would change, write nothing.
  --ref <ref>        Pin this tag/SHA instead of the newest framework/v* tag.
  --force-file <p>   (sync) Overwrite this locally-modified landing path.
  --prune            (sync) Delete orphaned framework files that still match
                     the pinned copy.
EOF
}

MODE='' TARGET='' CHECK=0 PRUNE=0 REF_OVERRIDE='' REF=''
FORCE_FILES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --into)
      [ $# -ge 2 ] || { echo "ERROR: --into needs a target path" >&2; exit 2; }
      MODE=into; TARGET="$2"; shift 2 ;;
    --sync) MODE=sync; shift ;;
    --check) CHECK=1; shift ;;
    --prune) PRUNE=1; shift ;;
    --force-file)
      [ $# -ge 2 ] || { echo "ERROR: --force-file needs a landing path" >&2; exit 2; }
      FORCE_FILES+=("$2"); shift 2 ;;
    --ref)
      [ $# -ge 2 ] || { echo "ERROR: --ref needs a value" >&2; exit 2; }
      REF_OVERRIDE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument '$1'" >&2; usage >&2; exit 2 ;;
  esac
done
if [ -z "$MODE" ]; then usage >&2; exit 2; fi

PENDING=0
APPLIED=0
report_apply()   { echo "$1"; APPLIED=$((APPLIED + 1)); }
report_pending() { echo "$1"; PENDING=$((PENDING + 1)); }
warn()  { echo "WARN: $1" >&2; }
fatal() { echo "ERROR: $1" >&2; exit 2; }

if [ "$MODE" = into ]; then
  [ "$PRUNE" = 0 ] || fatal "--prune is only valid with --sync"
  [ "${#FORCE_FILES[@]}" -eq 0 ] || fatal "--force-file is only valid with --sync"
fi

# --- resolve source clone (SRC) and instance (TARGET) ---

if [ "$MODE" = into ]; then
  SRC="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$SRC" ] && [ -f "$SRC/framework/FILES" ] \
    || fatal "--into must run from inside a framework clone (no framework/FILES at the git toplevel)"
  [ -d "$TARGET" ] || fatal "target '$TARGET' does not exist"
  TARGET="$(cd "$TARGET" && pwd -P)"
else
  TARGET="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  [ -n "$TARGET" ] || fatal "--sync must run from inside the instance (a git repo)"
fi

MANIFEST="$TARGET/.agents/manifest"
[ -f "$MANIFEST" ] || fatal "no manifest at $MANIFEST - declare the instance first (doctor.sh --init <topology>)"

# manifest_get <key>: first value wins (same semantics as doctor.sh).
manifest_get() {
  local line
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "$1="*) printf '%s\n' "${line#"$1"=}"; return 0 ;;
    esac
  done < "$MANIFEST"
  return 0
}

PIN=
if [ "$MODE" = sync ]; then
  PIN="$(manifest_get framework_ref)"
  [ -n "$PIN" ] || fatal "no framework_ref in $MANIFEST - not installed yet (run install.sh --into <this-instance> from a framework clone)"
  SRC="$(manifest_get framework_source)"
  if [ -n "$SRC" ]; then
    case "$SRC" in
      /*) ;;
      *) SRC="$TARGET/$SRC" ;;
    esac
    [ -d "$SRC" ] || fatal "framework_source '$SRC' (from manifest) does not exist"
  else
    parent="$(dirname "$TARGET")"
    if [ -f "$parent/agent-personas/framework/FILES" ]; then
      SRC="$parent/agent-personas"
    elif [ -f "$parent/claude-personas/framework/FILES" ]; then
      SRC="$parent/claude-personas"
    else
      fatal "no framework_source in $MANIFEST and no sibling agent-personas/claude-personas clone next to $TARGET - set framework_source explicitly"
    fi
  fi
  SRC="$(cd "$SRC" && pwd)"
  [ -f "$SRC/framework/FILES" ] || fatal "'$SRC' is not a framework clone (no framework/FILES)"
  git -C "$SRC" fetch --tags --quiet 2>/dev/null || true
fi

# --- resolve the ref to pin ---

if [ -n "$REF_OVERRIDE" ]; then
  RESOLVED_SHA="$(git -C "$SRC" rev-parse --verify --quiet "$REF_OVERRIDE^{commit}")" \
    || fatal "ref '$REF_OVERRIDE' not found in $SRC"
  case "$REF_OVERRIDE" in
    framework/v*) REF="$REF_OVERRIDE" ;;
    *)
      warn "pinning '$REF_OVERRIDE' - prefer a framework/v* tag"
      # Symbolic refs (HEAD, branch names, short SHAs) must not become the
      # pin verbatim - they move, which permanently zeroes doctor staleness
      # and drifts the receipt-absent fallback baseline. Resolve to the full
      # commit SHA instead; git show/ls-tree accept it identically to a ref.
      REF="$RESOLVED_SHA" ;;
  esac
else
  REF="$(git -C "$SRC" tag -l 'framework/v*' --sort=-v:refname | head -n 1)"
  if [ -z "$REF" ]; then
    REF="$(git -C "$SRC" rev-parse HEAD)"
    warn "no framework/v* tag in $SRC - pinning bare SHA $REF (prefer tags)"
  fi
fi

# --- read FILES at the refs ---

NEW_FILES="$(git -C "$SRC" show "$REF:framework/FILES" 2>/dev/null)" \
  || fatal "framework/FILES not found at ref '$REF' in $SRC"
PIN_FILES=""
if [ "$MODE" = sync ]; then
  PIN_FILES="$(git -C "$SRC" show "$PIN:framework/FILES" 2>/dev/null)" \
    || fatal "framework/FILES not found at pinned ref '$PIN' in $SRC - fetch the source or fix the pin"
fi

# parse_files: stdin FILES text -> "src<TAB>landing" lines; fatal on malformed.
parse_files() {
  local line
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    case "$line" in
      *' -> '*) printf '%s\t%s\n' "${line%% -> *}" "${line##* -> }" ;;
      *) return 1 ;;
    esac
  done
  return 0
}
NEW_TAB="$(printf '%s\n' "$NEW_FILES" | parse_files)" || fatal "malformed framework/FILES at '$REF'"
PIN_TAB=""
if [ "$MODE" = sync ]; then
  PIN_TAB="$(printf '%s\n' "$PIN_FILES" | parse_files)" || fatal "malformed framework/FILES at pin '$PIN'"
fi

pin_src_for_landing() {
  printf '%s\n' "$PIN_TAB" | awk -F'\t' -v l="$1" '$2 == l { print $1; exit }'
}
new_has_landing() {
  printf '%s\n' "$NEW_TAB" | awk -F'\t' -v l="$1" '$2 == l { found = 1 } END { exit found ? 0 : 1 }'
}
is_forced() {
  local f
  if [ "${#FORCE_FILES[@]}" -gt 0 ]; then
    for f in "${FORCE_FILES[@]}"; do
      [ "$f" = "$1" ] && return 0
    done
  fi
  return 1
}

# --- framework receipt (install-owned; dpkg .list+md5sums / pip RECORD split) ---
#
# Loaded once into RECEIPT_TAB (bash 3.2: no assoc arrays, so this stays a
# plain "<landing><TAB><oid>" text blob with awk-based get/set/del helpers,
# same style as PIN_TAB/NEW_TAB above). Mutated only in memory during a run;
# write_receipt() persists it, and is only ever called once, at the very
# end, guarded on CHECK = 0.

RECEIPT_FILE="$TARGET/.agents/framework-receipt"
RECEIPT_TAB=""
if [ -f "$RECEIPT_FILE" ]; then
  RECEIPT_TAB="$(awk '/^[[:space:]]*$/ { next } /^#/ { next } { print }' "$RECEIPT_FILE")"
fi

receipt_get_oid() { # receipt_get_oid <landing> -> tracked oid, or empty
  printf '%s\n' "$RECEIPT_TAB" | awk -F'\t' -v l="$1" 'NF == 0 { next } $1 == l { print $2; exit }'
}
receipt_set() { # receipt_set <landing> <oid> - record/replace, in memory only
  local landing="$1" oid="$2"
  RECEIPT_TAB="$(printf '%s\n' "$RECEIPT_TAB" | awk -F'\t' -v l="$landing" -v o="$oid" '
    NF == 0 { next }
    $1 == l { print l "\t" o; found = 1; next }
    { print }
    END { if (!found) print l "\t" o }
  ')"
}
receipt_del() { # receipt_del <landing> - drop entry, in memory only
  local landing="$1"
  RECEIPT_TAB="$(printf '%s\n' "$RECEIPT_TAB" | awk -F'\t' -v l="$landing" 'NF == 0 { next } $1 != l')"
}
receipt_landings() { # every landing path currently tracked, one per line
  printf '%s\n' "$RECEIPT_TAB" | awk -F'\t' 'NF { print $1 }'
}
write_receipt() { # persist RECEIPT_TAB atomically, sorted by landing
  local tmp
  mkdir -p "$(dirname "$RECEIPT_FILE")" || fatal "cannot create $(dirname "$RECEIPT_FILE")"
  tmp="$(mktemp "$(dirname "$RECEIPT_FILE")/.framework-receipt.XXXXXX" 2>/dev/null)" || fatal "mktemp failed"
  { echo "# framework-receipt - written by install.sh; landing path<TAB>blob oid. Do not edit."
    printf '%s\n' "$RECEIPT_TAB" | awk -F'\t' 'NF' | sort
  } > "$tmp" || { rm -f "$tmp"; fatal "cannot write $RECEIPT_FILE"; }
  if [ -f "$RECEIPT_FILE" ] && cmp -s "$tmp" "$RECEIPT_FILE"; then
    rm -f "$tmp"
    return 0
  fi
  mv "$tmp" "$RECEIPT_FILE" || { rm -f "$tmp"; fatal "cannot write $RECEIPT_FILE"; }
  chmod 0644 "$RECEIPT_FILE" || fatal "cannot set mode on $RECEIPT_FILE"
}

# --- copy machinery ---

write_from_ref() { # write_from_ref <src_path> <landing> <label>
  local src_path="$1" landing="$2" label="$3" dest="$TARGET/$2" tmp mode new_oid
  if [ "$CHECK" = 1 ]; then
    case "$label" in
      INSTALLED) report_pending "WOULD-INSTALL: $landing (from $src_path @ $REF)" ;;
      *)         report_pending "WOULD-SYNC: $landing (from $src_path @ $REF)" ;;
    esac
    return 0
  fi
  mkdir -p "$(dirname "$dest")" || fatal "cannot create $(dirname "$dest")"
  tmp="$(mktemp "$(dirname "$dest")/.install.$(basename "$dest").XXXXXX" 2>/dev/null)" || fatal "mktemp failed"
  if ! git -C "$SRC" show "$REF:$src_path" > "$tmp" 2>/dev/null; then
    rm -f "$tmp"
    fatal "cannot read '$src_path' at '$REF' from $SRC (is it in framework/FILES but not committed?)"
  fi
  mv "$tmp" "$dest" || { rm -f "$tmp"; fatal "cannot write $dest"; }
  mode="$(git -C "$SRC" ls-tree "$REF" -- "$src_path" 2>/dev/null | awk '{ print $1 }')"
  if [ "$mode" = "100755" ]; then
    chmod +x "$dest"
  else
    chmod 0644 "$dest"
  fi
  new_oid="$(source_oid "$REF" "$src_path")"
  receipt_set "$landing" "$new_oid"
  report_apply "$label: $landing"
}

# Blob oids, hashed/read through $SRC so both sides compare in the SAME
# repo's object format (the copy is byte-exact, so an installed pristine
# file hashes to its source oid).
current_oid() { git -C "$SRC" hash-object "$1" 2>/dev/null; }         # current_oid <dest-path>
source_oid()  { git -C "$SRC" rev-parse --verify --quiet "$1:$2"; }   # source_oid <ref> <src_path>

process_into() { # process_into <src_path> <landing>
  local src_path="$1" landing="$2" dest="$TARGET/$2" new_oid
  new_oid="$(source_oid "$REF" "$src_path")"
  [ -n "$new_oid" ] || fatal "cannot read '$src_path' at '$REF' from $SRC (is it in framework/FILES but not committed?)"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ "$(current_oid "$dest")" = "$new_oid" ]; then
      [ "$CHECK" = 1 ] || receipt_set "$landing" "$new_oid"
      return 0   # identical content: already installed - idempotent re-run, adopts pre-existing content
    fi
    report_pending "SHADOWED: $landing exists and differs - kept, instance-owned (install never overwrites)"
  else
    write_from_ref "$src_path" "$landing" INSTALLED
  fi
}

process_sync() { # process_sync <src_path> <landing>
  local src_path="$1" landing="$2" dest="$TARGET/$2"
  local new_oid cur_oid receipt_oid pin_src pinned_oid
  if [ ! -e "$dest" ] && [ ! -L "$dest" ]; then
    write_from_ref "$src_path" "$landing" INSTALLED
    return 0
  fi
  new_oid="$(source_oid "$REF" "$src_path")"
  cur_oid="$(current_oid "$dest")"
  if [ "$cur_oid" = "$new_oid" ]; then
    [ "$CHECK" = 1 ] || receipt_set "$landing" "$new_oid"
    return 0   # up to date
  fi
  receipt_oid="$(receipt_get_oid "$landing")"
  if [ -n "$receipt_oid" ]; then
    if [ "$cur_oid" = "$receipt_oid" ]; then
      write_from_ref "$src_path" "$landing" SYNCED
    elif is_forced "$landing"; then
      write_from_ref "$src_path" "$landing" FORCED
    else
      report_pending "MODIFIED: $landing differs from the pinned copy - kept (override: --force-file $landing)"
    fi
    return 0
  fi
  # No receipt entry for this landing (bootstrap/migration: instance
  # predates the receipt, or the file was deleted by hand): fall back to
  # comparing against the PIN's blob, exactly as before the receipt existed.
  pin_src="$(pin_src_for_landing "$landing")"
  pinned_oid=""
  if [ -n "$pin_src" ]; then
    pinned_oid="$(source_oid "$PIN" "$pin_src")"
  fi
  if [ "$cur_oid" = "$pinned_oid" ]; then
    write_from_ref "$src_path" "$landing" SYNCED
  elif is_forced "$landing"; then
    write_from_ref "$src_path" "$landing" FORCED
  else
    report_pending "MODIFIED: $landing differs from the pinned copy - kept (override: --force-file $landing)"
  fi
}

# candidate_landings: union of receipt-tracked landings and the pinned
# FILES' landings, one per line, deduplicated - the full pool process_orphans
# subtracts the new declared set from. A landing surviving in the receipt
# after its pin entry ages out (or vice versa) still surfaces here.
candidate_landings() {
  { receipt_landings
    printf '%s\n' "$PIN_TAB" | awk -F'\t' 'NF { print $2 }'
  } | awk 'NF' | sort -u
}

process_orphans() {
  local landing dest cur_oid target_oid pin_src
  while IFS= read -r landing; do
    [ -n "$landing" ] || continue
    if new_has_landing "$landing"; then continue; fi
    # A previously-installed landing is HISTORY, not the guarded current-ref
    # walk below - it can carry a bad path (a '..' traversal, or one outside
    # .agents/) that was never checked at the time it was installed/pinned.
    # Report-and-skip here, not fatal: fatal would brick --sync forever on
    # an instance carrying one bad historical entry, whereas skip-and-report
    # lets the run (and the pin) proceed cleanly.
    case "/$landing/" in
      */../*)
        report_pending "TAINTED ORPHAN: pinned FILES entry '$landing' contains a '..' component - ignored, never touched"
        continue ;;
    esac
    case "$landing" in
      .agents/*) ;;
      *)
        report_pending "TAINTED ORPHAN: pinned FILES entry '$landing' is outside .agents/ - ignored, never touched"
        continue ;;
    esac
    dest="$TARGET/$landing"
    if [ ! -e "$dest" ] && [ ! -L "$dest" ]; then
      [ "$CHECK" = 1 ] || receipt_del "$landing"
      continue
    fi
    cur_oid="$(current_oid "$dest")"
    target_oid="$(receipt_get_oid "$landing")"
    if [ -z "$target_oid" ]; then
      pin_src="$(pin_src_for_landing "$landing")"
      [ -n "$pin_src" ] && target_oid="$(source_oid "$PIN" "$pin_src")"
    fi
    if [ "$PRUNE" = 1 ] && [ "$CHECK" = 0 ]; then
      if [ -n "$target_oid" ] && [ "$cur_oid" = "$target_oid" ]; then
        rm "$dest" && { report_apply "PRUNED: $landing"; receipt_del "$landing"; } || fatal "cannot remove $dest"
      else
        report_pending "MODIFIED ORPHAN: $landing differs from the pinned copy - kept, delete by hand"
      fi
    elif [ "$PRUNE" = 1 ] && [ "$CHECK" = 1 ]; then
      if [ -n "$target_oid" ] && [ "$cur_oid" = "$target_oid" ]; then
        report_pending "WOULD-PRUNE: $landing no longer in framework/FILES"
      else
        report_pending "MODIFIED ORPHAN: $landing differs from the pinned copy - kept, delete by hand"
      fi
    else
      report_pending "ORPHANED: $landing no longer in framework/FILES - kept (remove with --prune)"
    fi
  done <<EOF_ORPHANS
$(candidate_landings)
EOF_ORPHANS
}

# --- walk the declared set ---

while IFS= read -r line; do
  [ -n "$line" ] || continue
  src_path="${line%%$'\t'*}"
  landing="${line##*$'\t'}"
  case "$landing" in
    .agents/*) ;;
    *) fatal "FILES declares a landing outside .agents/: '$landing' - refusing" ;;
  esac
  case "/$landing/" in
    */../*) fatal "FILES declares a landing with a '..' component: '$landing' - refusing" ;;
  esac
  if [ "$MODE" = into ]; then
    process_into "$src_path" "$landing"
  else
    process_sync "$src_path" "$landing"
  fi
done <<EOF_ENTRIES
$NEW_TAB
EOF_ENTRIES

if [ "$MODE" = sync ]; then
  process_orphans
fi

# --- write the receipt, then stamp the pin (neither ever happens in --check) ---
#
# The receipt (not the pin) is what makes an ORPHANED/MODIFIED ORPHAN landing
# discoverable and prunable, so the pin no longer needs to hold to preserve
# that provenance - it always advances on an apply run, refusals and all.
if [ "$CHECK" = 0 ]; then
  write_receipt

  if [ "$MODE" = into ]; then
    if [ "$SRC" = "$TARGET" ]; then
      SOURCE_VALUE="."
    elif [ "$(dirname "$SRC")" = "$(dirname "$TARGET")" ]; then
      SOURCE_VALUE="../$(basename "$SRC")"
    else
      SOURCE_VALUE="$SRC"
    fi
  fi
  if [ "$(manifest_get framework_ref)" != "$REF" ] \
     || { [ "$MODE" = into ] && [ "$(manifest_get framework_source)" != "${SOURCE_VALUE:-}" ]; }; then
    tmp="$(mktemp "$(dirname "$MANIFEST")/.manifest.XXXXXX" 2>/dev/null)" || fatal "mktemp failed"
    awk -F= -v mode="$MODE" '
      $1 == "framework_ref" { next }
      $1 == "framework_source" && mode == "into" { next }
      { print }
    ' "$MANIFEST" > "$tmp" || { rm -f "$tmp"; fatal "cannot rewrite $MANIFEST"; }
    if [ "$MODE" = into ]; then
      printf 'framework_source=%s\n' "$SOURCE_VALUE" >> "$tmp"
    fi
    printf 'framework_ref=%s\n' "$REF" >> "$tmp"
    mv "$tmp" "$MANIFEST" || fatal "cannot write $MANIFEST"
    chmod 0644 "$MANIFEST" || fatal "cannot set mode on $MANIFEST"
    report_apply "PINNED: framework_ref=$REF"
  fi
fi

if [ "$PENDING" -gt 0 ]; then
  exit 1
fi
if [ "$APPLIED" -gt 0 ]; then
  echo "OK: framework payload at $REF in $TARGET ($APPLIED change(s))"
else
  echo "OK: framework payload up to date at $REF in $TARGET"
fi
exit 0
