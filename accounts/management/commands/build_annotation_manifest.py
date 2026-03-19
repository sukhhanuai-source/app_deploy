import json
import os
from pathlib import PurePosixPath

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.core.management.base import BaseCommand, CommandError


def _env(name, default=''):
    return os.environ.get(name, default)


def _s3_client():
    aws_access_key_id = _env('AWS_ACCESS_KEY_ID') or _env('AWS_S3_ACCESS_KEY_ID')
    aws_secret_access_key = _env('AWS_SECRET_ACCESS_KEY') or _env('AWS_S3_SECRET_ACCESS_KEY')
    aws_session_token = _env('AWS_SESSION_TOKEN') or _env('AWS_S3_SESSION_TOKEN')
    endpoint_url = _env('S3_ENDPOINT_URL') or _env('AWS_S3_ENDPOINT_URL') or None
    region_name = _env('AWS_REGION') or _env('AWS_DEFAULT_REGION') or _env('AWS_S3_REGION_NAME') or 'us-east-1'

    if not aws_access_key_id or not aws_secret_access_key:
        raise CommandError('AWS credentials are required (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).')

    client_kwargs = {
        'aws_access_key_id': aws_access_key_id,
        'aws_secret_access_key': aws_secret_access_key,
        'region_name': region_name,
    }
    if aws_session_token:
        client_kwargs['aws_session_token'] = aws_session_token
    if endpoint_url:
        client_kwargs['endpoint_url'] = endpoint_url
    return boto3.client('s3', **client_kwargs)


def _iter_json_keys(s3, bucket, prefix):
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.lower().endswith('.json'):
                continue
            yield key


def _load_labels(payload):
    labels = []
    for shape in payload.get('shapes', []):
        label = shape.get('label')
        if label:
            labels.append(str(label))
    return sorted(set(labels))


class Command(BaseCommand):
    help = "Builds an annotation manifest JSON in S3 with paths and labels."

    def add_arguments(self, parser):
        parser.add_argument('--bucket', default=_env('ANNOTATION_MANIFEST_BUCKET', 'amzn-ra-databucket'))
        parser.add_argument('--prefix', default=_env('ANNOTATION_MANIFEST_PREFIX', 'hanuai/'))
        parser.add_argument('--output-key', default=_env('ANNOTATION_MANIFEST_KEY', 'hanuai/annotated_manifest.json'))
        parser.add_argument('--max', type=int, default=0, help='Optional limit of JSON files to process (0 = no limit).')

    def handle(self, *args, **options):
        bucket = options['bucket'].strip()
        prefix = options['prefix'].lstrip('/')
        output_key = options['output_key'].lstrip('/')
        max_items = options['max']

        if not bucket:
            raise CommandError('Bucket is required.')
        if not prefix:
            prefix = ''

        s3 = _s3_client()

        manifest = []
        processed = 0

        for key in _iter_json_keys(s3, bucket, prefix):
            if key == output_key:
                continue  # skip the manifest itself
            if max_items and processed >= max_items:
                break

            try:
                obj = s3.get_object(Bucket=bucket, Key=key)
                payload = json.loads(obj['Body'].read().decode('utf-8'))
            except (ClientError, BotoCoreError, json.JSONDecodeError, UnicodeDecodeError):
                continue

            labels = _load_labels(payload)
            record = {
                'annotation_s3_uri': f's3://{bucket}/{key}',
                'annotation_name': PurePosixPath(key).name,
                'labels': labels,
            }
            manifest.append(record)
            processed += 1

        try:
            s3.put_object(
                Bucket=bucket,
                Key=output_key,
                Body=json.dumps(manifest, indent=2, sort_keys=True).encode('utf-8'),
                ContentType='application/json',
            )
        except (ClientError, BotoCoreError, ValueError, TypeError) as exc:
            raise CommandError(f"Failed to write manifest: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(manifest)} records to s3://{bucket}/{output_key}"))
