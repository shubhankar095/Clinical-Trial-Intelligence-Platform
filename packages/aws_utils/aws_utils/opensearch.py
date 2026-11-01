from typing import Any
from urllib.parse import urlparse

import boto3

from opensearchpy import (
    OpenSearch,
    RequestsAWSV4SignerAuth,
    RequestsHttpConnection,
)


class OpenSearchService:
    """
    Shared AWS OpenSearch transport adapter.

    This service owns:

    - AWS credential resolution
    - AWS Signature Version 4 authentication
    - OpenSearch client construction
    - OpenSearch data-plane transport operations

    Index naming, mappings, document serialization,
    reindexing rules, and retrieval behavior belong
    to the calling application adapter.
    """

    SERVERLESS_DEPLOYMENT = "serverless"
    DOMAIN_DEPLOYMENT = "domain"

    SIGV4_SERVICE_NAMES = {
        SERVERLESS_DEPLOYMENT: "aoss",
        DOMAIN_DEPLOYMENT: "es",
    }

    SUPPORTED_DEPLOYMENT_TYPES = frozenset(
        SIGV4_SERVICE_NAMES
    )

    def __init__(
        self,
        *,
        deployment_type: str,
        endpoint: str,
        region_name: str,
        client: Any | None = None,
    ):
        normalized_deployment_type = (
            self._normalize_required_string(
                value=deployment_type,
                field_name="deployment_type",
            )
            .lower()
        )

        if (
            normalized_deployment_type
            not in self
            .SUPPORTED_DEPLOYMENT_TYPES
        ):
            supported_types = ", ".join(
                sorted(
                    self
                    .SUPPORTED_DEPLOYMENT_TYPES
                )
            )

            raise ValueError(
                "Unsupported OpenSearch "
                "deployment_type "
                f"'{normalized_deployment_type}'. "
                "Supported deployment types: "
                f"{supported_types}."
            )

        self.deployment_type = (
            normalized_deployment_type
        )

        self.endpoint = (
            self._normalize_required_string(
                value=endpoint,
                field_name="endpoint",
            )
        )

        self.region_name = (
            self._normalize_required_string(
                value=region_name,
                field_name="region_name",
            )
        )

        self._client = client

    @property
    def client(
        self,
    ) -> Any:
        """
        Lazily construct the OpenSearch client.

        Creating the service does not immediately
        resolve AWS credentials or contact AWS.
        """
        if self._client is None:
            self._client = (
                self._build_client()
            )

        return self._client

    def _build_client(
        self,
    ) -> OpenSearch:
        """
        Build an AWS SigV4-authenticated OpenSearch
        data-plane client.

        Serverless uses SigV4 service name 'aoss'.
        Provisioned domains use service name 'es'.
        """
        host = self._parse_endpoint(
            self.endpoint
        )

        credentials = (
            boto3.Session()
            .get_credentials()
        )

        if credentials is None:
            raise RuntimeError(
                "AWS credentials are required "
                "for Amazon OpenSearch access."
            )

        service_name = (
            self.SIGV4_SERVICE_NAMES[
                self.deployment_type
            ]
        )

        authentication = (
            RequestsAWSV4SignerAuth(
                credentials,
                self.region_name,
                service_name,
            )
        )

        return OpenSearch(
            hosts=[
                {
                    "host": host,
                    "port": 443,
                }
            ],
            http_auth=authentication,
            use_ssl=True,
            verify_certs=True,
            ssl_assert_hostname=True,
            ssl_show_warn=False,
            connection_class=(
                RequestsHttpConnection
            ),
            http_compress=True,
            timeout=60,
            max_retries=3,
            retry_on_timeout=True,
            pool_maxsize=20,
        )

    def index_exists(
        self,
        *,
        index_name: str,
    ) -> bool:
        """
        Return whether an OpenSearch index exists.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        return bool(
            self.client.indices.exists(
                index=normalized_index_name
            )
        )

    def create_index(
        self,
        *,
        index_name: str,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create an OpenSearch index.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        if not isinstance(
            definition,
            dict,
        ):
            raise TypeError(
                "definition must be a dictionary."
            )

        if not definition:
            raise ValueError(
                "definition must not be empty."
            )

        response = (
            self.client.indices.create(
                index=normalized_index_name,
                body=definition,
            )
        )

        return self._require_response_object(
            response=response,
            operation="create index",
        )

    def get_index_mapping(
        self,
        *,
        index_name: str,
    ) -> dict[str, Any]:
        """
        Return the mapping for one OpenSearch index.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        response = (
            self.client.indices.get_mapping(
                index=normalized_index_name
            )
        )

        return self._require_response_object(
            response=response,
            operation="get index mapping",
        )

    def bulk(
        self,
        *,
        operations: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:
        """
        Execute one OpenSearch bulk request.
        """
        if not isinstance(
            operations,
            list,
        ):
            raise TypeError(
                "operations must be a list."
            )

        if not operations:
            raise ValueError(
                "operations must not be empty."
            )

        response = self.client.bulk(
            body=operations,
        )

        return self._require_response_object(
            response=response,
            operation="bulk indexing",
        )

    def refresh_index(
        self,
        *,
        index_name: str,
    ) -> dict[str, Any]:
        """
        Refresh one OpenSearch index.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        response = (
            self.client.indices.refresh(
                index=normalized_index_name
            )
        )

        return self._require_response_object(
            response=response,
            operation="refresh index",
        )

    def count(
        self,
        *,
        index_name: str,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Count documents matching an OpenSearch
        query.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        if not isinstance(
            query,
            dict,
        ):
            raise TypeError(
                "query must be a dictionary."
            )

        if not query:
            raise ValueError(
                "query must not be empty."
            )

        response = self.client.count(
            index=normalized_index_name,
            body=query,
        )

        return self._require_response_object(
            response=response,
            operation="count documents",
        )

    def search(
        self,
        *,
        index_name: str,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute one OpenSearch search query.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        if not isinstance(
            query,
            dict,
        ):
            raise TypeError(
                "query must be a dictionary."
            )

        if not query:
            raise ValueError(
                "query must not be empty."
            )

        response = self.client.search(
            index=normalized_index_name,
            body=query,
        )

        return self._require_response_object(
            response=response,
            operation="search",
        )

    def delete_by_query(
        self,
        *,
        index_name: str,
        query: dict[str, Any],
        refresh: bool,
        conflicts: str = "proceed",
    ) -> dict[str, Any]:
        """
        Delete documents matching an OpenSearch
        query.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        if not isinstance(
            query,
            dict,
        ):
            raise TypeError(
                "query must be a dictionary."
            )

        if not query:
            raise ValueError(
                "query must not be empty."
            )

        if not isinstance(
            refresh,
            bool,
        ):
            raise TypeError(
                "refresh must be a boolean."
            )

        normalized_conflicts = (
            self._normalize_required_string(
                value=conflicts,
                field_name="conflicts",
            )
        )

        response = (
            self.client.delete_by_query(
                index=normalized_index_name,
                body=query,
                refresh=refresh,
                conflicts=(
                    normalized_conflicts
                ),
            )
        )

        return self._require_response_object(
            response=response,
            operation="delete by query",
        )

    def delete_index(
        self,
        *,
        index_name: str,
    ) -> dict[str, Any]:
        """
        Delete one OpenSearch index.
        """
        normalized_index_name = (
            self._normalize_required_string(
                value=index_name,
                field_name="index_name",
            )
        )

        response = (
            self.client.indices.delete(
                index=normalized_index_name
            )
        )

        return self._require_response_object(
            response=response,
            operation="delete index",
        )

    @staticmethod
    def _require_response_object(
        *,
        response: Any,
        operation: str,
    ) -> dict[str, Any]:
        """
        Validate an OpenSearch response object.
        """
        if not isinstance(
            response,
            dict,
        ):
            raise RuntimeError(
                "Amazon OpenSearch "
                f"{operation} response must be "
                "an object."
            )

        return response

    @staticmethod
    def _parse_endpoint(
        endpoint: str,
    ) -> str:
        """
        Parse an AWS OpenSearch endpoint supplied as
        a host name or HTTPS URL.
        """
        normalized_endpoint = (
            endpoint.strip()
        )

        if "://" not in normalized_endpoint:
            normalized_endpoint = f"https://{normalized_endpoint}"

        parsed_endpoint = urlparse(normalized_endpoint)

        if parsed_endpoint.scheme != "https":
            raise ValueError(
                "Amazon OpenSearch endpoint must "
                "use HTTPS."
            )

        if not parsed_endpoint.hostname:
            raise ValueError(
                "Amazon OpenSearch endpoint does "
                "not contain a valid host."
            )

        if parsed_endpoint.path not in {
            "",
            "/",
        }:
            raise ValueError(
                "Amazon OpenSearch endpoint must "
                "not contain a path."
            )

        if (
            parsed_endpoint.query
            or parsed_endpoint.fragment
        ):
            raise ValueError(
                "Amazon OpenSearch endpoint must "
                "not contain a query or fragment."
            )

        if parsed_endpoint.port not in {
            None,
            443,
        }:
            raise ValueError(
                "Amazon OpenSearch endpoint must "
                "use port 443."
            )

        return parsed_endpoint.hostname

    @staticmethod
    def _normalize_required_string(
        *,
        value: str,
        field_name: str,
    ) -> str:
        """
        Validate and normalize one required string.
        """
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"{field_name} must be a string."
            )

        normalized_value = (
            value.strip()
        )

        if not normalized_value:
            raise ValueError(
                f"{field_name} must not be blank."
            )

        return normalized_value