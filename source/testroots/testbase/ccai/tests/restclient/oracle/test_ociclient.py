"""
    .. module:: test_ociclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the Oracle Cloud Infrastructure client.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import base64
import json

from typing import Any, Dict, List, Optional

import pytest

from ccai.restclient.oracle import ocimodels
from ccai.restclient.oracle.ociclients import build_clients
from ccai.restclient.oracle.ocierror import (
    ServiceError, TransientServiceError
)
from ccai.restclient.oracle.ocimodels import (
    OciObject, Response, to_camel
)
from ccai.restclient.oracle.ocipagination import list_call_get_all_results
from ccai.restclient.oracle.ocisigner import (
    HEADERS_WITHOUT_BODY, HEADERS_WITH_BODY, OciRequestSigner,
    OciSigningError
)
from ccai.restclient.oracle.ocitransport import OciTransport


REGION = "us-ashburn-1"


class FakeResponse:
    """
        Minimal stand-in for a ``requests.Response``.
    """

    def __init__(self, *, status_code: int = 200,
                 payload: Optional[Any] = None, text: Optional[str] = None,
                 reason: str = "OK",
                 headers: Optional[Dict[str, str]] = None) -> None:
        self.status_code = status_code
        self.reason = reason
        self.headers = headers or {}
        if text is not None:
            self.text = text
        elif payload is not None:
            self.text = json.dumps(payload)
        else:
            self.text = ""
        self._payload = payload

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class FakeSession:
    """
        Records requests and replays queued responses.
    """

    def __init__(self) -> None:
        self.headers: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []
        self.responses: Dict[str, List[FakeResponse]] = {}
        self.default_response = FakeResponse(payload={})

    def queue(self, *, method: str, match: str,
              response: FakeResponse) -> None:
        key = "{} {}".format(method.upper(), match)
        self.responses.setdefault(key, []).append(response)
        return

    def request(self, method: str, url: str, params=None, data=None,
                headers=None, timeout=None) -> FakeResponse:
        body = None
        if data is not None:
            body = json.loads(data.decode("utf-8")
                              if isinstance(data, bytes) else data)

        self.calls.append({"method": method, "url": url,
                           "params": params or {}, "body": body,
                           "headers": headers or {}})

        for key, queued in self.responses.items():
            wanted_method, _, wanted = key.partition(" ")
            if method.upper() == wanted_method and wanted in url:
                if len(queued) > 0:
                    rtnval = queued.pop(0)
                    return rtnval

        rtnval = self.default_response
        return rtnval


def _generate_key():
    """
        Generate an RSA key pair for signature tests.

        :returns: A ``(pem, public_key)`` pair.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537,
                                           key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()).decode("ascii")
    return pem, private_key.public_key()


def _signer(pem=None):
    if pem is None:
        pem, _ = _generate_key()
    built = OciRequestSigner(tenancy="ocid1.tenancy.oc1..t",
                             user="ocid1.user.oc1..u",
                             fingerprint="aa:bb:cc", private_key=pem)
    return built


def _clients(session=None, pem=None):
    if session is None:
        session = FakeSession()
    transport = OciTransport(signer=_signer(pem), session=session)
    built = build_clients(transport=transport, region=REGION)
    return built, session


# ----------------------------------------------------------------------
# signing
# ----------------------------------------------------------------------

def test_key_id_is_the_composite_identifier():
    signer = _signer()

    assert signer.key_id == "ocid1.tenancy.oc1..t/ocid1.user.oc1..u/aa:bb:cc"
    return


