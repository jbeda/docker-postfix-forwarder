# Copyright 2015 Joe Beda
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

image-name := postfix-forwarder

.PHONY: base-image image bash

.DEFAULT_GOAL := image

base-image: Dockerfile.base
	docker build -f Dockerfile.base -t $(image-name)-base .

image: base-image Dockerfile.prod base-image
	docker build -f Dockerfile.prod -t $(image-name) .

bash: base-image Dockerfile.bash
	docker build -f Dockerfile.bash -t $(image-name)-bash .
	docker run -ti --rm $(image-name)-bash bash

BUCKET := $(shell gcloud config -q --format text list project | cut -d ' ' -f 2 | tr - _)
GCR_NAME := gcr.io/$(BUCKET)/$(image-name)

upload-gcr: image
	docker tag -f $(image-name) $(GCR_NAME)
	gcloud docker push $(GCR_NAME)
	docker rmi $(GCR_NAME)

upload-gcr-test: image
	docker tag -f $(image-name) $(GCR_NAME):test
	gcloud docker push $(GCR_NAME):test
	docker rmi $(GCR_NAME):test
