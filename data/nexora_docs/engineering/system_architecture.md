---
company: Nexora Technologies
department: engineering
access_level: engineering
doc_id: ENG-001
last_updated: 2026-08-25
---
# NexoStock System Architecture (Engineering Internal)

## Overview
NexoStock is a multi-tenant web application built from a set of services running on Kubernetes in the CloudNimbus cloud.

## Main components
- **API Gateway:** Handles authentication (JWT), rate limiting (1,000 requests per minute per tenant) and routing.
- **Inventory Service:** Python (FastAPI). Manages stock levels, warehouses and product catalogs.
- **Order Service:** Go. Processes orders and publishes events to the message queue.
- **Notification Service:** Node.js. Sends email and SMS alerts for low stock.
- **Message queue:** Apache Kafka, 3 brokers, 7-day retention.
- **Database:** PostgreSQL 15 with one primary and two read replicas. Each tenant has its own schema.
- **Cache:** Redis cluster for sessions and frequently read product data.

## Deployment
Code is deployed through GitHub Actions. Every merge to main runs unit and integration tests, builds a container image, and deploys to staging. Production deploys need one approval from a senior engineer and happen with a rolling update.

## Monitoring
Metrics are collected with Prometheus and shown in Grafana. Alerts go to the on-call engineer through PagerDuty. Target availability is 99.9% per month.

## Secrets
Secrets are stored in the cloud secrets manager and rotated every 90 days. Secrets must never be committed to Git.
