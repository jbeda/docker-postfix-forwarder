image-name := postfix-forwarder

.PHONY: image bash
image: Dockerfile
	docker build -t $(image-name) .

bash: image Dockerfile.bash
	docker build -f Dockerfile.bash -t $(image-name)-bash .
	docker run -ti --rm $(image-name)-bash bash
