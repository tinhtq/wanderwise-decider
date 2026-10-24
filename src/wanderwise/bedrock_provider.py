"""Amazon Bedrock model provider for the WanderWise agent.

The generative half of the agent (writing itineraries, talking to the user) runs
on Amazon Bedrock. Because our compute account denies ``bedrock:InvokeModel`` via
an SCP, we assume a role in a Bedrock-enabled account and hand the resulting
temporary credentials to the Strands ``BedrockModel`` via a boto3 session.

Set these in the environment (see ``.env``):
    AWS_REGION               e.g. us-east-1
    BEDROCK_MODEL_ID         e.g. us.anthropic.claude-haiku-5-5 (inference profile)
    BEDROCK_ASSUME_ROLE_ARN  cross-account role to assume (optional; if empty,
                             the instance's own credentials are used directly)
"""

from __future__ import annotations

import os

import boto3
from strands.models import BedrockModel


def _assumed_session(role_arn: str, region: str) -> boto3.Session:
    """Assume ``role_arn`` and return a boto3 session with the temp creds."""
    sts = boto3.client("sts", region_name=region)
    resp = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="wanderwise-bedrock",
        DurationSeconds=3600,
    )
    c = resp["Credentials"]
    return boto3.Session(
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
        region_name=region,
    )


def build_bedrock_model(
    model_id: str | None = None,
    region: str | None = None,
    assume_role_arn: str | None = None,
) -> BedrockModel:
    """Build a Strands ``BedrockModel``, assuming a cross-account role if given.

    Args and env fallbacks:
        model_id: BEDROCK_MODEL_ID
        region: AWS_REGION (default us-east-1)
        assume_role_arn: BEDROCK_ASSUME_ROLE_ARN (optional)
    """
    region = region or os.getenv("AWS_REGION", "us-east-1")
    model_id = model_id or os.getenv(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"
    )
    assume_role_arn = assume_role_arn or os.getenv("BEDROCK_ASSUME_ROLE_ARN", "")

    if assume_role_arn:
        session = _assumed_session(assume_role_arn, region)
    else:
        session = boto3.Session(region_name=region)

    # The session already carries the region; passing region_name too is rejected.
    return BedrockModel(
        model_id=model_id,
        boto_session=session,
    )
