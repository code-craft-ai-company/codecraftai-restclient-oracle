# Requirements

## Introduction

The `oracle-client` feature provides a pure-Python client for Oracle Cloud
Infrastructure, replacing the `oci` SDK for the provisioning venue. Every OCI
service is JSON over HTTPS authenticated with an HTTP-Signature
`Authorization` header, differing only in hostname and API version, so one
signed transport serves all seven service clients: `VirtualNetworkClient`,
`ComputeClient`, `ComputeManagementClient`, `BlockstorageClient`,
`ObjectStorageClient`, `DnsClient` and `FileStorageClient`.

Request signing is the package's most exacting concern and the reason it does
not use a vendor SDK. `ocisigner` owns it; `ocitransport` owns transport and
error classification; `ocipagination` replaces
`oci.pagination.list_call_get_all_results`, which the venue calls directly;
`ocimodels` holds the request-body models and the response objects; `ocierror`
holds the error types.

The package lives at `source/packages/ccai/restclient/oracle` and its runtime
dependencies are `requests` and `cryptography`. It does not import
`RestClientBase`, does not take an `aspects` parameter, and takes key material
as plain strings rather than a typed credential — all three are recorded as
open items in `tasks.md`.

The governing constraint throughout is SDK compatibility. Method names,
keyword names and response attribute names match `oci` exactly, including its
inconsistencies, because consumer call sites already pass them that way.

---

## Requirements

### Requirement 1: Sign Requests With the HTTP Signature Scheme

**User Story:** As a caller, I want every request signed with the tenancy's
API key so that OCI accepts it and the request cannot be altered in transit.

#### Acceptance Criteria

1. THE SYSTEM SHALL present a key identifier of the form
   `tenancy/user/fingerprint`.
2. THE SYSTEM SHALL build a signing string from the covered headers, one per
   line as `name: value`, sign it RSA-SHA256 with PKCS1v15 padding, and emit
   an `Authorization` header of the form
   `Signature version="1",keyId="...",algorithm="rsa-sha256",headers="...",signature="..."`.
3. WHEN the method is bodiless THE SYSTEM SHALL cover `(request-target)`,
   `host` and `date`.
4. WHEN the method is POST, PUT or PATCH THE SYSTEM SHALL additionally cover
   `x-content-sha256`, `content-type` and `content-length` — those are what
   bind the body to the signature. Omitting them produces a signature the
   service rejects and, worse, would leave the body unauthenticated if it were
   ever accepted.
5. THE SYSTEM SHALL compute `x-content-sha256` as the base64 of the body's
   SHA-256 digest, treating an absent body on a body-bearing method as empty
   bytes, and SHALL default `content-type` to `application/json` when the
   caller supplied none.
6. THE SYSTEM SHALL include the query string in `(request-target)`, so the
   query is signed.
7. THE SYSTEM SHALL return the COMPLETE header set to send — caller headers
   plus `host`, `date`, `Authorization` and the body headers — because sending
   a different set than was signed fails.
8. THE SYSTEM SHALL accept an injected RFC 1123 date so signatures are
   reproducible in tests, and SHALL otherwise use the current time.
9. THE SYSTEM SHALL load the PEM private key lazily, cache it, accept
   an optional passphrase, and accept PEM material carrying literal `\n`
   sequences from an environment-variable round trip.
10. WHEN the key cannot be loaded, is absent, or is not an RSA key THE SYSTEM
    SHALL raise `OciSigningError` identifying the cause.
11. THE SYSTEM SHALL expose the signing string separately from the signature
    so tests can assert exactly which headers are covered and in what order,
    which is the part of the scheme most easily got subtly wrong.

### Requirement 2: Perform Signed Requests and Classify Failures

**User Story:** As a service-client author, I want one transport that signs,
sends, classifies and decodes so that each service client only composes paths
and bodies.

#### Acceptance Criteria

1. THE SYSTEM SHALL drop query parameters whose value is `None`, and SHALL
   build the signed URL from the parameters actually sent, since the signature
   covers the query string.
