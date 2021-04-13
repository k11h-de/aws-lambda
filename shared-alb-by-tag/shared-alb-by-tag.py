import json
import boto3

def lambda_handler(event, context):

    # set these variables manually OR
    vpc_id = ''
    pub_subnet_1 = ''
    pub_subnet_2 = ''
    pub_subnet_3 = ''
    priv_subnet_1 = ''
    priv_subnet_2 = ''
    priv_subnet_3 = ''
    secgr_allport80 = ''
    secgr_allport443 = ''
    ssl_cert_arn = ''
    r53_hosted_zoneid = ''

    # # 2. get exports from cloudformation
    # # if choose this option, please adapt the export names to your needs
    # cfn_client = boto3.client('cloudformation')
    # exports = cfn_client.list_exports()
    # if exports['Exports']:
    #     for e in exports['Exports']:
    #         # get vpcid
    #         if e['Name'] == 'VpcId':
    #             vpc_id = str(e['Value'])
    #         # get public sub 1
    #         if e['Name'] == 'VpcPublicSubnet1':
    #             pub_subnet_1 = str(e['Value'])
    #         # get public sub 2
    #         if e['Name'] == 'VpcPublicSubnet2':
    #             pub_subnet_2 = str(e['Value'])
    #         # get public sub 3
    #         if e['Name'] == 'VpcPublicSubnet3':
    #             pub_subnet_3 = str(e['Value'])
    #         # get private sub 1
    #         if e['Name'] == 'VpcPrivateSubnet1':
    #             priv_subnet_1 = str(e['Value'])
    #         # get private sub 2
    #         if e['Name'] == 'VpcPrivateSubnet2':
    #             priv_subnet_2 = str(e['Value'])
    #         # get private sub 3
    #         if e['Name'] == 'VpcPrivateSubnet3':
    #             priv_subnet_3 = str(e['Value'])
    #         # get security group all 80
    #         if e['Name'] == 'SecGroupAllowAllPort80':
    #             secgr_allport80 = str(e['Value'])
    #         # get security group all 443
    #         if e['Name'] == 'SecGroupAllowAllPort443':
    #             secgr_allport443 = str(e['Value'])
    #         # get ssl cert arn
    #         if e['Name'] == 'SSLCert':
    #             ssl_cert_arn = str(e['Value'])
    #         # get r53 zoneid
    #         if e['Name'] == 'R53ZoneId':
    #             r53_hosted_zoneid = str(e['Value'])
    # if choose option 1, please comment out this block


    # get all running instances that have tag present
    ec2_client = boto3.client('ec2')
    response = ec2_client.describe_instances(
        Filters=[
            {
                'Name': 'tag:SharedALB',
                'Values': [
                    'public','internal'
                ]
            },
            {
                'Name': 'instance-state-name',
                'Values': [
                    'running',
                ]
            },
        ]
    )
    
    # loop through all instances and their tags and generate the dict
    ec2_dict = []
    if response['Reservations']:
        for r in response['Reservations']:
            
            if r['Instances']:
                for i in r['Instances']:
                    
                    value_vhost = ''
                    value_port = ''
                    value_alb = ''
                    
                    if i['Tags']:
                        for t in i['Tags']:
                            
                            if t['Key'] == 'SharedALB':
                                value_alb =   str(t['Value'])
                            if t['Key'] == 'SharedALB_Port':
                                value_port =  str(t['Value'])
                            if t['Key'] == 'SharedALB_Vhost':
                                value_vhost = str(t['Value'])                                    
                                    
                    match = {
                        'id': str(i['InstanceId']),
                        'port': value_port,
                        'vhost':  value_vhost,
                        'schema': value_alb
                    }
                    ec2_dict.append(match)
                    print(str(match))

    elbv2_client = boto3.client('elbv2')
    
    # create/ensure internal ALB
    response = elbv2_client.create_load_balancer(
        Name='SharedALB-internal',
        Subnets=[
            priv_subnet_1,priv_subnet_2,priv_subnet_3
        ],
        SecurityGroups=[
            secgr_allport80,secgr_allport443
        ],
        Scheme='internal',
        Type='application',
        IpAddressType='ipv4'
    )
    if response['LoadBalancers']:
        alb_internal_arn = str(response.get('LoadBalancers')[0]['LoadBalancerArn'])
        alb_internal_zoneid = str(response.get('LoadBalancers')[0]['CanonicalHostedZoneId'])
        alb_internal_dnsname = str(response.get('LoadBalancers')[0]['DNSName'])
    
    # create listener 80
    response = elbv2_client.create_listener(
        LoadBalancerArn=alb_internal_arn,
        Protocol='HTTP',
        Port=80,
        DefaultActions=[
            {
                'Type': 'redirect',
                'Order': 1,
                'RedirectConfig': {
                    'Protocol': 'HTTPS',
                    'Port': '443',
                    'StatusCode': 'HTTP_301'
                }
            },
        ]
    )
    # create listener 443
    response = elbv2_client.create_listener(
        LoadBalancerArn=alb_internal_arn,
        Protocol='HTTPS',
        Port=443,
        SslPolicy='ELBSecurityPolicy-2016-08',
        Certificates=[
            {
                'CertificateArn': ssl_cert_arn
            },
        ],
        DefaultActions=[
            {
                'Type': 'fixed-response',
                'Order': 1,
                'FixedResponseConfig': {
                    'MessageBody': 'the request was not routed',
                    'StatusCode': '404',
                    'ContentType': 'text/plain'
                }
            },
        ]
    )
    # get listenerARN for later use
    listener_internal_arn = ''
    if response['Listeners']:
        listener_internal_arn = str(response['Listeners'][0]['ListenerArn'])


    # create/ensure public ALB
    response = elbv2_client.create_load_balancer(
        Name='SharedALB-public',
        Subnets=[
            pub_subnet_1,pub_subnet_2,pub_subnet_3
        ],
        SecurityGroups=[
            secgr_allport80,secgr_allport443
        ],
        Scheme='internet-facing',
        Type='application',
        IpAddressType='ipv4'
    )
    if response['LoadBalancers']:
        alb_public_arn = str(response.get('LoadBalancers')[0]['LoadBalancerArn'])
        alb_public_zoneid = str(response.get('LoadBalancers')[0]['CanonicalHostedZoneId'])
        alb_public_dnsname = str(response.get('LoadBalancers')[0]['DNSName'])

    # create listener 80
    response = elbv2_client.create_listener(
        LoadBalancerArn=alb_public_arn,
        Protocol='HTTP',
        Port=80,
        DefaultActions=[
            {
                'Type': 'redirect',
                'Order': 1,
                'RedirectConfig': {
                    'Protocol': 'HTTPS',
                    'Port': '443',
                    'StatusCode': 'HTTP_301'
                }
            },
        ]
    )
    # create listener 443
    response = elbv2_client.create_listener(
        LoadBalancerArn=alb_public_arn,
        Protocol='HTTPS',
        Port=443,
        SslPolicy='ELBSecurityPolicy-2016-08',
        Certificates=[
            {
                'CertificateArn': ssl_cert_arn
            },
        ],
        DefaultActions=[
            {
                'Type': 'fixed-response',
                'Order': 1,
                'FixedResponseConfig': {
                    'MessageBody': 'request was not routed',
                    'StatusCode': '404',
                    'ContentType': 'text/plain'
                }
            },
        ]
    )
    # get listenerARN for later use
    listener_public_arn = ''
    if response['Listeners']:
        listener_public_arn = str(response['Listeners'][0]['ListenerArn'])

    # create/ensure one targetgroup per vhost and register
    for index in range(len(ec2_dict)):
        # create target-groups
        tg_arn = ''
        response = elbv2_client.create_target_group(
            Name= 'EBshared-' + str( ec2_dict[index]['vhost'] ).replace('-', '').replace('.', '')[0:20],
            Protocol='HTTP',
            Port=int(ec2_dict[index]['port']),
            VpcId=vpc_id,
            TargetType='instance',
            HealthCheckPath='/health'
        )
        if response['TargetGroups']:
            tg_arn = str(response.get('TargetGroups')[0]['TargetGroupArn'])
            # add tg_arn to dict
            ec2_dict[index].update( {'tg_arn' : tg_arn} )

        # register target in just created target group
        response = elbv2_client.register_targets(
            TargetGroupArn= tg_arn ,
            Targets=[
                {
                    'Id': str(ec2_dict[index]['id']),
                    'Port': int(ec2_dict[index]['port'])
                },
            ]
        )

    # cleanup rules 
    ## internal
    response = elbv2_client.describe_rules(
        ListenerArn=listener_internal_arn
    )
    if response['Rules']:
        for r in response['Rules']:
            if r['IsDefault'] == False:
                response_inner = elbv2_client.delete_rule(
                    RuleArn=r['RuleArn']
                )
    ## public
    response = elbv2_client.describe_rules(
        ListenerArn=listener_public_arn
    )
    if response['Rules']:
        for r in response['Rules']:
            if r['IsDefault'] == False:
                response_inner = elbv2_client.delete_rule(
                    RuleArn=r['RuleArn']
                )

    # create/ensure rules
    for index in range(len(ec2_dict)):
        # create rule for each internal item
        if ec2_dict[index]['schema'] == "internal":
            response = elbv2_client.create_rule(
                ListenerArn=listener_internal_arn,
                Conditions=[
                    {
                        'Field': 'host-header',
                        'Values': [
                            str(ec2_dict[index]['vhost']),
                        ]
                    },
                ],
                Priority= index + 1,
                Actions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': str(ec2_dict[index]['tg_arn']),
                        'Order': 1,
                    },
                ]
            )
        # create rule for each public item    
        if ec2_dict[index]['schema'] == "public":
            response = elbv2_client.create_rule(
                ListenerArn=listener_public_arn,
                Conditions=[
                    {
                        'Field': 'host-header',
                        'Values': [
                            str(ec2_dict[index]['vhost']),
                        ]
                    },
                ],
                Priority=index + 1,
                Actions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': str(ec2_dict[index]['tg_arn']),
                        'Order': 1,
                    },
                ]
            )

    # create/ensure DNS Records
    route53_client = boto3.client('route53')
    for index in range(len(ec2_dict)):
        # create internal records
        if ec2_dict[index]['schema'] == "internal":
            response = route53_client.change_resource_record_sets(
                HostedZoneId=r53_hosted_zoneid,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': ec2_dict[index]['vhost'],
                                'Type': 'A',
                                'AliasTarget': {
                                    'HostedZoneId': alb_internal_zoneid,
                                    'DNSName': alb_internal_dnsname,
                                    'EvaluateTargetHealth': False
                                }
                            }
                        },
                    ]
                }
            )
        # create public records
        if ec2_dict[index]['schema'] == "public":
            response = route53_client.change_resource_record_sets(
                HostedZoneId=r53_hosted_zoneid,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': ec2_dict[index]['vhost'],
                                'Type': 'A',
                                'AliasTarget': {
                                    'HostedZoneId': alb_public_zoneid,
                                    'DNSName': alb_public_dnsname,
                                    'EvaluateTargetHealth': False
                                }
                            }
                        },
                    ]
                }
            )

    return {
        'statusCode': 200,
        'body': json.dumps('okay')
        #'body': json.dumps(response, indent=4, sort_keys=True, default=str) # debug
    }