#!/bin/bash
source /opt/lang-env/bin/activate 
cd /opt/lang-env/GiAs-llm/ && ./stop_server.sh
cd /opt/lang-env/GiAs-llm/ && python3 tools/indexing/build_docs_index.py
cd /opt/lang-env/GiAs-llm && python scripts/sync_domande_risposte.py
cd /opt/lang-env/GiAs-llm/ && scripts/server.sh restart
/opt/lang-env/gchat/all.sh
