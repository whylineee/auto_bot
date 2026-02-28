from __future__ import annotations

import logging

import httpx


class LinkedInServiceError(Exception):
    pass


class LinkedInService:
    UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        logger: logging.Logger,
        timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._logger = logger
        self._timeout_seconds = timeout_seconds

    async def publish_post(self, text: str, access_token: str, person_id: str) -> str:
        access_token = access_token.strip()
        person_id = person_id.strip()
        if not access_token:
            raise LinkedInServiceError("LinkedIn access token is missing")
        if not person_id:
            raise LinkedInServiceError("LinkedIn person id is missing")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        payload = {
            "author": f"urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        try:
            response = await self._http_client.post(
                self.UGC_POSTS_URL,
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
            )
            self._logger.info("LinkedIn API status: %s", response.status_code)

            if response.status_code not in (201, 202):
                self._logger.error("LinkedIn API error body: %s", response.text)
                if response.status_code == 401:
                    raise LinkedInServiceError(
                        "LinkedIn access token is invalid or expired. Reconnect account via /linkedin_connect."
                    )
                raise LinkedInServiceError(
                    f"LinkedIn API returned status {response.status_code}: {response.text[:500]}"
                )

            post_urn = response.headers.get("x-restli-id", "")
            if not post_urn:
                data = response.json() if response.text else {}
                post_urn = str(data.get("id", ""))

            return post_urn or "published"
        except httpx.HTTPError as exc:
            self._logger.exception("LinkedIn API request failed")
            raise LinkedInServiceError(f"LinkedIn HTTP error: {exc}") from exc
