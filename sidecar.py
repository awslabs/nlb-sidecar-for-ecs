"""
Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
SPDX-License-Identifier: MIT

Licensed under the MIT License. See the LICENSE accompanying this file
for the specific language governing permissions and limitations under
the License.
"""

import logging
import os
import signal
import sys
import time
from enum import Enum

import boto3
import botocore
import daemon
import requests
from awsretry import AWSRetry

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def shutdown(clean: bool = True):
    """
    Exits the application/daemon

    :param clean: Determines the exit code.
    """
    if not clean:
        logging.error('Detected unclean exit, exit(1)')
        sys.exit(1)
    else:
        logging.info('Detected clean exit, exit(0)')
        sys.exit(0)


def shutdown_handler(signal_number: int, frame: None):
    """
    Handler function called by DaemonContext that will handle the shutdown

    :param signal_number: Signal provided by handler execution
    :param frame: Not used, required for instance
    """

    # We're going ignore the frame and signal number in this implementation
    logging.debug(f"Caught signal {signal_number:d}, calling shutdown()")
    logging.debug(f"Frame details: {str(frame)}")
    shutdown()


class Errors(Enum):
    """
    Enum representing the different error types that may be encountered
    """
    UNKNOWN = 0
    METADATA = 1
    CONTEXT = 2
    AWS_ACCESS = 3


