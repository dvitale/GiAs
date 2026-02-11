#!/bin/bash
# Esegue i test di consistenza RAG per intent info_procedure
#
# Uso:
#   ./scripts/run_rag_tests.sh           # Tutti i test
#   ./scripts/run_rag_tests.sh quick     # Solo test base rapidi
#   ./scripts/run_rag_tests.sh cu_01     # Singolo test case
#   ./scripts/run_rag_tests.sh metrics   # Solo test metriche aggregate

set -e
cd "$(dirname "$0")/.."

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Test RAG Consistency ===${NC}"
echo "Directory: $(pwd)"
echo ""

# Verifica server attivo
echo -n "Verifica server... "
if curl -s http://localhost:5005/status > /dev/null 2>&1; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}ERRORE${NC}"
    echo ""
    echo "Server non attivo. Avviare con:"
    echo "  scripts/server.sh start"
    exit 1
fi

# Verifica dipendenze
echo -n "Verifica dipendenze... "
if python -c "import pytest, yaml, requests" 2>/dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}Installazione dipendenze...${NC}"
    pip install pytest pyyaml requests -q
fi

echo ""

# Determina quali test eseguire
case "${1:-all}" in
    quick)
        echo -e "${YELLOW}Esecuzione test rapidi (solo base)...${NC}"
        python -m pytest tests/test_rag_consistency.py::TestIndividualCases -v \
            --tb=short
        ;;

    metrics)
        echo -e "${YELLOW}Esecuzione test metriche aggregate...${NC}"
        python -m pytest tests/test_rag_consistency.py::TestRAGMetrics -v \
            --tb=short
        ;;

    all)
        echo -e "${YELLOW}Esecuzione tutti i test RAG...${NC}"
        python -m pytest tests/test_rag_consistency.py -v \
            --tb=short \
            -x
        ;;

    *)
        # Assume sia un ID di test case specifico
        TEST_ID="$1"
        echo -e "${YELLOW}Esecuzione test case: ${TEST_ID}...${NC}"
        python -m pytest "tests/test_rag_consistency.py::TestRAGConsistency::test_rag_response[${TEST_ID}]" -v \
            --tb=long
        ;;
esac

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}=== Test completati con successo ===${NC}"
else
    echo -e "${RED}=== Test falliti (exit code: $EXIT_CODE) ===${NC}"
fi

exit $EXIT_CODE
