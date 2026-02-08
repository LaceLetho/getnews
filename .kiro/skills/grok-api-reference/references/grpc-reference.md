# Grok API - Grpc Reference

**Sections:** 1

---

## Table of Contents

- developers/grpc-reference

---

===/developers/grpc-reference===
# gRPC Reference

The xAI Enterprise gRPC API is a robust, high-performance gRPC interface designed for seamless integration into existing systems.

The base url for all services is at `api.x.ai`. For all services, you have to authenticate with the header `Authorization: Bearer <your xAI API key>`.

Visit [xAI API Protobuf Definitions](https://github.com/xai-org/xai-proto) to view and download our protobuf definitions.

***

<GrpcDocsSection title="Image" protoFileName={'xai/api/v1/image.proto'} serviceFullName={'xai_api.Image'} />

<GrpcDocsSection title="Models" protoFileName={'xai/api/v1/models.proto'} serviceFullName={'xai_api.Models'} />

<GrpcDocsSection title="Raw Sampling of a Language Model" protoFileName={'xai/api/v1/sample.proto'} serviceFullName={'xai_api.Sample'} />