class SideCarApp:
    """
    Class containing the sidecar application

    ...

    Attributes
    ----------
    deregistration_wait : int
        how long to wait after the NLB is in draining state before exiting in seconds
    polling_frequency : int
        how frequently in seconds to check the target status
    target_container_name : str or None
        the target container we need for
    network_type : str
        network type the ECS task is running on (currently only awsvpc is supported)
    network_addr : str
        IP address of the network interface
    container_ports_tcp : dict or None
        the ports that the container will be listening on (TCP)
    container_ports_udp:
        the ports that the container will be listening on (UDP)
    task_arn : str
        ARN of the ECS Task
    container_instance_arn : str or None
        ARN of the Container Instance this task is running on
    service_arn : str
        ARN of the ECS Service the ECS Task is a member of
    target_group_arns: list of str
        List of ARNs of the Target Groups attached to the Service
    instance_id : str or None
        The Instance ID of container instance the task is running on
    region : str
        Region of the Task
    ecs_cluster : str
        Cluster the ECS Task is a member of
    client_ecs : boto3.client
        ECS Client to interact with ECS API
    client_elb : boto3.client
        ELBv2 Client to interact with the ELBv2 API
    client_ec2: boto3.client
        EC2 Client to interact with the EC2 API
    load_balancers : dict
        Dictionary containing the attached Load Balancers to the ECS Service
    target_types : dict or None
        The target type of the target group indexed by Target Group Arn
    target_protocols : dict or None
        The target protocol of the target group (udp or tcp) indexed by Target Group Arn
    context : daemon.DaemonContext
        Context to setup the daemon process.
    """

    def __init__(self):
        # Process Environment Variables before starting

        # Grab Deregistration Wait Time from Environment Variables
        if not (deregistration_wait := os.getenv('DEREGISTRATION_WAIT', '120')).isnumeric():
            logging.warning(f'DEREGISTRATION_WAIT was not a numeric value: {deregistration_wait}')
            deregistration_wait = 120
        self.deregistration_wait = int(deregistration_wait)
        if not (polling_frequency := os.getenv('POLLING_FREQUENCY', '30')).isnumeric():
            logging.warning(f'POLLING_FREQUENCY was not a numeric value: {polling_frequency}')
            polling_frequency = 30
        self.polling_frequency = int(polling_frequency)
        if not (target_container_name := os.getenv('TARGET_CONTAINER_NAME', None)) is None:
            logging.debug('No TARGET_CONTAINER_NAME set, this may cause issues if in bridge mode')
        self.target_container_name = target_container_name
        logging.info(f'Deregistration wait configured to {self.deregistration_wait:d} seconds')
        logging.info(f'Polling frequency configured to {self.polling_frequency:d} seconds')

        # Validate Required Environment Variable and get Metadata
        if (ECS_CONTAINER_METADATA_URI_V4 := os.getenv('ECS_CONTAINER_METADATA_URI_V4')) is None:
            self.error(Errors.METADATA, "Environment Variable ECS_CONTAINER_METADATA_URI_V4 not set", fatal=True)
        try:
            r = requests.get(ECS_CONTAINER_METADATA_URI_V4 + '/task')
            self._metadata = r.json()
        except Exception as e:
            self.error(Errors.METADATA, str(e), fatal=True)

        self.task_arn = self._metadata['TaskARN']
        # ARN is "arn:partition:service:region", so we need 4th element, i.e. 3 zero-indexed
        logging.info(f'Determined TaskARN to be {self.task_arn}')
        self.region = self.task_arn.split(':')[3]
        self.ecs_cluster = self._metadata['Cluster']

        # Setup Needed Clients
        self.client_ecs = boto3.client('ecs', region_name=self.region)
        self.client_elb = boto3.client('elbv2', region_name=self.region)
        self.client_ec2 = boto3.client('ec2', region_name=self.region)
        self.network_type = self._metadata['Containers'][0]['Networks'][0]['NetworkMode']

        # Attempt to find out service details and container instance details
        try:
            logging.debug('Attempting to Describe Task in order to find out Task Group and Container Instance')
            r = self.client_ecs.describe_tasks(cluster=self.ecs_cluster, tasks=[self.task_arn])
            task_group = r['tasks'][0]['group']
            if not task_group.startswith('service:'):
                self.error(
                    Errors.CONTEXT, f"Task is not in a service, task group: {r['tasks'][0]['group']}",
                    fatal=True
                    )
            self._service_name = task_group.split(':', 1)[1]
            if 'containerInstanceArn' in r['tasks'][0]:
                self.container_instance_arn = r['tasks'][0]['containerInstanceArn']
            else:
                self.container_instance_arn = None

            logging.debug(
                f'Attempting to Describe Service {self._service_name} in order to get TargetGroupArn information'
                )
            r = self.client_ecs.describe_services(cluster=self.ecs_cluster, services=[self._service_name])
            self.service_arn = r['services'][0]['serviceArn']
            self.load_balancers = r['services'][0]['loadBalancers']
            target_group_arns = []
            for lb in self.load_balancers:
                if 'targetGroupArn' in lb:
                    target_group_arns.append(lb['targetGroupArn'])
            if len(target_group_arns) == 0:
                self.error(Errors.CONTEXT, "No NLB/ALB attached to service", fatal=True)
            self.target_group_arns = target_group_arns
        except Exception as e:
            self.error(Errors.AWS_ACCESS, str(e), fatal=True)
        logging.info(f'Determined Service to be {self.service_arn}')

        # Assumption: Only the first IP address is relevant for `bridge` and `awsvpc` only has one address
        if self.network_type == 'awsvpc':
            if len(self._metadata['Containers'][0]['Networks'][0]['IPv4Addresses']) != 1:
                self.error(Errors.CONTEXT, "Task has more than one IPv4 address", fatal=True)
            self.network_addr = self._metadata['Containers'][0]['Networks'][0]['IPv4Addresses'][0]
            self.instance_id = None
            self.container_ports_tcp = None
            self.container_ports_udp = None
            self.target_types = None
            self.target_protocols = None
        elif self.network_type == 'bridge':
            if self.container_instance_arn is None:
                self.error(
                    Errors.CONTEXT, "Task is running in 'bridge' mode but is not attached to a Container "
                                    "Instance", fatal=True
                    )
            logging.debug('Attempting to get the Instance ID')
            try:
                r = self.client_ecs.describe_container_instances(
                    cluster=self.ecs_cluster,
                    containerInstances=[self.container_instance_arn]
                    )
                self.instance_id = r['containerInstances'][0]['ec2InstanceId']

                r = self.client_ec2.describe_instances(InstanceIds=[self.instance_id])
                self.network_addr = r['Reservations'][0]['Instances'][0]['PrivateIpAddress']
            except Exception as e:
                self.error(Errors.AWS_ACCESS, str(e), fatal=True)

            logging.debug('Attempting to get Target Group information')
            try:
                r = self.client_elb.describe_target_groups(TargetGroupArns=self.target_group_arns)
                self.target_protocols = {}
                self.target_types = {}
                for tg in r['TargetGroups']:

                    if tg['TargetType'] in ['instance', 'ip']:
                        self.target_types[tg['TargetGroupArn']] = tg['TargetType']
                    else:
                        self.error(
                            Errors.CONTEXT, f"Unsupported target type {tg['TargetType']} for {tg['TargetGroupArn']}"
                            )
                    if tg['Protocol'] in ['TCP', 'TLS']:
                        self.target_protocols[tg['TargetGroupArn']] = 'tcp'
                    elif tg['Protocol'] in ['UDP']:
                        self.target_protocols[tg['TargetGroupArn']] = 'udp'
                    else:
                        self.error(
                            Errors.CONTEXT, f"Unsupported protocol {tg['Protocol']} for {tg['TargetGroupArn']}"
                            )
            except Exception as e:
                self.error(Errors.AWS_ACCESS, str(e), fatal=True)

            logging.debug('Attempting to get HostPort')
            if self.target_container_name is None:
                self.error(
                    Errors.CONTEXT, "Environment variable TARGET_CONTAINER_NAME was not set. Cannot determine "
                                    "Host Ports", fatal=True
                    )
            self._target_container = None
            # Loop through containers looking for target container
            for container in self._metadata['Containers']:
                if container['Name'] == self.target_container_name:
                    self._target_container = container
            if self._target_container is None:
                self.error(
                    Errors.CONTEXT,
                    f"Environment variable TARGET_CONTAINER_NAME refers to a container ({self.target_container_name}) "
                    f"that does not exist", fatal=True
                    )

            self.container_ports_tcp = None
            self.container_ports_udp = None
            for port in self._target_container['Ports']:
                if port['Protocol'] == 'tcp':
                    if self.container_ports_tcp is None:
                        self.container_ports_tcp = {}
                    self.container_ports_tcp[port['ContainerPort']] = port['HostPort']
                elif port['Protocol'] == 'udp':
                    if self.container_ports_udp is None:
                        self.container_ports_udp = {}
                    self.container_ports_udp[port['ContainerPort']] = port['HostPort']
                else:
                    self.error(
                        Errors.CONTEXT, f"Unknown protocol {port['Protocol']} for port {port['ContainerPort']:d}",
                        fatal=True
                        )
            if self.container_ports_tcp is None and self.container_ports_udp is None:
                self.error(
                    Errors.CONTEXT, f"Target container {self.target_container_name} does not have any port mappings"
                    )
        else:
            self.error(Errors.CONTEXT, "Task is not running in 'awsvpc' or `bridge` mode", fatal=True)

        logging.info(f'Determined network mode to be {self.network_type}')
        logging.info(f'Determined IP address to be {self.network_addr}')

        # Important: run with detach_process=False as running inside a container
        self.context = daemon.DaemonContext(
            detach_process=False,
            stdout=sys.stdout,
            stderr=sys.stderr,
            signal_map={
                signal.SIGTERM: shutdown_handler,
                }
            )

    @AWSRetry.backoff(tries=15, delay=2, backoff=1.5)
    def check_health(self, target_group_arn: str, port: int = 80, network_addr: str = None, instance_id: str = None):
        """
         Checks the health of a given target IP and port in a Target Group

         :param instance_id: Instance of the target to query. If set overrides network_addr
         :param target_group_arn: Target Group ARN to query
         :param network_addr: IP address of the target to query
         :param port: Port of the target to query
         :return: Health status of the Target
         """
        if instance_id is None:
            target = network_addr
        else:
            target = instance_id
        logging.debug(f'Attempting DescribeTargetHealth with {target_group_arn} ; {network_addr} ; {port}')
        try:
            r = self.client_elb.describe_target_health(
                TargetGroupArn=target_group_arn, Targets=[
                    {
                        'Id':   target,
                        'Port': port
                        }
                    ]
                )
        except botocore.exceptions.ClientError as e:
            raise e
        return r['TargetHealthDescriptions'][0]['TargetHealth']

    def run(self):
        """
        Runs the daemon process which checks the health of the targets for this task every 30 seconds and calls drain()
        when a target goes into 'draining'
        """
        logging.info('Initialization Complete, starting daemon')
        with self.context:
            logging.info('Daemon started')
            while True:
                # Attempt to check every POLLING_FREQUENCY seconds
                time.sleep(self.polling_frequency)

                for lb in self.load_balancers:
                    logging.info('Checking Target Health')
                    if 'targetGroupArn' in lb:
                        instance_id = None
                        if self.target_types is not None:
                            target_type = self.target_types[lb['targetGroupArn']]
                            target_protocol = self.target_protocols[lb['targetGroupArn']]
                            if target_type == 'instance':
                                instance_id = self.instance_id
                            if target_protocol == 'tcp':
                                port = self.container_ports_tcp[lb['containerPort']]
                            else:
                                # currently only 2, tcp and udp
                                port = self.container_ports_udp[lb['containerPort']]
                        else:
                            port = lb['containerPort']

                        # Perform actual health check
                        r = self.check_health(
                            lb['targetGroupArn'], port=port, network_addr=self.network_addr,
                            instance_id=instance_id
                            )
                        logging.info(f'Health check for target {self.network_addr}:{port:d} was {r["State"]}')
                        if r['State'] == 'draining':
                            logging.warning(
                                f'Determined that {lb["targetGroupArn"]} target {self.network_addr} is in state '
                                f'{r["State"]}, exiting after {self.deregistration_wait:d} seconds'
                                )
                            self.drain()

    def drain(self):
        """
        Waits the deregistration_wait time (in seconds) and then calls shutdown()
        """
        # Wait DEREGISTRATION seconds for NLB workflow timeout
        time.sleep(self.deregistration_wait)
        # For containers marked as essential this should send a SIGTERM to compliment task.
        shutdown()

    @staticmethod
    def error(error: Errors, message: str, fatal: bool = False):
        """
        Prints an error message to the log.

        :param error: Error type
        :param message: Message to be printed
        :param fatal: Determines if function should call shutdown after this error
        """
        if error == Errors.METADATA:
            logging.error(f'Error import ECS Metadata: {message}')

        elif error == Errors.CONTEXT:
            logging.error(f'Task context incorrect: {message}')

        elif error == Errors.AWS_ACCESS:
            logging.error(f'Unable to access AWS API: {message}')

        else:
            logging.error(f'Unknown Error: {message}')

        if fatal:
            logging.fatal("Previous error was a fatal error, attempting to exit process cleanly")
            shutdown(clean=False)


app = SideCarApp()
app.run()
