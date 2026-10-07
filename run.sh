#!/usr/bin/env bash
set -e

# Navega para a pasta do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Cria o ambiente virtual e instala dependências se não existir
if [ ! -d ".venv" ]; then
    echo "Criando ambiente virtual (.venv)..."
    python3 -m venv .venv
    echo "Instalando dependências..."
    .venv/bin/pip install -r requirements.txt
fi

# Executa o baixador passando os parâmetros fornecidos
.venv/bin/python baixador.py "$@"
