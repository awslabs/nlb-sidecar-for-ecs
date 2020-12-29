# AWS Network Load Balancer Sidecar Container for ECS

This repository contains a Dockerfile and some Python Code that will create a small Python based daemon that will help ensure that your application properly handles an AWS Network Load Balancer in ECS.

You can grab this image under the ECR Public Repository at `public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:latest`

Currently, ECS will keep the task open for the entire deregistration delay, however there is not a way to "prematurely" stop the task allowing for a gracefully handing over any active connections.

This sidecar monitors the NLB Target Group Target Health of the primary process in order to determine if the target is in the "draining" state. It will then wait the recommended 120 seconds before exiting (by default). If the sidecar container is marked as "essential" in the ECS task definition this will result in a `SIGTERM` signal being sent (by default) to all other containers in the task.

Configurable options include:

- `DEREGISTRATION_WAIT` : time to wait after task goes into draining in seconds before exiting (default: 120)
- `POLLING_FREQUENCY` : frequency to check the current status of the target in seconds (default: 30)
- `TARGET_CONTAINER_NAME` : for `bridge` mode tasks. This specifies the container that has been linked to a NLB that you wish to monitor the target health of

Depending on how the primary application is configured, this allows the primary application to gracefully exit by using the `SIGTERM` signal and `stopTimeout` property. A graceful exit _should_ consist of:

- Completing the active transaction
- Sending a TCP RST or TCP FIN signal to close out the connection.

If your application is configured to achieve this graceful exit condition on a signal other than `SIGTERM` it is recommended you build your image with a modified [`STOPSIGNAL`](https://docs.docker.com/engine/reference/builder/#stopsignal).

For example the `library/nginx` image uses `SIGTERM` by default for versions 1.19.4 and below but a `SIGQUIT` signal can be used provided that you are not using UNIX sockets or a version prior to 1.19.1 (as per [defect #753](https://trac.nginx.org/nginx/ticket/753) which was merged into [1.19.1 of ngnix](https://trac.nginx.org/nginx/browser/nginx/src/os/unix/ngx_process_cycle.c?rev=062920e2f3bf871ef7a3d8496edec1b3065faf80)) which will "gracefully exit" existing connections. Therefore, you may want to build your own nginx with a modified `STOPSIGNAL` or use version [1.19.5 or later](https://github.com/nginxinc/docker-nginx/commit/3fb70ddd7094c1fdd50cc83d432643dc10ab6243) as ECS does not support runtime modification of the stop signal:

```
FROM nginx:1.19.4
STOPSIGNAL SIGQUIT
```

The specific signalling behaviour you will need to use depends on the particular application stack you are using. Please spend time familiarising yourself with the signal handling behaviour of your chosen stack and ensure you are correctly signalling.

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
      "image": "public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:latest",
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
      "memory": 256,
      "image": "public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:latest",
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

------

Please feel free to raise an issue or pull request.