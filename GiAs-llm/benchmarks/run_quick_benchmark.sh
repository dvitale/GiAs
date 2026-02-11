#!/bin/bash

echo "==========================================="
echo "   GiAs-llm Quick Benchmark"
echo "==========================================="
echo ""

# Check if both backends are running
echo "🔍 Checking backends availability..."

LLAMACPP_OK=false
OLLAMA_OK=false

if curl -sf http://localhost:11435/health > /dev/null 2>&1; then
    echo "   ✅ Llama.cpp is running (port 11435)"
    LLAMACPP_OK=true
else
    echo "   ❌ Llama.cpp is NOT running (port 11435)"
    echo "      Start it with: ./start_llama-cpp.sh"
fi

if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "   ✅ Ollama is running (port 11434)"
    OLLAMA_OK=true
else
    echo "   ❌ Ollama is NOT running (port 11434)"
    echo "      Start it with: ollama serve"
fi

echo ""

if [ "$LLAMACPP_OK" = false ] && [ "$OLLAMA_OK" = false ]; then
    echo "❌ No backends available! Please start at least one backend."
    exit 1
fi

# Determine which backends to test
BACKENDS=""
if [ "$LLAMACPP_OK" = true ]; then
    BACKENDS="$BACKENDS llamacpp"
fi
if [ "$OLLAMA_OK" = true ]; then
    BACKENDS="$BACKENDS ollama"
fi

echo "🚀 Running quick benchmark..."
echo "   Backends: $BACKENDS"
echo "   Test cases: 10 representative"
echo "   Iterations: 1"
echo ""

# Run benchmark
python3 compare_llm_backends.py \
    --quick \
    --backends $BACKENDS \
    --output quick_benchmark.json

if [ $? -eq 0 ]; then
    echo ""
    echo "==========================================="
    echo "   Benchmark completed successfully!"
    echo "==========================================="
    echo ""
    echo "📊 Results saved to: quick_benchmark.json"
    echo ""
    echo "📈 Generate HTML report:"
    echo "   python3 visualize_benchmark.py quick_benchmark.json"
    echo ""
else
    echo ""
    echo "❌ Benchmark failed! Check the errors above."
    exit 1
fi
