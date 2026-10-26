#!/bin/bash
set -e
GPIO_TOOLS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export GPIO_TOOLS_DIR
exec /bin/bash --rcfile "$GPIO_TOOLS_DIR/terminal-bashrc" -i
