#  Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: MIT
#
#  Licensed under the MIT License. See the LICENSE accompanying this file
#  for the specific language governing permissions and limitations under
#  the License.

.PHONY: build setup	use clean-local clean export-local


export-local: build
	docker buildx build --load --file AmazonLinux2.Dockerfile --tag public.ecr.aws/aws-se/nlb-sidecar-for-ecs:local .
	docker buildx build --load --file Alpine.Dockerfile --tag public.ecr.aws/aws-se/nlb-sidecar-for-ecs:local-alpine .

build: use
	docker buildx build --pull --platform linux/amd64,linux/arm64 --file AmazonLinux2.Dockerfile --tag public.ecr.aws/aws-se/nlb-sidecar-for-ecs:local .
	docker buildx build --pull --platform linux/amd64,linux/arm64 --file Alpine.Dockerfile --tag public.ecr.aws/aws-se/nlb-sidecar-for-ecs:local-alpine  .

setup:
	docker buildx create --name multi-arch

use:
	docker buildx use multi-arch

clean-local:
	docker rmi public.ecr.aws/aws-se/nlb-sidecar-for-ecs:local public.ecr.aws/aws-se/nlb-sidecar-for-ecs:local-alpine ${LOCALPUSHTOO}

clean: clean-local
	docker rmi public.ecr.aws/aws-se/nlb-sidecar-for-ecs:latest || true
	docker image prune -f
