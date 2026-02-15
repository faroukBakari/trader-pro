#!/bin/bash                                           
  # IA Stack Guard — enforcement hook for exclusive .claude/ modification rights
  # Events: UserPromptSubmit, PreToolUse, PostToolUse                                                                                                                                             
  # Guards: Edit, Write, Bash (incl. claude CLI), create_file_code, replace_lines_code, move_file_code, rename_file_code
  # Requires ia-design skill context before .claude/ modifications                                                                                                                                
  # Mode: block (default) or warn — set via IA_STACK_GUARD_MODE env var                        
                     
  INPUT=$(cat)
  SESSION=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
  EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // ""')
  STATE="/tmp/claude-ia-guard-${SESSION}"
  MODE="${IA_STACK_GUARD_MODE:-block}"

  # ── UserPromptSubmit: reset per-turn ia_context flag ──
  if [ "$EVENT" = "UserPromptSubmit" ]; then
    echo "ia_context=0" > "$STATE"
    exit 0
  fi

  TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

  # ── PostToolUse: track ia-design skill reads ──
  if [ "$EVENT" = "PostToolUse" ]; then
    if [ "$TOOL_NAME" = "Read" ]; then
      FPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
      # Only ia-* methodology skills in skill-bank set context
      # (NOT glossaries or agent templates — those are targets, not authorization signals)
      if echo "$FPATH" | grep -qE '\.claude/skill-bank/ia-'; then
        if [ -f "$STATE" ]; then
          sed -i 's/ia_context=0/ia_context=1/' "$STATE"
        else
          echo "ia_context=1" > "$STATE"
        fi
      fi
    fi
    exit 0
  fi

  # ── PreToolUse: guard .claude/ write operations ──
  if [ "$EVENT" = "PreToolUse" ]; then
    # Extract target path based on tool type
    case "$TOOL_NAME" in
      Edit|Write)
        FPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')
        ;;
      mcp__vscode-mcp-server__create_file_code|mcp__vscode-mcp-server__replace_lines_code)
        FPATH=$(echo "$INPUT" | jq -r '.tool_input.path // ""')
        ;;
      mcp__vscode-mcp-server__move_file_code)
        SRC=$(echo "$INPUT" | jq -r '.tool_input.sourcePath // ""')
        TGT=$(echo "$INPUT" | jq -r '.tool_input.targetPath // ""')
        FPATH="${SRC} ${TGT}"
        ;;
      mcp__vscode-mcp-server__rename_file_code)
        FPATH=$(echo "$INPUT" | jq -r '.tool_input.filePath // ""')
        ;;
      Task)
        # Reset ia_context on subagent spawn — prevent cross-agent inheritance
        echo "ia_context=0" > "$STATE"
        exit 0
        ;;
      Bash)
        CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
        # Allow governance scripts
        if echo "$CMD" | grep -qE '^python3?\s+(\./)?\.claude/scripts/'; then
          exit 0
        fi
        # Catch CLI commands that modify .claude/ config indirectly
        # (claude mcp add/remove, claude config set — path never appears in args)
        if echo "$CMD" | grep -qE '\bclaude\s+(mcp|config)\s'; then
          FPATH=".claude/"
        # Check if command targets .claude/ paths explicitly
        elif echo "$CMD" | grep -qE '\.claude/'; then
          FPATH=".claude/"
        else
          exit 0
        fi
        ;;
      *) exit 0 ;;
    esac

    # Check if path targets .claude/ directory
    if echo "$FPATH" | grep -qE '\.claude/'; then
      # Exclude runtime-ephemeral paths (auto-memory, plan files)
      if echo "$FPATH" | grep -qE '\.claude/(projects|plans)/'; then
        exit 0
      fi

      # Check ia_context flag
      ia_context=0
      if [ -f "$STATE" ]; then
        # shellcheck source=/dev/null
        source "$STATE"
      fi

      if [ "$ia_context" -eq 0 ]; then
        MSG="IA Stack Guard: .claude/ modifications require ia-design context. Delegate to agentic-designer agent (Task with .claude/agents/agentic-designer.md template) or load ia-design skills
   first."
        if [ "$MODE" = "block" ]; then
          echo "$MSG" >&2
          exit 2
        else
          echo "$MSG" >&2
        fi
      fi
    fi
    exit 0
  fi

  exit 0