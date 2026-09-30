from abc import ABC, abstractmethod

import httpx


class VoiceProvider(ABC):
    @abstractmethod
    async def mint_token(self, expires_in_seconds: int, max_session_duration_seconds: int) -> dict:
        raise NotImplementedError


class AssemblyAIVoiceProvider(VoiceProvider):
    TOKEN_URL = "https://agents.assemblyai.com/v1/token"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def mint_token(self, expires_in_seconds: int, max_session_duration_seconds: int) -> dict:
        params = {
            "expires_in_seconds": expires_in_seconds,
            "max_session_duration_seconds": max_session_duration_seconds,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.TOKEN_URL, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
