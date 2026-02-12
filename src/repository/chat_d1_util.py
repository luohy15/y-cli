import json
from typing import Any, Dict, List, Optional, Union
import httpx
from config import config


class PreparedStatement:
    """A prepared SQL statement that can be executed with bound parameters"""

    def __init__(self, d1_client, sql: str):
        self.d1_client = d1_client
        self.sql = sql
        self.params = []

    def bind(self, *args) -> 'PreparedStatement':
        self.params = list(args)
        return self

    async def first(self) -> Optional[Dict[str, Any]]:
        result = await self.all()
        if isinstance(result, dict):
            if not result or not result.get('results') or len(result['results']) == 0:
                return None
            return result['results'][0]
        elif isinstance(result, list):
            if not result:
                return None
            return result[0]
        else:
            return None

    async def all(self) -> Dict[str, Any]:
        return await self.d1_client._execute_prepared(self.sql, self.params, 'query')

    async def run(self) -> Dict[str, Any]:
        return await self.d1_client._execute_prepared(self.sql, self.params, 'query')


class D1Database:
    """Client for interacting with Cloudflare D1 database"""

    def __init__(self, account_id: Optional[str] = None, database_id: Optional[str] = None, api_token: Optional[str] = None):
        self.account_id = account_id or config.get('cloudflare_d1', {}).get('account_id')
        self.api_token = api_token or config.get('cloudflare_d1', {}).get('api_token')
        self.database_id = database_id or config.get('cloudflare_d1', {}).get('database_id')

        if not all([self.account_id, self.api_token, self.database_id]):
            raise ValueError("Cloudflare D1 configuration is incomplete. Please check your config.")

        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.database_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    async def exec(self, sql: str) -> Dict[str, Any]:
        url = f"{self.base_url}/query"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json={"sql": sql})
            response.raise_for_status()
            result = response.json()
            if not result.get('success', False):
                errors = result.get('errors', [])
                error_msg = '; '.join([err.get('message', 'Unknown error') for err in errors]) if errors else 'Unknown error'
                raise RuntimeError(f"D1 execution failed: {error_msg}")
            return result.get('result', {})

    def prepare(self, sql: str) -> PreparedStatement:
        return PreparedStatement(self, sql)

    async def _execute_prepared(self, sql: str, params: List[Any], mode: str = 'query') -> Dict[str, Any]:
        url = f"{self.base_url}/{mode}"
        processed_params = []
        for param in params:
            if isinstance(param, (dict, list)):
                processed_params.append(json.dumps(param))
            else:
                processed_params.append(param)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=self.headers,
                json={"sql": sql, "params": processed_params}
            )
            try:
                response.raise_for_status()
                result = response.json()
                if not result.get('success', False):
                    errors = result.get('errors', [])
                    error_msg = '; '.join([err.get('message', 'Unknown error') for err in errors]) if errors else 'Unknown error'
                    raise RuntimeError(f"D1 execution failed: {error_msg}")
                return result.get('result', {})
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                try:
                    error_json = e.response.json()
                    if 'errors' in error_json:
                        error_detail = '; '.join([err.get('message', 'Unknown error') for err in error_json['errors']])
                except:
                    pass
                raise RuntimeError(f"D1 API error: {e.response.status_code}, {error_detail}")
