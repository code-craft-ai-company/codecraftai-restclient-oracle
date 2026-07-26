"""
    .. module:: ocitransport
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: :class:`OciTransport` — the signed transport for OCI.

    Every OCI service is JSON over HTTPS with an HTTP-Signature
    ``Authorization`` header, differing only in hostname and API version, so
    one transport serves them all.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, Optional

import requests

from ccai.restclient.oracle.ocierror import (
    ServiceError, TransientServiceError
)
from ccai.restclient.oracle.ocimodels import Response, wrap
from ccai.restclient.oracle.ocisigner import OciRequestSigner


DEFAULT_TIMEOUT_SECONDS = 60.0

# OCI returns the token for the following page in this header rather than in
# the body, which is why listing needs the headers and not just the payload.
NEXT_PAGE_HEADER = "opc-next-page"


class OciTransport:
    """
        Signed JSON transport for the OCI services.
    """

    def __init__(self, *, signer: OciRequestSigner,
                 session: Optional[Any] = None,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        """
            Construct an OciTransport.

            :param signer: The request signer.
            :param session: Optional pre-built ``requests.Session`` — the test
                seam.
            :param timeout_seconds: The default per-request timeout.
        """
        self._signer = signer
        self._timeout_seconds = timeout_seconds

        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()
        return

    @property
    def signer(self) -> OciRequestSigner:
        """
            Return the request signer.

            :returns: The :class:`OciRequestSigner`.
        """
        rtnval = self._signer
        return rtnval

    def request(self, *, method: str, url: str,
                params: Optional[Dict[str, Any]] = None,
                body: Optional[Any] = None,
                timeout_seconds: Optional[float] = None) -> Response:
        """
            Perform one signed request.

            :param method: The HTTP method.
            :param url: The absolute URL.
            :param params: Optional query parameters; ``None`` values are
                dropped.
            :param body: Optional request body, already rendered to plain
                data.
            :param timeout_seconds: Optional per-request timeout override.

            :returns: A :class:`Response`.

            :raises: :class:`ServiceError` on a non-success status.
        """
        query: Dict[str, Any] = {}
        if params is not None:
            for key, value in params.items():
                if value is not None:
                    query[key] = value

        payload: Optional[bytes] = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")

        # The signature covers the query string, so it must be built against
        # the URL actually sent rather than the bare path.
        signed_url = url
        if len(query) > 0:
            import urllib.parse
            signed_url = "{}?{}".format(url, urllib.parse.urlencode(query))

        headers = self._signer.sign(method=method, url=signed_url,
                                    body=payload)

        timeout = timeout_seconds
        if timeout is None:
            timeout = self._timeout_seconds

        response = self._session.request(method, url, params=query,
                                         data=payload, headers=headers,
                                         timeout=timeout)

        status = getattr(response, "status_code", 0)
        raw_headers = getattr(response, "headers", None) or {}

        if status < 200 or status >= 300:
            text = getattr(response, "text", "")
            code, message = self._error_of(response=response)

            err_msg_lines = ["The OCI request failed."]
            err_msg_lines.append("METHOD: {}".format(method))
            err_msg_lines.append("URL: {}".format(url))
            err_msg_lines.append("STATUS: {}".format(status))
            err_msg_lines.append("CODE: {}".format(code))
            err_msg_lines.append("MESSAGE: {}".format(message))
            err_msg = os.linesep.join(err_msg_lines)

            if status == 429 or status >= 500:
                # Throttles and server faults are worth retrying; a 4xx is
                # not, and conflating them would retry a bad request forever.
                raise TransientServiceError(err_msg, status=status,
                                            code=code, message=message,
                                            body=text)

            raise ServiceError(err_msg, status=status, code=code,
                               message=message, body=text)

        data: Any = None
        text = getattr(response, "text", "")
        if text is not None and len(text.strip()) > 0:
            try:
                data = wrap(response.json())
            except Exception:
                data = text

        rtnval = Response(status=status, headers=dict(raw_headers),
                          data=data,
                          next_page=self._next_page(headers=raw_headers))
        return rtnval

    def _next_page(self, *, headers: Any) -> Optional[str]:
        """
            Read the next-page token out of the response headers.

            :param headers: The response headers.

            :returns: The token, or None on the last page.
        """
        getter = getattr(headers, "get", None)
        if getter is None:
            rtnval: Optional[str] = None
            return rtnval

        found = getter(NEXT_PAGE_HEADER, None)
        if found is None:
            for key in getattr(headers, "keys", lambda: [])():
                if str(key).lower() == NEXT_PAGE_HEADER:
                    found = headers[key]
                    break

        if found is None or len(str(found)) == 0:
            rtnval = None
            return rtnval

        rtnval = str(found)
        return rtnval

    def _error_of(self, *, response: Any) -> Any:
        """
            Pull the OCI error code and message out of a failed response.

            OCI answers with ``{"code": ..., "message": ...}``, and the code
            is what callers key on — ``BucketNotEmpty`` and ``NotAuthorized``
            need different handling.

            :param response: The failed response.

            :returns: A ``(code, message)`` pair.
        """
        fallback = getattr(response, "reason", "")

        try:
            decoded = response.json()
        except Exception:
            rtnval = ("", fallback)
            return rtnval

        if isinstance(decoded, dict) is False:
            rtnval = ("", fallback)
            return rtnval

        rtnval = (str(decoded.get("code", "")),
                  str(decoded.get("message", fallback)))
        return rtnval
