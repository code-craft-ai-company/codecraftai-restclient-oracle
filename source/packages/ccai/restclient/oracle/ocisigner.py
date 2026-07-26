"""
    .. module:: ocisigner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI API-key request signing.

    Oracle Cloud authenticates with the HTTP Signature scheme: a set of
    request headers is concatenated into a signing string, signed RSA-SHA256
    with the caller's API private key, and presented in an ``Authorization``
    header naming which headers were covered.

    Which headers are covered depends on the method.  A bodiless request signs
    ``(request-target)``, ``host`` and ``date``.  A request WITH a body also
    signs ``x-content-sha256``, ``content-type`` and ``content-length`` —
    which is what binds the body to the signature.  Omitting them on a POST
    would produce a signature the service rejects, and, worse, would leave the
    body unauthenticated if it were ever accepted.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import base64
import email.utils
import hashlib
import os

from typing import Any, Dict, List, Optional, Tuple
import urllib.parse


# Methods that carry a body, and therefore sign the body headers too.
BODY_METHODS = ("POST", "PUT", "PATCH")

HEADERS_WITHOUT_BODY = ("(request-target)", "host", "date")

HEADERS_WITH_BODY = ("(request-target)", "host", "date",
                     "x-content-sha256", "content-type", "content-length")

SIGNATURE_VERSION = "1"


class OciSigningError(Exception):
    """
        Raised when a request cannot be signed.
    """


class OciRequestSigner:
    """
        Signs OCI requests with an API key.

        :ivar key_id: The composite key identifier OCI expects, of the form
            ``tenancy/user/fingerprint``.
    """

    def __init__(self, *, tenancy: str, user: str, fingerprint: str,
                 private_key: str,
                 pass_phrase: Optional[str] = None) -> None:
        """
            Construct an OciRequestSigner.

            :param tenancy: The tenancy OCID.
            :param user: The user OCID.
            :param fingerprint: The API key's fingerprint.
            :param private_key: The API private key, PEM encoded.
            :param pass_phrase: Optional passphrase protecting the key.
        """
        self._tenancy = tenancy
        self._user = user
        self._fingerprint = fingerprint
        self._private_key_text = private_key
        self._pass_phrase = pass_phrase
        self._private_key: Any = None
        return

    @property
    def key_id(self) -> str:
        """
            Return the composite key identifier.

            :returns: ``tenancy/user/fingerprint``.
        """
        rtnval = "{}/{}/{}".format(self._tenancy, self._user,
                                   self._fingerprint)
        return rtnval

    def _load_key(self) -> Any:
        """
            Load and cache the RSA private key.

            :returns: The private key.

            :raises: :class:`OciSigningError` when the key cannot be loaded
                or is not an RSA key.
        """
        if self._private_key is not None:
            rtnval = self._private_key
            return rtnval

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        material = self._private_key_text
        if material is None or len(material) == 0:
            err_msg = "No API private key is available to sign the request."
            raise OciSigningError(err_msg)

        # A PEM round-tripped through an environment variable arrives with
        # literal backslash-n sequences.
        encoded = material.replace("\\n", "\n").encode("utf-8")

        password = None
        if self._pass_phrase is not None and len(self._pass_phrase) > 0:
            password = self._pass_phrase.encode("utf-8")

        try:
            loaded = serialization.load_pem_private_key(encoded,
                                                       password=password)
        except Exception as xcpt:
            err_msg_lines = ["The OCI API private key could not be loaded."]
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciSigningError(err_msg) from None

        if isinstance(loaded, rsa.RSAPrivateKey) is False:
            err_msg_lines = [
                "The OCI API key must be an RSA key; OCI signs RSA-SHA256."
            ]
            err_msg_lines.append("ACTUAL: {}".format(type(loaded).__name__))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciSigningError(err_msg)

        self._private_key = loaded
        rtnval = loaded
        return rtnval

    def sign(self, *, method: str, url: str, body: Optional[bytes] = None,
             headers: Optional[Dict[str, str]] = None,
             now: Optional[str] = None) -> Dict[str, str]:
        """
            Return the headers that authenticate one request.

            The returned mapping is the COMPLETE set to send: the caller's own
            headers plus ``host``, ``date``, ``Authorization`` and, for a
            request with a body, ``x-content-sha256`` / ``content-type`` /
            ``content-length``.  Those body headers are part of the signature,
            so sending a different set than was signed fails.

            :param method: The HTTP method.
            :param url: The absolute request URL.
            :param body: The request body, or None.
            :param headers: Any caller headers to include.
            :param now: The RFC 1123 date to sign; defaults to now.
                Injectable so signatures are reproducible in tests.

            :returns: The headers to send.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        parsed = urllib.parse.urlsplit(url)

        target = parsed.path
        if len(parsed.query) > 0:
            target = "{}?{}".format(target, parsed.query)

        moment = now
        if moment is None:
            moment = email.utils.formatdate(usegmt=True)

        to_send: Dict[str, str] = {}
        if headers is not None:
            for name, value in headers.items():
                to_send[name] = value

        to_send["host"] = parsed.netloc
        to_send["date"] = moment

        upper = method.upper()
        carries_body = upper in BODY_METHODS

        if carries_body is True:
            payload = body if body is not None else b""
            digest = base64.b64encode(
                hashlib.sha256(payload).digest()).decode("ascii")
            to_send["x-content-sha256"] = digest
            to_send["content-length"] = str(len(payload))
            if "content-type" not in {key.lower() for key in to_send}:
                to_send["content-type"] = "application/json"
            covered = HEADERS_WITH_BODY
        else:
            covered = HEADERS_WITHOUT_BODY

        lowered = {key.lower(): value for key, value in to_send.items()}

        parts: List[str] = []
        for name in covered:
            if name == "(request-target)":
                parts.append("(request-target): {} {}".format(
                    upper.lower(), target))
                continue
            parts.append("{}: {}".format(name, lowered.get(name, "")))

        signing_string = "\n".join(parts)

        private_key = self._load_key()
        signature = private_key.sign(signing_string.encode("utf-8"),
                                     padding.PKCS1v15(), hashes.SHA256())

        authorization = (
            'Signature version="{}",keyId="{}",algorithm="rsa-sha256",'
            'headers="{}",signature="{}"'.format(
                SIGNATURE_VERSION, self.key_id, " ".join(covered),
                base64.b64encode(signature).decode("ascii"))
        )

        to_send["Authorization"] = authorization

        rtnval = to_send
        return rtnval

    def signing_string(self, *, method: str, url: str,
                       body: Optional[bytes] = None,
                       headers: Optional[Dict[str, str]] = None,
                       now: str = "") -> Tuple[str, Tuple[str, ...]]:
        """
            Build the signing string without signing it.

            Exposed so tests can assert exactly which headers are covered and
            in what order, which is the part of the scheme most easily got
            subtly wrong.

            :param method: The HTTP method.
            :param url: The absolute request URL.
            :param body: The request body, or None.
            :param headers: Any caller headers.
            :param now: The date to sign.

            :returns: A ``(signing_string, covered_headers)`` pair.
        """
        parsed = urllib.parse.urlsplit(url)

        target = parsed.path
        if len(parsed.query) > 0:
            target = "{}?{}".format(target, parsed.query)

        upper = method.upper()
        carries_body = upper in BODY_METHODS

        values: Dict[str, str] = {"host": parsed.netloc, "date": now}
        if headers is not None:
            for name, value in headers.items():
                values[name.lower()] = value

        if carries_body is True:
            payload = body if body is not None else b""
            values["x-content-sha256"] = base64.b64encode(
                hashlib.sha256(payload).digest()).decode("ascii")
            values["content-length"] = str(len(payload))
            values.setdefault("content-type", "application/json")
            covered = HEADERS_WITH_BODY
        else:
            covered = HEADERS_WITHOUT_BODY

        parts: List[str] = []
        for name in covered:
            if name == "(request-target)":
                parts.append("(request-target): {} {}".format(
                    upper.lower(), target))
                continue
            parts.append("{}: {}".format(name, values.get(name, "")))

        rtnval = ("\n".join(parts), covered)
        return rtnval
