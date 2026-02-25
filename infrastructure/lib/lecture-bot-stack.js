"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.LectureBotStack = void 0;
const cdk = __importStar(require("aws-cdk-lib"));
const s3 = __importStar(require("aws-cdk-lib/aws-s3"));
const iam = __importStar(require("aws-cdk-lib/aws-iam"));
const lambda = __importStar(require("aws-cdk-lib/aws-lambda"));
const s3n = __importStar(require("aws-cdk-lib/aws-s3-notifications"));
class LectureBotStack extends cdk.Stack {
    constructor(scope, id, props) {
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
        lectureBucket.addEventNotification(s3.EventType.OBJECT_CREATED, new s3n.LambdaDestination(processorFunction), { suffix: '.txt' });
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
exports.LectureBotStack = LectureBotStack;
