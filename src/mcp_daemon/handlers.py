import json
import re
from typing import Dict, Any, Optional, Tuple
from loguru import logger

from .models import MCPResponse, ServerSession

class RequestHandler:
    """Handles client requests to the MCP daemon"""
    def __init__(self, sessions: Dict[str, ServerSession]):
        self.sessions = sessions

    async def handle_request(self, message: str) -> Dict[str, Any]:
        """Process incoming client requests"""
        try:
            request = json.loads(message)
            request_type = request.get("type")
            
            handlers = {
                "execute_tool": self.handle_execute_tool,
                "list_servers": self.handle_list_servers,
                "list_server_tools": self.handle_list_server_tools,
                "list_server_resource_templates": self.handle_list_resource_templates,
                "list_server_resources": self.handle_list_server_resources
            }
            
            handler = handlers.get(request_type)
            if not handler:
                return MCPResponse(
                    status="error",
                    error=f"Unknown request type: {request_type}"
                ).to_dict()
                
            return await handler(request)
            
        except json.JSONDecodeError:
            return MCPResponse(
                status="error",
                error="Invalid JSON"
            ).to_dict()
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return MCPResponse(
                status="error",
                error=f"Error processing request: {str(e)}"
            ).to_dict()

    async def handle_execute_tool(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool"""
        server_name = request.get("server_name")
        tool_name = request.get("tool_name")
        arguments = request.get("arguments", {})
        
        if not all([server_name, tool_name]):
            return MCPResponse(
                status="error",
                error="Missing required fields (server_name, tool_name)"
            ).to_dict()
            
        if server_name not in self.sessions:
            return MCPResponse(
                status="error",
                error=f"MCP server '{server_name}' not found or not connected"
            ).to_dict()
            
        try:
            logger.info(f"Executing MCP tool '{tool_name}' on server '{server_name}'")
            result = await self.sessions[server_name].session.call_tool(tool_name, arguments)
            
            text_contents = []
            for item in result.content:
                if hasattr(item, 'type') and item.type == 'text':
                    text_contents.append(item.text)
                    
            return MCPResponse(
                status="success",
                content='\n'.join(text_contents) if text_contents else "No text content found in result"
            ).to_dict()
            
        except Exception as e:
            logger.error(f"Error executing MCP tool: {str(e)}")
            return MCPResponse(
                status="error",
                error=f"Error executing MCP tool: {str(e)}"
            ).to_dict()

    async def handle_list_servers(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List all connected MCP servers"""
        return MCPResponse(
            status="success",
            content=json.dumps(list(self.sessions.keys()))
        ).to_dict()

    async def handle_list_server_tools(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List tools available on a specific MCP server"""
        server_name = request.get("server_name")
        if not server_name:
            return MCPResponse(
                status="error",
                error="Missing server_name parameter"
            ).to_dict()
            
        if server_name not in self.sessions:
            return MCPResponse(
                status="error",
                error=f"Server '{server_name}' not found or not connected"
            ).to_dict()
            
        try:
            tools_response = await self.sessions[server_name].session.list_tools()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                for tool in tools_response.tools
            ] if tools_response.tools else []
            
            return MCPResponse(
                status="success",
                content=json.dumps(tools)
            ).to_dict()
            
        except Exception as e:
            return MCPResponse(
                status="error",
                error=f"Error listing tools: {str(e)}"
            ).to_dict()

    async def handle_list_resource_templates(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List resource templates available on a specific MCP server"""
        server_name = request.get("server_name")
        if not server_name:
            return MCPResponse(
                status="error",
                error="Missing server_name parameter"
            ).to_dict()
            
        if server_name not in self.sessions:
            return MCPResponse(
                status="error",
                error=f"Server '{server_name}' not found or not connected"
            ).to_dict()
            
        try:
            templates_response = await self.sessions[server_name].session.list_resource_templates()
            templates = [
                {
                    "uriTemplate": template.uriTemplate,
                    "name": template.name,
                    "description": template.description,
                    "mimeType": template.mimeType
                }
                for template in templates_response.resourceTemplates
            ] if templates_response.resourceTemplates else []
            
            return MCPResponse(
                status="success",
                content=json.dumps(templates)
            ).to_dict()
            
        except Exception as e:
            return MCPResponse(
                status="error",
                error=f"Error listing resource templates: {str(e)}"
            ).to_dict()

    async def handle_list_server_resources(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List resources available on a specific MCP server"""
        server_name = request.get("server_name")
        if not server_name:
            return MCPResponse(
                status="error",
                error="Missing server_name parameter"
            ).to_dict()
            
        if server_name not in self.sessions:
            return MCPResponse(
                status="error",
                error=f"Server '{server_name}' not found or not connected"
            ).to_dict()
            
        try:
            resources_response = await self.sessions[server_name].session.list_resources()
            resources = [
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mimeType
                }
                for resource in resources_response.resources
            ] if resources_response.resources else []
            
            return MCPResponse(
                status="success",
                content=json.dumps(resources)
            ).to_dict()
            
        except Exception as e:
            return MCPResponse(
                status="error",
                error=f"Error listing resources: {str(e)}"
            ).to_dict()
