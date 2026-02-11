#!/bin/bash
time curl -X  POST http://localhost:5005/webhooks/rest/webhook \
      -H "Content-Type: application/json" \
      -d '{"sender": "test", "message": "Quale piano è  più frequente nei controlli ufficiali della mia asl?", "metadata": {"asl": "AVELLINO"}}'

