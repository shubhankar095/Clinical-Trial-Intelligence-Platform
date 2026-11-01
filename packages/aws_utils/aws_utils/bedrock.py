from typing import Any

from aws_utils.client import get_client


class BedrockRuntimeService:
    """
    Shared Amazon Bedrock Runtime transport adapter.

    Model-specific payload creation and response
    parsing belong to the calling model adapter.
    """

    def __init__(
        self,
        region_name: str | None = None,
        client: Any | None = None,
    ):
        if region_name is not None and not isinstance(region_name, str):
            raise TypeError( "region_name must be a string or None.")

        normalized_region_name = region_name.strip() if region_name is not None else None
        
        if region_name is not None and not normalized_region_name :
            raise ValueError("region_name must not be blank when supplied.")

        self.region_name = normalized_region_name

        self._client = client

    @property
    def client(self) -> Any:
        """
        Lazily create the Bedrock Runtime client.
        """
        if self._client is None:
            self._client = get_client("bedrock-runtime", region_name=(self.region_name))

        return self._client

    def invoke_model(
        self,
        *,
        model_id: str,
        body: str | bytes,
        accept: str = "application/json",
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        """
        Invoke a Bedrock model using its native
        request and response format.
        """
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be a nonblank string.")

        if not isinstance(body, (str, bytes)):
            raise TypeError("body must be a string or bytes.")

        if not isinstance(accept, str) or not accept.strip():
            raise ValueError("accept must be a nonblank string.")

        if not isinstance(content_type, str) or not content_type.strip():
            raise ValueError("content_type must be a nonblank string.")

        return self.client.invoke_model(
            modelId=model_id.strip(),
            body=body,
            accept=accept.strip(),
            contentType=content_type.strip()
        )