from mcp_scenarios import mcp_servers_list

ORDER = 46
OPERATION_ID = "mcp_servers_list"
MCP_REQUIRED = True

def run(context):
    mcp_servers_list(context)