2. THE SYSTEM SHALL encode a request body as UTF-8 JSON and sign that exact
   byte sequence.
3. WHEN the response status is 429 or 5xx THE SYSTEM SHALL raise
   `TransientServiceError`; for any other non-2xx status THE SYSTEM SHALL
   raise `ServiceError`. These are distinct because throttles and server
   faults are worth retrying and a 4xx is not — conflating them would retry a
   bad request forever.
4. THE SYSTEM SHALL populate `status`, `code`, `message` and `body` on the
   raised error, reading `code` and `message` from OCI's
   `{"code": ..., "message": ...}` body and falling back to the HTTP reason
   phrase when the body is unusable.
5. WHEN a success response carries a body THE SYSTEM SHALL decode and wrap it;
   WHEN it is not JSON THE SYSTEM SHALL keep the raw text as the data; WHEN it
   is empty THE SYSTEM SHALL leave the data `None`.
6. THE SYSTEM SHALL read the next-page token from the `opc-next-page` RESPONSE
   HEADER, not the body, matching case-insensitively.
7. THE SYSTEM SHALL accept an injected session object as the test seam and
   SHALL otherwise build its own `requests.Session`.

### Requirement 3: Preserve the SDK's Error Contract

**User Story:** As a teardown path, I want the OCI error code on the exception
so that I can tell `BucketNotEmpty` from `NotAuthorized`.

#### Acceptance Criteria

1. THE SYSTEM SHALL name the base error `ServiceError`, matching
   `oci.exceptions.ServiceError`, and SHALL expose `status`, `code` and
   `message` as the SDK did, because consumer code branches on them — treating
   those two codes alike would either leak storage or mask a permissions
   problem.
2. `TransientServiceError` SHALL derive from `ServiceError`, so a consumer
   that does not care about the distinction can catch the base.

### Requirement 4: Render Request Bodies From Typed Models

**User Story:** As a consumer migrating off the SDK, I want to keep
constructing `CreateVcnDetails(compartment_id=..., cidr_block=...)` so that my
call sites are unchanged.

#### Acceptance Criteria

1. THE SYSTEM SHALL accept snake_case keyword fields at construction and
   SHALL render them to camelCase JSON.
2. THE SYSTEM SHALL omit fields whose value is `None` rather than send
   explicit nulls, because OCI distinguishes "not supplied" from "explicitly
   null" on update calls.
3. THE SYSTEM SHALL serialise nested models, lists of models and dicts of
   models recursively.
4. THE SYSTEM SHALL allow fields to be read back and assigned by attribute,
   with an unset field reading as `None`, and SHALL raise `AttributeError` for
   underscore-prefixed names.
5. THE SYSTEM SHALL expose each SDK model name as a distinct named subclass
   rather than an alias, so a mistyped class name fails at import. The
   subclasses SHALL cover the 29 `*Details` and rule types the venue
   constructs.

### Requirement 5: Present Responses As the SDK Did

**User Story:** As a consumer, I want to read `instance.display_name` and
`response.data` so that my existing reads keep working against camelCase JSON.

#### Acceptance Criteria

1. THE SYSTEM SHALL return an object exposing `status`, `headers`, `data`,
   `request`, `next_page`, `request_id` and `has_next_page`, matching
   `oci.response.Response`, because the paginator reads several of them.
2. THE SYSTEM SHALL wrap decoded payloads so a field is readable in either
   spelling, matching on a normalised form — underscores removed, lowercased —
   rather than converting camelCase to snake_case, which keeps
   acronym-bearing names such as `rr_set`/`rrSet` and `vnic_id`/`vnicId`
   working without special cases.
3. WHEN a field is absent THE SYSTEM SHALL return `None`. OCI's optional
   fields really are absent, unlike the protobuf-derived zero values the
   Google client in this fleet must present.
4. THE SYSTEM SHALL wrap nested objects and lists so a second attribute hop
   resolves, and SHALL expose `as_dict()` returning the plain wire dictionary.

