#!/bin/bash

echo "==========================================="
echo "   GiAs-llm Full Benchmark Suite"
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

# Generate timestamp for unique filenames
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
JSON_OUTPUT="benchmark_${TIMESTAMP}.json"
HTML_OUTPUT="benchmark_report_${TIMESTAMP}.html"

echo "🚀 Running full benchmark..."
echo "   Backends: $BACKENDS"
echo "   Test cases: 42 (all intents)"
echo "   Iterations: 3"
echo "   Output: $JSON_OUTPUT"
echo ""
echo "⏱️  Estimated time: 5-10 minutes"
echo "   (Please wait, this may take a while...)"
echo ""

# Run benchmark
python3 compare_llm_backends.py \
    --backends $BACKENDS \
    --iterations 3 \
    --output "$JSON_OUTPUT"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Benchmark failed! Check the errors above."
    exit 1
fi

echo ""
echo "==========================================="
echo "   Benchmark completed successfully!"
echo "==========================================="
echo ""
echo "📊 JSON Results: $JSON_OUTPUT"
echo ""
echo "📈 Generating HTML report..."

# Generate HTML report
python3 visualize_benchmark.py "$JSON_OUTPUT" --output "$HTML_OUTPUT"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ HTML Report: $HTML_OUTPUT"
    echo ""
    echo "🌐 Open in browser:"
    echo "   file://$(pwd)/$HTML_OUTPUT"
    echo ""
    echo "📋 Files generated:"
    echo "   - $JSON_OUTPUT (raw data)"
    echo "   - $HTML_OUTPUT (visual report)"
    echo ""
else
    echo ""
    echo "⚠️  HTML generation failed, but JSON results are available"
fi

echo "==========================================="
echo "   Benchmark suite completed!"
echo "==========================================="
