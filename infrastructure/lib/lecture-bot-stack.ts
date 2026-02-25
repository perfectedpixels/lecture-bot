import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import { Construct } from 'constructs';

export class LectureBotStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket for lecture transcripts
    const lectureBucket = new s3.Bucket(this, 'LectureBucket', {
      bucketName: `lecture-transcripts-${this.account}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // IAM role for Bedrock Knowledge Base
    const bedrockKbRole = new iam.Role(this, 'BedrockKBRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Role for Bedrock Knowledge Base to access S3',
    });

    lectureBucket.grantRead(bedrockKbRole);

    bedrockKbRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream'
      ],
      resources: ['*'],
    }));

    // Lambda for processing uploads
    const processorFunction = new lambda.Function(this, 'TranscriptProcessor', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('../src/lambda/processor'),
      environment: {
        BUCKET_NAME: lectureBucket.bucketName,
      },
      timeout: cdk.Duration.minutes(5),
    });

    lectureBucket.grantReadWrite(processorFunction);

    // Trigger Lambda on new uploads
    lectureBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(processorFunction),
      { suffix: '.txt' }
    );

    // Outputs
    new cdk.CfnOutput(this, 'BucketName', {
      value: lectureBucket.bucketName,
      description: 'S3 bucket for lecture transcripts',
    });

    new cdk.CfnOutput(this, 'BedrockRoleArn', {
      value: bedrockKbRole.roleArn,
      description: 'IAM role ARN for Bedrock Knowledge Base',
    });
  }
}
