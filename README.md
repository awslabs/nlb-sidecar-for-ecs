# AWS Network Load Balancer Sidecar Container for ECS

This repository contains a Dockerfile and some Python Code that will create a small Python based daemon that will help ensure that your application properly handles an AWS Network Load Balancer in ECS.

You can grab this image under the ECR Public Repository at `public.ecr.aws/aws-se/nlb-sidecar-for-ecs:latest` with a reduced size variant based upon Alpine Linux at `public.ecr.aws/aws-se/nlb-sidecar-for-ecs:alpine`.

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

---

**Acknowledgements**

[Sidecar icon created by Freepik - Flaticon](https://www.flaticon.com/free-icons/sidecar)