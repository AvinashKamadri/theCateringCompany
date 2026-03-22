#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CateringStack } from '../lib/infra-stack';

const app = new cdk.App();
new CateringStack(app, 'CateringStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'us-east-1',
  },
});
