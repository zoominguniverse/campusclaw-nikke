from mcp_scenarios import mcp_servers_update

ORDER = 48
OPERATION_ID = "mcp_servers_update"
MCP_REQUIRED = True

def run(context):
    mcp_servers_update(context)
