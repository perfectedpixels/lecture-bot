#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { LectureBotStack } from '../lib/lecture-bot-stack';

const app = new cdk.App();
new LectureBotStack(app, 'LectureBotStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1'
  }
});
