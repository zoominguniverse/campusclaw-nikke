from mcp_scenarios import mcp_tool_calls_list

ORDER = 52
OPERATION_ID = "mcp_tool_calls_list"
MCP_REQUIRED = True

def run(context):
    mcp_tool_calls_list(context)
