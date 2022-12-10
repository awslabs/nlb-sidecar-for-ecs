#  Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: MIT
#
#  Licensed under the MIT License. See the LICENSE accompanying this file
#  for the specific language governing permissions and limitations under
#  the License.

FROM public.ecr.aws/amazonlinux/amazonlinux:2
RUN mkdir -p /app \
 && yum makecache \
 && yum install amazon-linux-extras -y\
 && amazon-linux-extras enable python3.8 \
 && yum clean metadata \
 && yum install python3.8 python3.8-pip -y\
 && yum clean all
WORKDIR /app
COPY requirements.txt ./
RUN python3.8 -m pip install --no-cache-dir -r requirements.txt
COPY . .
CMD [ "python3.8", "./sidecar.py" ]
