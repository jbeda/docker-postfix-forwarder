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
	gcloud preview docker push $(GCR_NAME)
	docker rmi $(GCR_NAME)

upload-gcr-test: image
	docker tag -f $(image-name) $(GCR_NAME):test
	gcloud preview docker push $(GCR_NAME):test
	docker rmi $(GCR_NAME):test
