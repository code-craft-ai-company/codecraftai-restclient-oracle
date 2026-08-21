# Implementation Plan — Oracle Client

## Package Skeleton

- [x] 1. Create `source/packages/ccai/restclient/oracle/` with a module per concern.
- [x] 2. Add `requests` and `cryptography` as the runtime dependencies in `pyproject.toml`.

## Request Signing

- [x] 3. Implement `OciRequestSigner` with the composite `tenancy/user/fingerprint` key id.
- [x] 4. Implement lazy, cached PEM key loading with optional passphrase support, accepting literal `\n` sequences from an environment-variable round trip.
- [x] 5. Raise `OciSigningError` for an absent, unloadable or non-RSA key.
- [x] 6. Define the two covered header sets: three headers without a body, six with one.
- [x] 7. Compute `x-content-sha256`, `content-length` and a default `content-type` for body-bearing methods.
- [x] 8. Include the query string in `(request-target)`.
- [x] 9. Sign the signing string RSA-SHA256 with PKCS1v15 padding and emit the `Signature version="1",...` header naming the covered set.
- [x] 10. Return the complete header set to send, so the sent headers match the signed ones.
- [x] 11. Accept an injected date so signatures are reproducible under test.
- [x] 12. Expose `signing_string()` separately so tests can assert the covered headers and their order.

## Transport

- [x] 13. Implement `OciTransport` over an injectable session.
- [x] 14. Drop `None` query parameters and build the signed URL from the parameters actually sent.
- [x] 15. Encode request bodies as UTF-8 JSON and sign those exact bytes.
- [x] 16. Classify 429 and 5xx as `TransientServiceError` and other non-2xx as `ServiceError`.
- [x] 17. Extract the OCI `code` and `message` from the failure body, falling back to the HTTP reason phrase.
- [x] 18. Decode success bodies through `wrap`, keeping raw text when the body is not JSON and `None` when it is empty.
- [x] 19. Read the next-page token from the `opc-next-page` response header, matching case-insensitively.

## Errors

- [x] 20. Implement `ServiceError` keeping the `oci.exceptions` name and its `status` / `code` / `message` attributes.
- [x] 21. Implement `TransientServiceError` as a subclass, so a consumer that does not care about the distinction can catch the base.

## Models

- [x] 22. Implement `OciModel` taking snake_case keywords and rendering camelCase bodies with unset fields omitted.
- [x] 23. Implement `to_camel` and recursive `serialize` for nested models, lists and dicts.
- [x] 24. Generate the 29 named `*Details` and rule subclasses from `MODEL_NAMES` so a mistyped class name fails at import.
- [x] 25. Implement `OciObject` resolving fields through `normalize_name` in either spelling, returning `None` when absent.
- [x] 26. Implement `wrap` so nested objects and lists stay attribute-addressable, and `as_dict` for the raw wire shape.
- [x] 27. Implement `Response` with the `oci.response.Response` attribute set, including `has_next_page` and `request_id`.

## Pagination

- [x] 28. Implement `list_call_get_all_results` following `next_page` and returning one aggregated response.
- [x] 29. Raise `TypeError` when the operation answers with something other than a list.
- [x] 30. Implement the generator form yielding every entry across all pages.

## Service Clients

- [x] 31. Implement `_ServiceClient` composing `https://{service}.{region}.{domain}` plus a version path segment, accepting the config dict positionally.
- [x] 32. Implement `VirtualNetworkClient` for VCNs, subnets, internet gateways, route tables and security lists.
- [x] 33. Implement `ComputeClient` for instance launch and termination, instance and image listing, and volume attachment.
- [x] 34. Implement `ComputeManagementClient` for instance configurations and cluster networks.
- [x] 35. Implement `BlockstorageClient` for block volumes.
- [x] 36. Implement `ObjectStorageClient` with no version segment, overriding URL composition.
- [x] 37. Implement `DnsClient` addressing record sets by zone, domain and record type.
- [x] 38. Implement `FileStorageClient.get_file_system`.
- [x] 39. Implement `_camel_params` so arbitrary list filters render as camelCase query parameters.
- [x] 40. Implement `build_clients` returning all seven clients under the keys the venue's session factory used.
- [x] 41. Reproduce the SDK's naming inconsistencies: `create_instance_configuration` without the `_details` suffix, and `ig_id` / `rt_id` abbreviated while `security_list_id` is not.

## Tests

- [x] 42. Build `FakeSession` and `FakeResponse`, with response headers modelled since the next-page token arrives there.
- [x] 43. Verify a produced signature against its own public key.
- [x] 44. Assert the three-header and six-header covered sets, the digest changing with the body, the query string in `(request-target)`, and the `Authorization` header naming the covered set.
- [x] 45. Cover the unusable-key error path.
- [x] 46. Cover model rendering: camelCase, omitted unset fields, nested serialisation, attribute read-back.
- [x] 47. Cover snake_case response reads and `None` for absent fields.
- [x] 48. Cover the OCI error code on the exception, the transient split across 429/500/503, and that a 4xx is not transient.
- [x] 49. Cover next-page extraction from the response header.
- [x] 50. Cover paginator aggregation across pages, the single-page stop, and the non-list `TypeError`.
- [x] 51. Cover per-service hostnames, the shared Core Services host and version, the unversioned Object Storage paths, and the File Storage version.
- [x] 52. Cover the three reproduced SDK naming inconsistencies and the DNS record path shape.

## Open Items

- [ ] 53. The signed query string and the sent query string are built by different encoders. `OciTransport.request` signs a URL built with `urllib.parse.urlencode`, then hands `params` to `requests`, which re-encodes them. The two agree for every scalar value tried, including strings needing percent-encoding, but diverge for a LIST or TUPLE value: `urlencode` renders the repr as a single parameter (`k=%5B%27a%27%2C+%27b%27%5D`) while `requests` expands it into repeated parameters (`k=a&k=b`). Since the signature covers `(request-target)`, a multi-valued filter — which OCI list operations accept for fields such as `lifecycleState` — would be signed differently from how it is sent, and rejected. No current test passes a list-valued filter.
- [ ] 54. No retry on `TransientServiceError`. The transport classifies throttles and server faults as retryable and then raises them; nothing retries, so the classification is currently advisory only.
- [ ] 55. `Response.request` is never populated. `OciTransport` constructs `Response` without it, so it is always `None`, and the paginator propagates that `None` into the aggregate.
- [ ] 56. Reconcile with `codecraftai-restclient-base`. `pyproject.toml` declares it alongside `codecraftai-credentials` and `codecraftai-errors`, but nothing under `source/packages` imports any of the three. Either build on `RestClientBase` or drop the unused dependencies.
- [ ] 57. Accept a typed credential object. `OciRequestSigner` takes tenancy, user, fingerprint, PEM key and passphrase as plain strings, which the repository coding standard in `AGENTS.md` forbids on the API surface.
- [ ] 58. Add the `aspects` parameter. No method takes one, so retry, backoff and logging policy is not caller-controlled; `timeout_seconds` at construction and per call is the only lever.
- [ ] 59. Add property-based tests using `ccai.testbase.properties`. All 31 tests are example-based; signing-string composition over arbitrary paths, queries and bodies, and paginator aggregation totality, are the natural candidates.
- [ ] 60. Add a gated live-API smoke test. Nothing currently exercises a real OCI endpoint, and signing is the one concern where a working offline test does not guarantee acceptance.
- [ ] 61. No instance-principal or resource-principal authentication. API-key signing is the only supported credential kind.
- [ ] 62. No work-request polling. OCI reports long-running operations through work requests, and nothing here waits on one.
