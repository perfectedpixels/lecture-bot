import json
import boto3
import os
from datetime import datetime

s3_client = boto3.client('s3')

def handler(event, context):
    """
    Process uploaded lecture transcripts.
    Extracts metadata and prepares for indexing.
    """
    
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"Processing: s3://{bucket}/{key}")
        
        # Get file content
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        
        # Extract metadata
        metadata = {
            'source': key,
            'upload_time': datetime.now().isoformat(),
            'size': len(content),
            'type': 'lecture_transcript'
        }
        
        # Add metadata to S3 object
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={'Bucket': bucket, 'Key': key},
            Key=key,
            Metadata=metadata,
            MetadataDirective='REPLACE'
        )
        
        print(f"Processed {key} - {len(content)} characters")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete')
    }
