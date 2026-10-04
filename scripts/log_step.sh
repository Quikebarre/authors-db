#!/usr/bin/env bash
# Uso: scripts/log_step.sh "<tipo>" "<descripción>"   (tipo: PEDIDO | PROPUESTA | VALIDADO | DESCARTADO | DECISION)
# Añade una línea a ai-usage/02-registro-pasos.md con hora y tiempo transcurrido desde el inicio.
set -euo pipefail
cd "$(dirname "$0")/.."
start=$(cat ai-usage/.session_start)
now=$(date +%s)
el=$((now - start))
elapsed=$(printf '%02d:%02d:%02d' $((el/3600)) $((el%3600/60)) $((el%60)))
log=ai-usage/02-registro-pasos.md
[ -f "$log" ] || printf '# Registro de pasos (IA)\n\n| Hora (UTC) | Transcurrido | Tipo | Descripción |\n|---|---|---|---|\n' > "$log"
printf '| %s | %s | %s | %s |\n' "$(date -u +%H:%M:%S)" "$elapsed" "$1" "$2" >> "$log"
echo "Tiempo transcurrido desde el inicio: $elapsed"
