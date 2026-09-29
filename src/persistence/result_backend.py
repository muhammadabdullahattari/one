import json
from typing import Any
from uuid import UUID

from src.core.config import get_settings


class ResultBackend:
    def __init__(self, size_threshold_bytes: int = 65536) -> None:
        self.size_threshold_bytes = size_threshold_bytes
        self.settings = get_settings()

    async def store_result(
        self, task_id: UUID, result_data: Any
    ) -> tuple[dict[str, Any] | None, str | None]:
        if result_data is None:
            return (None, None)
        serialized = json.dumps(result_data, default=str)
        payload_size = len(serialized.encode("utf-8"))
        if payload_size <= self.size_threshold_bytes:
            if isinstance(result_data, dict):
                return (result_data, None)
            return ({"return_value": result_data}, None)
        storage_key = f"results/{task_id}.json"
        if self.settings.s3_endpoint_url and self.settings.s3_access_key_id:
            import boto3

            s3 = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.s3_access_key_id,
                aws_secret_access_key=self.settings.s3_secret_access_key,
                region_name=self.settings.s3_region,
            )
            s3.put_object(
                Bucket=self.settings.s3_bucket_name,
                Key=storage_key,
                Body=serialized.encode("utf-8"),
                ContentType="application/json",
            )
            return (None, f"s3://{self.settings.s3_bucket_name}/{storage_key}")
        if isinstance(result_data, dict):
            return (result_data, None)
        return ({"return_value": result_data}, None)
