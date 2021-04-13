# shared-alb-by-tag

in AWS Loadbalancers are quite cost-intensive. If you are in a non-production environment, you probably do not need one LB for each (micro-)service.
This lambda function automatically adds ec2 instances to a targetgroup & adds a host-header-based rule to a single shared ALB

:zap: the ALB is designed to redirect all traffic from http port 80 to https port 443

## installation

0. create a IAM role for your lambda with the permissions below
1. choose `Python 3.8` as Runtime
2. create & select your IAM Role with the policys listed below
3. Choose your VPC in "Advanced settings"
4. ensure this lambda will not run concurrently


### IAM policies required for this lambda

attach these AWS-managed policies to your 
* required; create/update ALB and targetgroups   
  `arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess`
* required; reading ec2 tags    
  `arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess`
* required; create Route53 records for vhost     
  `arn:aws:iam::aws:policy/AmazonRoute53FullAccess`
* a policy to allow upload of logs to cloudwatch logs; modify and use [policy.json](policy.json)
* optional; to read VPC details from cloudformation exports:     
  `arn:aws:iam::aws:policy/AWSCloudFormationReadOnlyAccess` 

## usage

simply add follwoing tags to your EC2 instances and run the lambda function

| key              | value                 | 
| ---------------- | --------------------- |
|`SharedALB`       | `public` or `internal`|
|`SharedALB_Port`  | `80`                  |
|`SharedALB_Vhost` | `www.example.com`     |

**to-dos**
* managed removal (by setting `SharedALB = absent`) 
* handle alb [limits](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-limits.html)