def test_signature_verifies_against_the_public_key():
    """
        The signature must actually verify — this is real asymmetric crypto,
        so a self-consistent but wrong signature would stay invisible until
        OCI rejected it.
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    pem, public_key = _generate_key()
    signer = _signer(pem)

    url = "https://iaas.us-ashburn-1.oraclecloud.com/20160918/vcns"
    date = "Mon, 26 Jul 2026 12:00:00 GMT"

    headers = signer.sign(method="GET", url=url, now=date)
    signing_string, _ = signer.signing_string(method="GET", url=url,
                                              now=date)

    authorization = headers["Authorization"]
    encoded = authorization.split('signature="')[1].rstrip('"')
    signature = base64.b64decode(encoded)

    # Raises InvalidSignature if the signing string or algorithm is wrong.
    public_key.verify(signature, signing_string.encode("utf-8"),
                      padding.PKCS1v15(), hashes.SHA256())
    return


def test_bodiless_request_signs_three_headers():
    signer = _signer()
    url = "https://iaas.us-ashburn-1.oraclecloud.com/20160918/vcns"

    signing_string, covered = signer.signing_string(
        method="GET", url=url, now="Mon, 26 Jul 2026 12:00:00 GMT")

    assert covered == HEADERS_WITHOUT_BODY
    assert signing_string.splitlines()[0] == \
        "(request-target): get /20160918/vcns"
    assert "host: iaas.us-ashburn-1.oraclecloud.com" in signing_string
    return


def test_request_with_a_body_also_signs_the_body_headers():
    signer = _signer()
    url = "https://iaas.us-ashburn-1.oraclecloud.com/20160918/vcns"
    body = b'{"cidrBlock": "10.0.0.0/16"}'

    signing_string, covered = signer.signing_string(
        method="POST", url=url, body=body,
        now="Mon, 26 Jul 2026 12:00:00 GMT")

    # These are what bind the body to the signature; omitting them would
    # leave the body unauthenticated.
    assert covered == HEADERS_WITH_BODY
    assert "x-content-sha256: " in signing_string
    assert "content-length: {}".format(len(body)) in signing_string
    assert "content-type: application/json" in signing_string
    return


def test_body_digest_changes_with_the_body():
    signer = _signer()
    url = "https://iaas.us-ashburn-1.oraclecloud.com/20160918/vcns"

    first, _ = signer.signing_string(method="POST", url=url, body=b"a",
                                     now="d")
    second, _ = signer.signing_string(method="POST", url=url, body=b"b",
                                      now="d")

    assert first != second
    return


def test_query_string_is_part_of_the_request_target():
    signer = _signer()

    signing_string, _ = signer.signing_string(
        method="GET",
        url="https://iaas.us-ashburn-1.oraclecloud.com/20160918/vcns"
            "?compartmentId=abc",
        now="d")

    assert signing_string.splitlines()[0] == \
        "(request-target): get /20160918/vcns?compartmentId=abc"
    return


def test_authorization_header_names_the_covered_headers():
    signer = _signer()

    headers = signer.sign(
        method="GET",
        url="https://iaas.us-ashburn-1.oraclecloud.com/20160918/vcns",
        now="Mon, 26 Jul 2026 12:00:00 GMT")

    authorization = headers["Authorization"]
    assert 'algorithm="rsa-sha256"' in authorization
    assert 'headers="(request-target) host date"' in authorization
    assert 'keyId="{}"'.format(signer.key_id) in authorization
    return


def test_unusable_key_is_reported():
    signer = OciRequestSigner(tenancy="t", user="u", fingerprint="f",
                              private_key="-----BEGIN PRIVATE KEY-----\n"
                                          "nope\n"
                                          "-----END PRIVATE KEY-----\n")

    with pytest.raises(OciSigningError):
        signer.sign(method="GET", url="https://host/x", now="d")
    return


# ----------------------------------------------------------------------
# models
# ----------------------------------------------------------------------

def test_models_render_camel_case_bodies():
    details = ocimodels.CreateVcnDetails(
        compartment_id="ocid1.compartment", cidr_block="10.0.0.0/16",
        display_name="net-a")

    body = details.to_body()
    assert body == {"compartmentId": "ocid1.compartment",
                    "cidrBlock": "10.0.0.0/16", "displayName": "net-a"}
    return


def test_unset_model_fields_are_omitted():
    details = ocimodels.CreateVcnDetails(compartment_id="c",
                                         display_name=None)

    # OCI distinguishes "not supplied" from "explicitly null" on updates.
    assert "displayName" not in details.to_body()
    return


def test_nested_models_are_serialized():
    rule = ocimodels.IngressSecurityRule(
        protocol="6", source="0.0.0.0/0",
        tcp_options=ocimodels.TcpOptions(
            destination_port_range=ocimodels.PortRange(min=22, max=22)))
    details = ocimodels.CreateSecurityListDetails(
        compartment_id="c", ingress_security_rules=[rule])

    body = details.to_body()
    nested = body["ingressSecurityRules"][0]
    assert nested["protocol"] == "6"
    assert nested["tcpOptions"]["destinationPortRange"] == {"min": 22,
                                                            "max": 22}
    return


def test_model_fields_read_back_by_attribute():
    details = ocimodels.CreateVcnDetails(compartment_id="c")

    assert details.compartment_id == "c"
    assert details.display_name is None
    return


def test_to_camel_leaves_single_words_alone():
    assert to_camel("protocol") == "protocol"
    assert to_camel("compartment_id") == "compartmentId"
    return


def test_response_objects_read_snake_case():
    obj = OciObject({"displayName": "net-a", "lifecycleState": "AVAILABLE",
                     "id": "ocid1.vcn"})

    assert obj.display_name == "net-a"
    assert obj.lifecycle_state == "AVAILABLE"
    # OCI's optional fields really are absent, unlike protobuf's zero values.
    assert obj.freeform_tags is None
    return


# ----------------------------------------------------------------------
# transport
# ----------------------------------------------------------------------

def test_request_is_signed_and_sent():
    clients, session = _clients()
    session.queue(method="GET", match="/vcns",
                  response=FakeResponse(payload={"id": "ocid1.vcn"}))

    clients["virtual_network"].list_vcns(compartment_id="ocid1.compartment")

    call = session.calls[0]
    assert call["headers"]["Authorization"].startswith("Signature version=")
    assert call["params"]["compartmentId"] == "ocid1.compartment"
    return


def test_error_carries_the_oci_code():
    clients, session = _clients()
    session.queue(method="DELETE", match="/b/bkt-a/",
                  response=FakeResponse(
                      status_code=409, reason="Conflict",
                      payload={"code": "BucketNotEmpty",
                               "message": "bucket is not empty"}))

    with pytest.raises(ServiceError) as caught:
        clients["object_storage"].delete_bucket(namespace_name="ns",
                                                bucket_name="bkt-a")

    # Callers branch on the code; BucketNotEmpty and NotAuthorized need
    # different handling.
    assert caught.value.code == "BucketNotEmpty"
    assert caught.value.status == 409
    return


@pytest.mark.parametrize("status", [429, 500, 503])
def test_throttles_and_server_faults_are_transient(status):
    clients, session = _clients()
    session.queue(method="GET", match="/vcns",
                  response=FakeResponse(status_code=status, reason="x",
                                        payload={"code": "TooManyRequests",
                                                 "message": "slow down"}))

    with pytest.raises(TransientServiceError):
        clients["virtual_network"].list_vcns(compartment_id="c")
    return


def test_client_errors_are_not_transient():
    clients, session = _clients()
    session.queue(method="GET", match="/vcns",
                  response=FakeResponse(status_code=404, reason="Not Found",
                                        payload={"code": "NotFound",
                                                 "message": "no"}))

    with pytest.raises(ServiceError) as caught:
        clients["virtual_network"].list_vcns(compartment_id="c")

    # Retrying a bad request forever would be worse than failing.
    assert isinstance(caught.value, TransientServiceError) is False
    return


def test_next_page_token_is_read_from_the_header():
    clients, session = _clients()
    session.queue(method="GET", match="/vcns",
                  response=FakeResponse(payload=[{"id": "a"}],
                                        headers={"opc-next-page": "tok-1"}))

    response = clients["virtual_network"].list_vcns(compartment_id="c")

    # OCI returns the token in a header, not the body.
    assert response.next_page == "tok-1"
    assert response.has_next_page is True
    return


# ----------------------------------------------------------------------
# pagination
# ----------------------------------------------------------------------

def test_paginator_aggregates_every_page():
    pages = [Response(data=[1, 2], next_page="p2"),
             Response(data=[3], next_page="p3"),
             Response(data=[4], next_page=None)]
    seen: List[Any] = []

    def _list(**kwargs):
        seen.append(kwargs.get("page", None))
        return pages.pop(0)

    result = list_call_get_all_results(_list, compartment_id="c")

    assert result.data == [1, 2, 3, 4]
    assert seen == [None, "p2", "p3"]
    assert result.next_page is None
    return


def test_paginator_stops_on_a_single_page():
    def _list(**kwargs):
        return Response(data=[1], next_page=None)

    result = list_call_get_all_results(_list, compartment_id="c")

    assert result.data == [1]
    return


def test_paginator_refuses_a_non_list_operation():
    def _list(**kwargs):
        return Response(data=OciObject({"id": "x"}), next_page=None)

    # Silently accepting this would produce a malformed aggregate.
    with pytest.raises(TypeError):
        list_call_get_all_results(_list, compartment_id="c")
    return


# ----------------------------------------------------------------------
# client paths
# ----------------------------------------------------------------------

def test_core_services_share_one_host_and_version():
    clients, session = _clients()

    assert clients["virtual_network"].base_url == \
        "https://iaas.us-ashburn-1.oraclecloud.com"
    assert clients["compute"].base_url == \
        "https://iaas.us-ashburn-1.oraclecloud.com"
    assert clients["blockstorage"].base_url == \
        "https://iaas.us-ashburn-1.oraclecloud.com"
    return


def test_each_service_has_its_own_host():
    clients, session = _clients()

    assert clients["object_storage"].base_url.startswith(
        "https://objectstorage.")
    assert clients["dns"].base_url.startswith("https://dns.")
    assert clients["file_storage"].base_url.startswith(
        "https://filestorage.")
    return


def test_create_vcn_posts_the_rendered_details():
    clients, session = _clients()
    session.queue(method="POST", match="/vcns",
                  response=FakeResponse(payload={"id": "ocid1.vcn"}))

    details = ocimodels.CreateVcnDetails(compartment_id="c",
                                         cidr_block="10.0.0.0/16")
    response = clients["virtual_network"].create_vcn(
        create_vcn_details=details)

    call = session.calls[0]
    assert call["url"].endswith("/20160918/vcns")
    assert call["body"] == {"compartmentId": "c",
                            "cidrBlock": "10.0.0.0/16"}
    assert response.data.id == "ocid1.vcn"
    return


def test_abbreviated_identifier_keywords_are_preserved():
    clients, session = _clients()

    clients["virtual_network"].delete_internet_gateway(ig_id="ocid1.ig")
    clients["virtual_network"].delete_route_table(rt_id="ocid1.rt")

    # The SDK abbreviates these two and not their siblings; consumer code
    # already passes them that way.
    assert session.calls[0]["url"].endswith("/internetGateways/ocid1.ig")
    assert session.calls[1]["url"].endswith("/routeTables/ocid1.rt")
    return


def test_instance_configuration_keyword_lacks_the_details_suffix():
    clients, session = _clients()

    details = ocimodels.CreateInstanceConfigurationDetails(compartment_id="c")
    clients["compute_management"].create_instance_configuration(
        create_instance_configuration=details)

    assert session.calls[0]["url"].endswith("/instanceConfigurations")
    return


def test_object_storage_paths_are_unversioned():
    clients, session = _clients()

    clients["object_storage"].get_bucket(namespace_name="ns",
                                         bucket_name="bkt-a")

    # Object Storage is the one service without a version segment.
    assert session.calls[0]["url"].endswith("/n/ns/b/bkt-a/")
    return


def test_dns_record_paths_carry_domain_and_type():
    clients, session = _clients()

    details = ocimodels.UpdateRRSetDetails(items=[
        ocimodels.RecordDetails(domain="a.example.com", rtype="A",
                                rdata="1.2.3.4", ttl=300)])
    clients["dns"].update_rr_set(zone_name_or_id="example.com",
                                 domain="a.example.com", rtype="A",
                                 update_rr_set_details=details)

    call = session.calls[0]
    assert call["url"].endswith("/zones/example.com/records/a.example.com/A")
    assert call["body"]["items"][0]["rdata"] == "1.2.3.4"
    return


def test_file_storage_get_uses_its_own_version():
    clients, session = _clients()

    clients["file_storage"].get_file_system(file_system_id="ocid1.fs")

    assert session.calls[0]["url"].endswith("/20171215/fileSystems/ocid1.fs")
    return


def test_launch_instance_and_terminate_paths():
    clients, session = _clients()

    details = ocimodels.LaunchInstanceDetails(compartment_id="c",
                                              display_name="vm-a")
    clients["compute"].launch_instance(launch_instance_details=details)
    clients["compute"].terminate_instance(instance_id="ocid1.instance")

    assert session.calls[0]["url"].endswith("/20160918/instances")
    assert session.calls[1]["method"] == "DELETE"
    assert session.calls[1]["url"].endswith("/instances/ocid1.instance")
    return
