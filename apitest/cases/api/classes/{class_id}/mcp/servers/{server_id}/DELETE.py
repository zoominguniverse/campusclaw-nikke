from mcp_scenarios import mcp_servers_delete

ORDER = 53
OPERATION_ID = "mcp_servers_delete"
MCP_REQUIRED = True

def run(context):
    mcp_servers_delete(context)
