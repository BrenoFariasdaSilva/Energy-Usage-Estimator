#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 scripts/launcher.py run
status=$?
if [ "$status" -ne 0 ]; then
  echo "Falha ao iniciar. Instale Python 3.11+ e confira a conexao com a internet."
  printf "Pressione Enter para sair..."
  read -r _
fi
exit "$status"
