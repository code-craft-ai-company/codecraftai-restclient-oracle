==============================
codecraftai-restclient-oracle
==============================

A pure-Python client for `Oracle Cloud Infrastructure
<https://docs.oracle.com/en-us/iaas/api/>`_, replacing the ``oci`` SDK.

Every OCI service is JSON over HTTPS with an HTTP-Signature ``Authorization``
header, differing only in hostname and API version, so one signed transport
serves all seven clients.

Design notes
============

**Which headers are signed depends on the method.** A bodiless request signs
``(request-target)``, ``host`` and ``date``.  A request WITH a body also signs
``x-content-sha256``, ``content-type`` and ``content-length`` — those are what
bind the body to the signature.  Omitting them on a POST produces a signature
the service rejects and, worse, would leave the body unauthenticated if it were
ever accepted.  The query string is part of ``(request-target)``, so it is
signed too.

**The paginator is part of the surface.** The venue calls
``oci.pagination.list_call_get_all_results`` directly rather than going through
a client method, so replacing the clients alone would not have been enough.
``ocipagination`` follows ``next_page`` until the listing is exhausted and
returns ONE response whose ``data`` is every page concatenated — a truncated
listing would under-report owned resources, which on a teardown path means
leaked infrastructure.  It refuses a non-list operation rather than silently
building a malformed aggregate.

**Request models are one class.** The SDK's twenty-nine ``*Details`` types are
all plain data holders, so ``OciModel`` serves them all; the named
subclasses exist so call sites read the same as before and a mistyped class
name still fails at import.  Fields left unset are omitted rather than sent as
null, because OCI distinguishes "not supplied" from "explicitly null" on
updates.

**SDK inconsistencies are reproduced, not tidied.** The details keyword is
``create_vcn_details`` for one call and ``create_instance_configuration`` for
another; identifiers are abbreviated for some resources (``ig_id``, ``rt_id``)
and not others (``security_list_id``).  Consumer code already passes them that
way.

**Responses are absent-as-None**, unlike the Google clients' protobuf zero
values — OCI's optional fields really are absent.

**Errors carry the OCI code.** ``ServiceError`` keeps its ``oci.exceptions``
name and its ``status`` / ``code`` / ``message`` attributes, because consumer
code branches on them: ``BucketNotEmpty`` and ``NotAuthorized`` need different
handling, and a teardown that treated them alike would either leak storage or
mask a permissions problem.  Throttles and server faults raise
``TransientServiceError``, separately, because those are worth retrying and a
4xx is not.
