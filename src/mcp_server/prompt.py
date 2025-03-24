import json
from typing import Optional, Dict
from mcp import ClientSession
from config import prompt_service

async def format_server_info(sessions: Dict[str, ClientSession]) -> str:
    """Format MCP server information for the system prompt"""
    if not sessions:
        return "(No MCP servers currently connected)"

    server_sections = []

    for server_name, session in sessions.items():
        # Get server information
        tools_section = ""
        templates_section = ""
        resources_section = ""

        try:
            # Get and format tools section
            tools_response = await session.list_tools()
            if tools_response and tools_response.tools:
                tools = []
                for tool in tools_response.tools:
                    schema_str = ""
                    if tool.inputSchema:
                        schema_json = json.dumps(tool.inputSchema, indent=2)
                        schema_lines = schema_json.split("\n")
                        schema_str = "\n    Input Schema:\n    " + "\n    ".join(schema_lines)

                    tools.append(f"- {tool.name}: {tool.description}{schema_str}")
                tools_section = "\n\n### Available Tools\n" + "\n\n".join(tools)
        except Exception as e:
            print(f"Error listing tools for {server_name}: {str(e)}")

        try:
            # Get and format resource templates section
            templates_response = await session.list_resource_templates()
            if templates_response and templates_response.resourceTemplates:
                templates = []
                for template in templates_response.resourceTemplates:
                    templates.append(
                        f"- {template.uriTemplate} ({template.name}): {template.description}"
                    )
                templates_section = "\n\n### Resource Templates\n" + "\n".join(templates)
        except Exception as e:
            pass
            # print(f"Error listing resource templates for {server_name}: {str(e)}")

        try:
            # Get and format direct resources section
            resources_response = await session.list_resources()
            if resources_response and resources_response.resources:
                resources = []
                for resource in resources_response.resources:
                    resources.append(
                        f"- {resource.uri} ({resource.name}): {resource.description}"
                    )
                resources_section = "\n\n### Direct Resources\n" + "\n".join(resources)
        except Exception as e:
            pass
            # print(f"Error listing resources for {server_name}: {str(e)}")

        # Combine all sections
        server_section = (
            f"## {server_name}"
            f"{tools_section}"
            f"{templates_section}"
            f"{resources_section}"
        )
        server_sections.append(server_section)

    return "\n\n".join(server_sections)

async def get_mcp_prompt(mcp_client) -> str:
    """Generate the complete system prompt including MCP server information"""
    # check if sessions
    if not mcp_client.sessions:
        return None
    
    # Get formatted server information
    server_info = await format_server_info(mcp_client.sessions)
    if server_info:
        mcp_prompt = prompt_service.get_prompt("mcp")
        return mcp_prompt.content + server_info

    return None