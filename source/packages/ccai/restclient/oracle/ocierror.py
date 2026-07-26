"""
    .. module:: ocierror
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Errors raised for non-success OCI responses.

    :class:`ServiceError` keeps the name ``oci.exceptions`` used, and the same
    ``status`` / ``code`` / ``message`` attributes, because consumer code
    catches it and branches on those — ``BucketNotEmpty`` and ``NotAuthorized``
    need different handling, and a teardown that treated them alike would
    either leak storage or mask a permissions problem.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Optional


class ServiceError(Exception):
    """
        Raised when an OCI service returns a non-success status.

        :ivar status: The HTTP status code.
        :ivar code: The OCI error code, e.g. ``BucketNotEmpty``.
        :ivar message: The OCI error message.
        :ivar body: The raw response body text.
    """

    def __init__(self, message_text: str, *, status: int = 0,
                 code: str = "", message: str = "",
                 body: Optional[str] = None) -> None:
        """
            Construct a ServiceError.

            :param message_text: The human-readable error message.
            :param status: The HTTP status code.
            :param code: The OCI error code.
            :param message: The OCI error message.
            :param body: The raw response body.
        """
        super().__init__(message_text)
        self.status: int = status
        self.code: str = code
        self.message: str = message
        self.body: Optional[str] = body
        return


class TransientServiceError(ServiceError):
    """
        Raised for a throttle or a server fault.

        Separate from :class:`ServiceError` because these are worth retrying
        and a 4xx is not; conflating them would retry a bad request forever.
    """
