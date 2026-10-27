from mcp_scenarios import mcp_servers_get

ORDER = 47
OPERATION_ID = "mcp_servers_get"
MCP_REQUIRED = True

def run(context):
    mcp_servers_get(context)
