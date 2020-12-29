#  Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: MIT
#
#  Licensed under the MIT License. See the LICENSE accompanying this file
#  for the specific language governing permissions and limitations under
#  the License.

.PHONY: build build-local build-local-and-push build-and-push setup	use clean-local clean

build: use
	docker buildx build --platform linux/amd64,linux/arm64 -t public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:latest .

build-and-push: use
	docker buildx build --platform linux/amd64,linux/arm64 -t public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs\:latest --push .

build-local:
	docker build -t public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local .

build-local-and-push: build-local
	docker tag public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local ${LOCALPUSHTOO}
	docker push ${LOCALPUSHTOO}

setup:
	docker buildx create --name multi-arch

use:
	docker buildx use multi-arch

clean-local:
	docker rmi public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:local ${LOCALPUSHTOO} || true

clean: clean-local
	docker rmi public.ecr.aws/x3l4a9v5/nlb-sidecar-for-ecs:latest || true
	docker image prune -f
