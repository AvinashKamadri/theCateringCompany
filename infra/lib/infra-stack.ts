import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export class CateringStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // ── VPC ────────────────────────────────────────────────────────────────
    // Use default VPC — no NAT gateway cost
    const vpc = ec2.Vpc.fromLookup(this, 'DefaultVpc', { isDefault: true });

    // ── Security Group for RDS ─────────────────────────────────────────────
    const rdsSg = new ec2.SecurityGroup(this, 'RdsSg', {
      vpc,
      description: 'CateringCompany RDS - allow Postgres from VPC',
      allowAllOutbound: false,
    });

    rdsSg.addIngressRule(
      ec2.Peer.ipv4(vpc.vpcCidrBlock),
      ec2.Port.tcp(5432),
      'Postgres from VPC',
    );

    // ── RDS PostgreSQL 16 ──────────────────────────────────────────────────
    const db = new rds.DatabaseInstance(this, 'Database', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_16,
      }),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MICRO,
      ),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      securityGroups: [rdsSg],
      databaseName: 'cateringco_prod',
      credentials: rds.Credentials.fromGeneratedSecret('cateringco', {
        secretName: 'catering/rds',
      }),
      allocatedStorage: 20,
      storageType: rds.StorageType.GP2,
      multiAz: false,
      deletionProtection: false,
      removalPolicy: cdk.RemovalPolicy.SNAPSHOT,
      backupRetention: cdk.Duration.days(7),
      publiclyAccessible: false,
    });

    // ── S3 Bucket ──────────────────────────────────────────────────────────
    const uploadsBucket = new s3.Bucket(this, 'UploadsBucket', {
      bucketName: `catering-uploads-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      cors: [
        {
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.PUT,
            s3.HttpMethods.POST,
            s3.HttpMethods.DELETE,
          ],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
        },
      ],
    });

    // ── Outputs ────────────────────────────────────────────────────────────
    new cdk.CfnOutput(this, 'RdsEndpoint', {
      value: db.instanceEndpoint.hostname,
      description: 'Paste into DATABASE_URL in .env.pp1',
    });

    new cdk.CfnOutput(this, 'RdsSecretArn', {
      value: db.secret!.secretArn,
      description: 'Retrieve RDS password from AWS Secrets Manager',
    });

    new cdk.CfnOutput(this, 'S3BucketName', {
      value: uploadsBucket.bucketName,
      description: 'Paste into R2_BUCKET in .env.pp1',
    });
  }
}
