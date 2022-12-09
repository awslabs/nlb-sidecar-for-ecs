This sidecar requires the following minimal permissions added to the Task Role to function (further permission reduction may be possible but has not been tested):

Note that `elasticloadbalancing:DescribeTargetGroups`, `ec2:DescribeInstances` and `ecs:DescribeContainerInstances` are only required for `bridge` mode tasks. In `awsvpc` mode tasks this information is not required to determine the target in the target group that represents the active task.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ECSNLBSideCar",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "elasticloadbalancing:DescribeTargetHealth",
                "elasticloadbalancing:DescribeTargetGroups",
                "ecs:DescribeServices",
                "ecs:DescribeContainerInstances",
                "ecs:DescribeTasks"
            ],
            "Resource": "*"
        }
    ]
}
```

Here is an example Task Definition with this in use compatible with Fargate:

```json
{
  "containerDefinitions": [
    {
      "name": "web",
      "image": "nginx",
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "stopTimeout": 60,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/web-application-example",
          "awslogs-region": "ap-southeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    },
    {
      "name": "sidecar",
      "image": "public.ecr.aws/aws-se/nlb-sidecar-for-ecs:latest",
      "essential": true,
      "environment" : [
        {
          "name": "DEREGISTRATION_WAIT",
          "value": "120"
        }     
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/web-application-example",
          "awslogs-region": "ap-southeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "family": "web-application-example",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ECSNLBSidecar",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "networkMode": "awsvpc",
  "requiresCompatibilities": [
    "FARGATE"
  ],
  "cpu": "512",
  "memory": "1024"
}
```

Here is an example Task Definition for Bridge Mode Tasks:

```json
{
  "containerDefinitions": [
    {
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/web-application-example",
          "awslogs-region": "ap-southeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "portMappings": [
        {
          "protocol": "tcp",
          "containerPort": 80
        }
      ],
      "memory": 256,
      "image": "nginx",
      "essential": true,
      "stopTimeout": 60,
      "name": "web"
    },
    {
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/web-application-example",
          "awslogs-region": "ap-southeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "environment": [
        {
          "name": "DEREGISTRATION_WAIT",
          "value": "180"
        },
        {
          "name": "POLLING_FREQUENCY",
          "value": "10"
        },
        {
          "name": "TARGET_CONTAINER_NAME",
          "value": "web"
        }
      ],
      "memory": 64,
      "image": "public.ecr.aws/aws-se/nlb-sidecar-for-ecs:latest",
      "dependsOn": [
        {
          "containerName": "web",
          "condition": "START"
        }
      ],
      "essential": true,
      "name": "sidecar"
    }
  ],
  "taskRoleArn": "arn:aws:iam::123456789012:role/ECSNLBSidecar",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "family": "web-application-example",
  "networkMode": "bridge"
}
```

Note also that after initialisation each instance of this sidecar will perform a `DescribeTargetHealth` API call every 30 seconds (by default). It is not recommended running too many of these in parallel as the code has limited exponential backoff and retry logic. Failure for the API call to be called currently will result in premature termination of the sidecar as an uncaught exception will likely be raised.

This sidecar currently also relies on the following assumptions:

- Tasks are running in `awsvpc` or `bridge` network mode. `host` mode tasks are not supported.
- Tasks have access to the ECS Metadata V4 API. This applies to current FARGATE environments and agent version 1.39 or later.
- When Task is running in `bridge` network mode `TARGET_CONTAINER_NAME` is set with the container name of the container connected to the NLB.
- When Task is running in `bridge` network mode the protocol of the target group is configured to either `TLS`, `TCP` or `UDP`. `TCP_UDP` is not supported. 
- When Task is running in `bridge` mode the sidecar container is started after the application container. Recommend using `dependsOn` to enforce this.
