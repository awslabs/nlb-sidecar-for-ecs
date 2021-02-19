#  Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: MIT
#
#  Licensed under the MIT License. See the LICENSE accompanying this file
#  for the specific language governing permissions and limitations under
#  the License.

VERSION_MAJOR=1.0
VERSION_MINOR=1.0.1


.PHONY: build build-local build-local-and-push build-and-push setup	use clean-local clean

build: use
	docker buildx build --platform linux/amd64,linux/arm64 --file AmazonLinux2.Dockerfile . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:latest \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:amazonlinux2
	docker buildx build --platform linux/amd64,linux/arm64 --file Alpine.Dockerfile . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR)-alpine \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR)-alpine \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:alpine

build-and-push: use
	docker buildx build --platform linux/amd64,linux/arm64 --file AmazonLinux2.Dockerfile --push . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:latest \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR) \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:amazonlinux2
	docker buildx build --platform linux/amd64,linux/arm64 --file Alpine.Dockerfile --push . \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MAJOR)-alpine \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:$(VERSION_MINOR)-alpine \
          --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:alpine

build-local:
	docker build --file AmazonLinux2.Dockerfile --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local .
	docker build --file Alpine.Dockerfile --tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local-alpine .

build-local-and-push: build-local
	docker tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local $(LOCALPUSHTOO):amazonlinux
	docker push $(LOCALPUSHTOO):amazonlinux
	docker tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local-alpine $(LOCALPUSHTOO):alpine
	docker push $(LOCALPUSHTOO):alpine

setup:
	docker buildx create --name multi-arch

use:
	docker buildx use multi-arch

clean-local:
	docker rmi public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local-alpine ${LOCALPUSHTOO} || true

clean: clean-local
	docker rmi public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:latest || true
	docker image prune -f
