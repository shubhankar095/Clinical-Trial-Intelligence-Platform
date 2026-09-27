import boto3


def get_client(
    service_name: str,
    region_name: str | None = None
):
    """
    Create and return a boto3 client.

    Examples:
        get_client("s3")
        get_client("textract")
        get_client("bedrock-runtime")
    """

    kwargs = {}

    if region_name:
        kwargs["region_name"] = region_name

    return boto3.client(
        service_name,
        **kwargs
    )