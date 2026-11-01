from typing import Any

from aws_utils.client import get_client


class DynamoDBService:
    """
    Shared Amazon DynamoDB transport adapter.

    Conditional expressions and item schemas belong
    to the calling application repository.
    """

    def __init__(
        self,
        *,
        region_name: str | None = None,
        client: Any | None = None,
    ):
        if (
            region_name is not None
            and not isinstance(
                region_name,
                str,
            )
        ):
            raise TypeError(
                "region_name must be a string or "
                "None."
            )

        normalized_region = (
            region_name.strip()
            if region_name is not None
            else None
        )

        if (
            region_name is not None
            and not normalized_region
        ):
            raise ValueError(
                "region_name must not be blank "
                "when supplied."
            )

        self.region_name = normalized_region
        self._client = client

    @property
    def client(
        self,
    ) -> Any:
        """
        Lazily construct the DynamoDB client.
        """
        if self._client is None:
            self._client = get_client(
                "dynamodb",
                region_name=self.region_name,
            )

        return self._client

    def put_item(
        self,
        table_name: str,
        item: dict,
        condition_expression: (
            str
            | None
        ) = None,
        expression_attribute_names: (
            dict
            | None
        ) = None,
        expression_attribute_values: (
            dict
            | None
        ) = None,
        return_values: str = "NONE",
    ) -> dict:
        request: dict[str, Any] = {
            "TableName": table_name,
            "Item": item,
            "ReturnValues": return_values,
        }

        if condition_expression:
            request["ConditionExpression"] = (
                condition_expression
            )

        if expression_attribute_names:
            request[
                "ExpressionAttributeNames"
            ] = expression_attribute_names

        if expression_attribute_values:
            request[
                "ExpressionAttributeValues"
            ] = expression_attribute_values

        return self.client.put_item(
            **request
        )

    def get_item(
        self,
        table_name: str,
        key: dict,
        consistent_read: bool = True,
    ) -> dict | None:
        response = self.client.get_item(
            TableName=table_name,
            Key=key,
            ConsistentRead=consistent_read,
        )

        item = response.get(
            "Item"
        )

        if item is None:
            return None

        if not isinstance(
            item,
            dict,
        ):
            raise RuntimeError(
                "DynamoDB Item response must be "
                "a dictionary."
            )

        return item

    def update_item(
        self,
        table_name: str,
        key: dict,
        update_expression: str,
        condition_expression: (
            str
            | None
        ) = None,
        expression_attribute_names: (
            dict
            | None
        ) = None,
        expression_attribute_values: (
            dict
            | None
        ) = None,
        return_values: str = "ALL_NEW",
    ) -> dict:
        request: dict[str, Any] = {
            "TableName": table_name,
            "Key": key,
            "UpdateExpression": (
                update_expression
            ),
            "ReturnValues": return_values,
        }

        if condition_expression:
            request["ConditionExpression"] = (
                condition_expression
            )

        if expression_attribute_names:
            request[
                "ExpressionAttributeNames"
            ] = expression_attribute_names

        if expression_attribute_values:
            request[
                "ExpressionAttributeValues"
            ] = expression_attribute_values

        return self.client.update_item(
            **request
        )

    def delete_item(
        self,
        table_name: str,
        key: dict,
        condition_expression: (
            str
            | None
        ) = None,
        expression_attribute_names: (
            dict
            | None
        ) = None,
        expression_attribute_values: (
            dict
            | None
        ) = None,
        return_values: str = "NONE",
    ) -> dict:
        request: dict[str, Any] = {
            "TableName": table_name,
            "Key": key,
            "ReturnValues": return_values,
        }

        if condition_expression:
            request["ConditionExpression"] = (
                condition_expression
            )

        if expression_attribute_names:
            request[
                "ExpressionAttributeNames"
            ] = expression_attribute_names

        if expression_attribute_values:
            request[
                "ExpressionAttributeValues"
            ] = expression_attribute_values

        return self.client.delete_item(
            **request
        )