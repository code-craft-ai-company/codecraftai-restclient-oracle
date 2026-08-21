# Design

## Overview

`codecraftai-restclient-oracle` is a pure-Python client for Oracle Cloud
Infrastructure. It exists to remove the `oci` SDK dependency from the
provisioning venue while keeping the SDK's call shapes, keyword names, response
attributes and error contract intact.

OCI is uniform in the ways that matter here: every service is JSON over HTTPS,
authenticated with the same HTTP-Signature scheme, differing only in hostname
and API version. So one signer and one transport sit under seven thin service
clients, each of which contributes little more than a hostname prefix, a
version segment and a set of paths.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  codecraftai-provisioning / venues / oracle                  │
│  (also calls list_call_get_all_results directly)             │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
   ┌──────────────────────────────────────────────────────┐
   │  build_clients() → 7 service clients                 │
   │  virtual_network · compute · compute_management      │
   │  blockstorage · object_storage · dns · file_storage  │
   └──────────────────────────┬───────────────────────────┘
                              ▼
                  ┌────────────────────────┐
                  │      OciTransport      │  signs, sends,
                  │                        │  classifies, decodes
                  └───────────┬────────────┘
                              ▼
                  ┌────────────────────────┐
                  │    OciRequestSigner    │  RSA-SHA256 over a
                  │                        │  canonical header set
                  └────────────────────────┘
```

---

## Module Layout

```
source/packages/ccai/restclient/oracle/
├── __init__.py
├── ocisigner.py       # OciRequestSigner, OciSigningError
├── ocitransport.py    # OciTransport
├── ocimodels.py       # OciModel + named subclasses, OciObject, Response
├── ocipagination.py   # list_call_get_all_results (+ generator form)
├── ociclients.py      # the seven service clients, build_clients
└── ocierror.py        # ServiceError, TransientServiceError
```

---

## Notable Choices

**The covered header set is method-dependent, and that is the whole game.** A
bodiless request signs `(request-target)`, `host` and `date`. A body-bearing
one also signs `x-content-sha256`, `content-type` and `content-length`, which
is what binds the body to the signature. Getting this wrong fails closed in
the ordinary case — OCI rejects the signature — but the failure mode that
matters is the other one: a scheme that accepted the short set would leave
request bodies unauthenticated. `signing_string()` exists as a separate public
method precisely so tests can assert the covered set and its order directly,
rather than inferring it from a signature that either verifies or does not.

**The signature covers the query string, so the transport builds the signed
URL from the parameters it is about to send** rather than from the bare path.
This is the one place where the transport has to think about the signer's
requirements instead of treating it as a black box.

**One model class, twenty-nine names.** The SDK's `*Details` types are all
plain data holders with no behaviour, so `OciModel` implements all of them.
The named subclasses are generated from `MODEL_NAMES` and exist for exactly
two reasons: call sites read as they did before, and a mistyped class name
still fails at import rather than at request time. Unset fields are omitted
from the rendered body rather than sent as null, because OCI treats "not
supplied" and "explicitly null" differently on updates — sending null would
clear a field the caller never mentioned.

**Field lookup normalises rather than converts.** `OciObject.__getattr__`
compares `normalize_name` of the requested name against `normalize_name` of
each key. A camelCase-to-snake_case converter would need a rule for every
acronym; normalising both sides makes `rr_set`/`rrSet` and `vnic_id`/`vnicId`
work without special cases. Absent fields read as `None`, which is the honest
answer for OCI — its optional fields really are absent. This is the opposite
of the Google client in this fleet, which must present protobuf zero values
because its consumers guard on `!= 0` and `len()`.

**The paginator is part of the public surface, not an internal helper.** The
venue calls `oci.pagination.list_call_get_all_results` directly, so replacing
the clients alone would not have been enough. It follows `next_page` until
exhausted and returns one response whose `data` is every page concatenated;
callers treat that as a complete listing, and a truncated one would
under-report owned resources, which on a teardown path means leaked
infrastructure. It raises `TypeError` on a non-list operation rather than
build a malformed aggregate from a single object.

**Transient failures are a distinct type, not a retry.** The transport
classifies 429 and 5xx as `TransientServiceError` and everything else non-2xx
as `ServiceError`, then raises. It does not retry — classification is where
this package's responsibility currently ends, and the caller decides policy.
The two types are separate because retrying a 4xx forever is worse than
failing it.

**SDK inconsistencies are reproduced deliberately.** The details keyword is
`create_vcn_details` for one call and `create_instance_configuration` for
another; identifiers are abbreviated for internet gateways (`ig_id`) and route
tables (`rt_id`) but not for security lists (`security_list_id`). Object
Storage has no version segment while every other service does. Each of these
is the SDK's own shape, and consumer code already passes them that way, so
tidying them would break the call sites this package exists to keep working.

---

## Relationship to `codecraftai-restclient-base`

The clients do not subclass `RestClientBase` and take no `aspects` parameter,
though `pyproject.toml` declares `codecraftai-restclient-base`,
`codecraftai-credentials` and `codecraftai-errors` as dependencies. Nothing
under `source/packages` imports any of the three; tenancy, user, fingerprint
and PEM key material enter `OciRequestSigner.__init__` as plain strings. Both
divergences are open items in `tasks.md`, recorded here so this design is not
read as claiming a base-class integration that does not exist.

---

## Testing Strategy

Tests live at
`source/testroots/testbase/ccai/tests/restclient/oracle/test_ociclient.py`
and run under the testbase runner, not pytest:

```
PYTHONPATH="$PWD/source/packages:$PWD/source/testroots/testbase" \
    .venv/bin/testbase testing run --root source/testroots/testbase/ccai \
    --includes="*" --output=./.output
```

The suite is example-based and offline. `FakeSession` records every call and
replays responses queued against a `METHOD substring` key; `FakeResponse`
stands in for `requests.Response` including its headers, which matters because
the next-page token arrives there. A fresh RSA key pair is generated per
signing test.

The signing tests carry the most weight, since this is real asymmetric crypto
and a self-consistent but wrong signature would stay invisible until OCI
rejected it in production. So one test verifies a produced signature against
its own public key, and the rest assert the structural properties that
verification alone would not catch: that a bodiless request covers exactly
three headers and a body-bearing one covers six, that the digest changes with
the body, that the query string appears in `(request-target)`, and that the
`Authorization` header names the covered set.

The remainder covers model rendering (camelCase, omitted nulls, nested
serialisation), snake_case response reads with `None` for absent, the
transient-versus-permanent error split across 429/500/503, the OCI error code
on the exception, next-page extraction from the header, paginator aggregation
and its non-list refusal, per-service hostnames and version segments, and the
three reproduced SDK naming inconsistencies.