### Requirement 6: Aggregate Paginated Listings

**User Story:** As a teardown path calling
`list_call_get_all_results` directly, I want one response carrying every page
so that I do not leak resources that fell past the first page.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose `list_call_get_all_results(list_func, *args,
   **kwargs)` at module scope, matching the SDK helper the venue calls
   directly rather than through a client method.
2. THE SYSTEM SHALL call the list operation repeatedly, passing the previous
   response's `next_page` as the `page` keyword, until no token is returned.
3. THE SYSTEM SHALL return ONE response whose `data` is every page's entries
   concatenated, whose `next_page` is `None`, and whose `status`, `headers`
   and `request` come from the final page.
4. WHEN an operation answers with data that is not a list THE SYSTEM SHALL
   raise `TypeError` rather than silently build a malformed aggregate.
5. THE SYSTEM SHALL additionally expose a generator form yielding every entry
   across all pages.

### Requirement 7: Cover the Service Surface the Venue Uses

**User Story:** As a provisioner, I want the OCI operations a full host
lifecycle needs so that the venue can be driven through this client.

#### Acceptance Criteria

1. THE SYSTEM SHALL build regional endpoints as
   `https://{service}.{region}.{domain}`, defaulting the domain to
   `oraclecloud.com`, and SHALL accept an explicit endpoint override.
2. THE SYSTEM SHALL accept the OCI config dict POSITIONALLY at construction,
   matching how the SDK clients were built and how the venue's session factory
   calls them, taking the region from it when not passed explicitly.
3. THE SYSTEM SHALL place the API version as a path segment after the host:
   `20160918` for the Core Services clients, `20180115` for DNS, `20171215`
   for File Storage. Object Storage SHALL have NO version segment.
4. `VirtualNetworkClient` SHALL cover create, delete and list for VCNs,
   subnets, internet gateways, route tables and security lists.
5. `ComputeClient` SHALL cover `launch_instance`, `terminate_instance`,
   `list_instances`, `list_images`, `attach_volume` and
   `list_volume_attachments` (filterable by `instance_id` and / or
   `volume_id`).
6. `ComputeManagementClient` SHALL cover `create_instance_configuration`,
   `create_cluster_network`, `terminate_cluster_network` and
   `list_cluster_networks`.
7. `BlockstorageClient` SHALL cover `create_volume`, `delete_volume` and
   `list_volumes`.
8. `ObjectStorageClient` SHALL cover `get_namespace`, `create_bucket`,
   `get_bucket`, `delete_bucket` and `list_buckets`.
9. `DnsClient` SHALL cover `update_rr_set`, `delete_rr_set` and `list_zones`,
   addressing record sets by zone, domain and record type.
10. `FileStorageClient` SHALL cover `get_file_system`.
11. THE SYSTEM SHALL expose `build_clients(transport, region, domain)`
    returning every client under the keys `virtual_network`, `compute`,
    `compute_management`, `blockstorage`, `object_storage`, `dns` and
    `file_storage`.
12. THE SYSTEM SHALL accept arbitrary further filters as keyword arguments on
    list operations and render them as camelCase query parameters.

### Requirement 8: Reproduce the SDK's Naming Inconsistencies

**User Story:** As a consumer, I want the keyword names I already pass to keep
working so that migration does not require editing every call site.

#### Acceptance Criteria

1. THE SYSTEM SHALL name the details keyword `create_instance_configuration`
   on `ComputeManagementClient.create_instance_configuration`, without the
   `_details` suffix its sibling calls use.
2. THE SYSTEM SHALL abbreviate the identifier keyword as `ig_id` on
   `delete_internet_gateway` and `rt_id` on `delete_route_table`, while
   `delete_security_list` keeps the unabbreviated `security_list_id`.
3. THE SYSTEM SHALL NOT tidy these; they are the SDK's own inconsistencies and
   consumer code already passes them that way.
