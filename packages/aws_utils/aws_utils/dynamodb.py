from aws_utils.client import get_client


class DynamoDBService:

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = get_client(
                "dynamodb"
            )

        return self._client

    def put_item(
        self,
        table_name: str,
        item: dict,
        condition_expression: str | None = None,
        expression_attribute_names: dict | None = None,
        expression_attribute_values: dict | None = None,
    ) -> dict:
        request = {
            "TableName": table_name,
            "Item": item,
        }

        if condition_expression:
            request[
                "ConditionExpression"
            ] = condition_expression

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

        return response.get(
            "Item"
        )

    def update_item(
        self,
        table_name: str,
        key: dict,
        update_expression: str,
        condition_expression: str,
        expression_attribute_names: dict,
        expression_attribute_values: dict,
    ) -> dict:
        return self.client.update_item(
            TableName=table_name,
            Key=key,
            UpdateExpression=(
                update_expression
            ),
            ConditionExpression=(
                condition_expression
            ),
            ExpressionAttributeNames=(
                expression_attribute_names
            ),
            ExpressionAttributeValues=(
                expression_attribute_values
            ),
            ReturnValues="ALL_NEW",
        )

    def delete_item(
        self,
        table_name: str,
        key: dict,
        condition_expression: str,
        expression_attribute_names: dict,
        expression_attribute_values: dict,
    ) -> dict:
        return self.client.delete_item(
            TableName=table_name,
            Key=key,
            ConditionExpression=(
                condition_expression
            ),
            ExpressionAttributeNames=(
                expression_attribute_names
            ),
            ExpressionAttributeValues=(
                expression_attribute_values
            ),
        )