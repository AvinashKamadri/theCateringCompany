import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
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

    // ── EC2 Security Group ─────────────────────────────────────────────────
    const ec2Sg = new ec2.SecurityGroup(this, 'Ec2Sg', {
      vpc,
      description: 'CateringCompany EC2 app server',
      allowAllOutbound: true,
    });
    ec2Sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22),   'SSH');
    ec2Sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(3001), 'Backend API');
    ec2Sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(8000), 'ML Agent');

    // Allow EC2 to reach RDS
    rdsSg.addIngressRule(ec2Sg, ec2.Port.tcp(5432), 'EC2 to RDS');

    // ── IAM Role for EC2 (S3 access) ───────────────────────────────────────
    const ec2Role = new iam.Role(this, 'Ec2Role', {
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore'),
      ],
    });
    uploadsBucket.grantReadWrite(ec2Role);

    // ── SSH Key Pair ───────────────────────────────────────────────────────
    const keyPair = new ec2.KeyPair(this, 'KeyPair', {
      keyPairName: 'catering-ec2-key',
    });

    // ── EC2 Instance ───────────────────────────────────────────────────────
    const userData = ec2.UserData.forLinux();
    userData.addCommands(
      'apt-get update -y',
      'curl -fsSL https://get.docker.com | sh',
      'usermod -aG docker ubuntu',
      'systemctl enable docker',
      'systemctl start docker',
      'git clone https://github.com/AvinashKamadri/theCateringCompany.git /home/ubuntu/app',
      'cd /home/ubuntu/app && git checkout deploy',
      'chown -R ubuntu:ubuntu /home/ubuntu/app',
    );

    const instance = new ec2.Instance(this, 'AppServer', {
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      machineImage: ec2.MachineImage.fromSsmParameter(
        '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id',
      ),
      securityGroup: ec2Sg,
      role: ec2Role,
      keyPair,
      userData,
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

    new cdk.CfnOutput(this, 'Ec2PublicIp', {
      value: instance.instancePublicIp,
      description: 'EC2 public IP — use in Vercel env vars and SSH',
    });

    new cdk.CfnOutput(this, 'SshKeyName', {
      value: keyPair.keyPairName,
      description: 'Key pair name — download .pem from EC2 console to SSH in',
    });
  }
}
