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
 && yum install -y python3.8 python3.8-pip \
 && rm /usr/bin/python \
 && ln -s /usr/bin/python3.8 /usr/bin/python3 \
 && ln -s /usr/bin/python3.8 /usr/bin/python
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .
CMD [ "python", "./sidecar.py" ]
