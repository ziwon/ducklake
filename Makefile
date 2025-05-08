MODE ?= nessie
ENV ?= .env
BASE = compose/docker-compose.base.yml
OVR = compose/docker-compose.$(MODE).yml
SERVICES = postgres airflow-init minio  # 기본 서비스 목록 (필요시 확장 가능)

# Add near the top
REGISTRY_HOST = registry:5000
SPARK_DRIVER_IMAGE_NAME = spark-quotes-ingest
SPARK_DRIVER_IMAGE_TAG = latest
SPARK_DRIVER_FULL_IMAGE = $(REGISTRY_HOST)/$(SPARK_DRIVER_IMAGE_NAME):$(SPARK_DRIVER_IMAGE_TAG)

.PHONY: build-spark-driver push-spark-driver

# Target to build the Spark driver image locally
build-spark-driver:
	@echo "Building Spark driver image..."
	docker build -t $(SPARK_DRIVER_IMAGE_NAME):$(SPARK_DRIVER_IMAGE_TAG) -f docker/spark-driver/Dockerfile .

# Target to tag and push the image to the local registry
push-spark-driver: build-spark-driver
	@echo "Tagging image for local registry $(REGISTRY_HOST)..."
	docker tag $(SPARK_DRIVER_IMAGE_NAME):$(SPARK_DRIVER_IMAGE_TAG) $(SPARK_DRIVER_FULL_IMAGE)
	@echo "Pushing image to local registry $(REGISTRY_HOST)..."
	docker push $(SPARK_DRIVER_FULL_IMAGE)

# 전체 서비스 시작 (기존 동작 유지)
up:
	docker compose --env-file $(ENV) -f $(BASE) -f $(OVR) up --build -d

# 특정 서비스만 시작 (예: make up-svc SERVICE="postgres airflow-init")
up-svc:
	docker compose --env-file $(ENV) -f $(BASE) -f $(OVR) up --build -d $(SERVICE)

# Hive 모드 전체 시작
up-hive:
	$(MAKE) MODE=hive up

# Nessie 모드 전체 시작
up-nessie:
	$(MAKE) MODE=nessie up

# 특정 서비스 Hive 모드 시작 (예: make up-hive-svc SERVICE="hive-metastore")
up-hive-svc:
	$(MAKE) MODE=hive up-svc SERVICE="$(SERVICE)"

# 특정 서비스 Nessie 모드 시작 (예: make up-nessie-svc SERVICE="nessie")
up-nessie-svc:
	$(MAKE) MODE=nessie up-svc SERVICE="$(SERVICE)"

# 서비스 재시작
restart:
	$(MAKE) down && $(MAKE) up

# 서비스 종료
down:
	docker compose --env-file $(ENV) -f $(BASE) -f $(OVR) down --remove-orphans --volumes

# 전체 로그 확인
logs:
	docker compose --env-file $(ENV) -f $(BASE) -f $(OVR) logs -f

# 특정 서비스 로그 확인 (예: make logs-svc SERVICE="airflow-web")
logs-svc:
	docker compose --env-file $(ENV) -f $(BASE) -f $(OVR) logs -f $(SERVICE)

.PHONY: up down logs ps restart up-svc up-hive up-nessie