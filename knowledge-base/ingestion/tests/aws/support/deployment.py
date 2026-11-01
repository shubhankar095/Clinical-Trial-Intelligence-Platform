from __future__ import annotations
import json, os, subprocess
from dataclasses import dataclass
from pathlib import Path
import boto3

@dataclass(frozen=True)
class AwsDeployment:
    region: str; account_id: str; environment: str; terraform_dir: Path
    queue_url: str; queue_arn: str; dlq_arn: str; dlq_url: str
    canonical_bucket: str; registry_table: str; ecs_cluster: str; ecs_service: str
    log_group: str; ecr_repository_url: str; image_uri: str
    opensearch_endpoint: str; collection_name: str; access_policy_name: str
    timeout: int
    @classmethod
    def load(cls) -> "AwsDeployment":
        terraform_dir=Path(os.getenv("TERRAFORM_DIR","infra"))
        data=json.loads(subprocess.run(["terraform",f"-chdir={terraform_dir}","output","-json"],check=True,capture_output=True,text=True).stdout)
        value=lambda name: data[name]["value"]
        region=os.environ["AWS_REGION"]; session=boto3.Session(region_name=region)
        sqs=session.client("sqs"); dlq_arn=value("ingestion_dlq_arn"); dlq_name=dlq_arn.rsplit(":",1)[-1]
        return cls(region,os.environ["AWS_ACCOUNT_ID"],os.getenv("ENVIRONMENT","dev"),terraform_dir,
          value("ingestion_queue_url"),value("ingestion_queue_arn"),dlq_arn,
          sqs.get_queue_url(QueueName=dlq_name)["QueueUrl"],value("canonical_bucket"),
          value("processing_registry_table"),value("ecs_cluster"),value("ecs_service_name"),
          value("cloudwatch_log_group"),value("ecr_repository_url"),value("ingestion_image_uri"),
          value("opensearch_collection_endpoint"),value("opensearch_collection_name"),
          value("opensearch_access_policy_name"),int(os.getenv("AWS_TEST_TIMEOUT","1200")))
    def client(self,name: str): return boto3.client(name,region_name=self.region)

########################################################################
