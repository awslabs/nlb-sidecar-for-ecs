#  Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: MIT
#
#  Licensed under the MIT License. See the LICENSE accompanying this file
#  for the specific language governing permissions and limitations under
#  the License.

VERSION_MAJOR=1.0
VERSION_MINOR=1.0.4


.PHONY: build build-local build-local-and-push build-and-push setup	use clean-local clean

build: use
	docker buildx build --pull --platform linux/amd64,linux/arm64 --file AmazonLinux2.Dockerfile . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:latest \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:amazonlinux2 \
          --tag $(LOCALPUSHTOO):amazonlinux2
	docker buildx build --pull --platform linux/amd64,linux/arm64 --file Alpine.Dockerfile . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR)-alpine \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR)-alpine \
          --tag public.ecr.aws/x314a9v5/nlb-sidecar-for-ecs\:alpine \
          --tag $(LOCALPUSHTOO):alpine


build-and-push: use
	docker buildx build --pull --platform linux/amd64,linux/arm64 --file AmazonLinux2.Dockerfile --push . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:latest \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:amazonlinux2 \
          --tag $(LOCALPUSHTOO):amazonlinux2
	docker buildx build --pull --platform linux/amd64,linux/arm64 --file Alpine.Dockerfile --push . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR)-alpine \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR)-alpine \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:alpine \
          --tag $(LOCALPUSHTOO):alpine

build-local: use
	docker buildx build --pull --platform linux/amd64,linux/arm6 --file AmazonLinux2.Dockerfile --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local .
	docker buildx build --pull --platform linux/amd64,linux/arm6 --file Alpine.Dockerfile --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local-alpine .

build-local-and-push: use
	docker buildx build --pull --push --platform linux/amd64,linux/arm64 --file AmazonLinux2.Dockerfile --tag $(LOCALPUSHTOO):local-amazonlinux .
	docker buildx build --pull --push --platform linux/amd64,linux/arm64 --file Alpine.Dockerfile --tag $(LOCALPUSHTOO):local-alpine .

setup:
	docker buildx create --name multi-arch

use:
	docker buildx use multi-arch

clean-local:
	docker rmi public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local-alpine ${LOCALPUSHTOO} || true

clean: clean-local
	docker rmi public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:latest || true
	docker image prune -f
