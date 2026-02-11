#!/bin/bash
"""
Script per applicare tutti i fix necessari sul server cloud
"""

echo "🔧 APPLYING CLOUD SERVER FIXES..."
echo "=================================="

cd "$(dirname "${BASH_SOURCE[0]}")"

# Fix 1: data_agent.py column mapping
echo "1. Fixing data_agent.py column mapping..."
sed -i "s/delayed\['piano'\]/delayed['indicatore']/g" agents/agents/data_agent.py
echo "   ✅ Fixed 'piano' -> 'indicatore' in data_agent.py"

# Fix 2: priority_tools.py column references
echo "2. Fixing priority_tools.py column references..."
sed -i "s/groupby('piano')/groupby('indicatore')/g" tools/priority_tools.py
sed -i "s/piano_summary\['piano'\]/piano_summary['indicatore']/g" tools/priority_tools.py
sed -i "s/delayed_df\['piano'\]/delayed_df['indicatore']/g" tools/priority_tools.py
sed -i "s/piano_match\['piano'\]/piano_match['indicatore']/g" tools/priority_tools.py
echo "   ✅ Fixed all 'piano' -> 'indicatore' references in priority_tools.py"

# Fix 3: Verify all fixes applied
echo "3. Verifying fixes applied..."
REMAINING_PIANO=$(grep -r "piano\]" tools/priority_tools.py agents/agents/data_agent.py 2>/dev/null || true)
if [ -n "$REMAINING_PIANO" ]; then
    echo "   ⚠️ Some 'piano' references still found:"
    echo "$REMAINING_PIANO"
else
    echo "   ✅ All 'piano' column references fixed"
fi

# Fix 4: Set environment variable
echo "4. Setting LLM model environment variable..."
export GIAS_LLM_MODEL=llama3.2
echo "export GIAS_LLM_MODEL=llama3.2" >> ~/.bashrc
echo "   ✅ Set GIAS_LLM_MODEL=llama3.2"

# Fix 5: Test fixes
echo "5. Testing fixes..."
python3 -c "
try:
    from tools.risk_tools import risk_tool
    result = risk_tool(asl='NA1')
    if 'piano' in str(result.get('error', '')):
        print('   ❌ risk_tool still has piano error')
    else:
        print('   ✅ risk_tool fixed')
except Exception as e:
    print(f'   ❌ risk_tool error: {e}')

try:
    from tools.priority_tools import priority_tool
    result = priority_tool(asl='NA1', uoc='SEPE', action='priority')
    if 'piano' in str(result.get('error', '')):
        print('   ❌ priority_tool still has piano error')
    else:
        print('   ✅ priority_tool fixed')
except Exception as e:
    print(f'   ❌ priority_tool error: {e}')
"

echo ""
echo "=================================="
echo "🎯 FIXES APPLIED SUCCESSFULLY"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Restart the GiAs-llm server: ./start_server.sh"
echo "2. Test with GChat: 'Sulla base del rischio storico chi dovrei controllare per primo?'"
echo ""