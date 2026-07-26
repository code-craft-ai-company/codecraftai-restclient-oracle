"""
    .. module:: ocimodels
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Request-body models and response objects for OCI.

    The ``oci`` SDK required typed model objects for request bodies —
    ``CreateVcnDetails(compartment_id=..., cidr_block=...)`` — and returned
    typed models on responses.  Consumers construct the former by keyword and
    read the latter by attribute, both in snake_case, while the wire format is
    camelCase JSON.

    Every one of those models is a plain data holder, so a single
    :class:`OciModel` serves them all; the named subclasses exist only so the
    call sites read the same as before and so a typo in a class name still
    fails loudly.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


def to_camel(name: str) -> str:
    """
        Convert a snake_case field name to the camelCase the wire uses.

        :param name: The snake_case name.

        :returns: The camelCase name.
    """
    parts = name.split("_")
    if len(parts) == 1:
        rtnval = parts[0]
        return rtnval

    rtnval = parts[0] + "".join(part.title() for part in parts[1:])
    return rtnval


def normalize_name(name: str) -> str:
    """
        Reduce a field name to a spelling-insensitive form.

        Matching on this rather than converting camelCase to snake_case keeps
        acronym-bearing names like ``rr_set`` / ``rrSet`` and ``vnic_id`` /
        ``vnicId`` working without special cases.

        :param name: The field name.

        :returns: The normalised name.
    """
    rtnval = name.replace("_", "").lower()
    return rtnval


def serialize(value: Any) -> Any:
    """
        Render a model, list or scalar for the wire.

        :param value: The value to render.

        :returns: JSON-ready data.
    """
    if isinstance(value, OciModel) is True:
        rtnval = value.to_body()
        return rtnval
    if isinstance(value, list) is True:
        rtnval = [serialize(item) for item in value]
        return rtnval
    if isinstance(value, dict) is True:
        rtnval = {key: serialize(item) for key, item in value.items()}
        return rtnval
    rtnval = value
    return rtnval


class OciModel:
    """
        A request-body model.

        Constructed with snake_case keywords and rendered to camelCase JSON.
        Fields left unset are omitted rather than sent as null, because OCI
        distinguishes "not supplied" from "explicitly null" on update calls.
    """

    def __init__(self, **fields: Any) -> None:
        """
            Construct a model from keyword fields.

            :param fields: The model's fields, in snake_case.
        """
        object.__setattr__(self, "_fields", dict(fields))
        return

    def __getattr__(self, name: str) -> Any:
        """
            Read a field.

            :param name: The field name.

            :returns: The field value, or None when unset.
        """
        if name.startswith("_") is True:
            raise AttributeError(name)

        fields = object.__getattribute__(self, "_fields")
        rtnval = fields.get(name, None)
        return rtnval

    def __setattr__(self, name: str, value: Any) -> None:
        """
            Set a field.

            :param name: The field name.
            :param value: The value.
        """
        if name.startswith("_") is True:
            object.__setattr__(self, name, value)
            return
        object.__getattribute__(self, "_fields")[name] = value
        return

    def __repr__(self) -> str:
        """
            Return a debug representation.

            :returns: The representation.
        """
        fields = object.__getattribute__(self, "_fields")
        rtnval = "{}({})".format(
            type(self).__name__,
            ", ".join("{}={!r}".format(k, v) for k, v in fields.items()))
        return rtnval

    def to_body(self) -> Dict[str, Any]:
        """
            Render this model as a request body.

            :returns: The camelCase JSON body, with unset fields omitted.
        """
        fields = object.__getattribute__(self, "_fields")

        rtnval: Dict[str, Any] = {}
        for name, value in fields.items():
            if value is None:
                continue
            rtnval[to_camel(name)] = serialize(value)
        return rtnval


def _model(name: str) -> type:
    """
        Build a named model class.

        :param name: The class name.

        :returns: The class.
    """
    rtnval = type(name, (OciModel,), {
        "__doc__": "The OCI ``{}`` request model.".format(name),
    })
    return rtnval


# The models the provisioning venue constructs.  Named subclasses rather than
# aliases of OciModel so a mistyped class name fails at import.
MODEL_NAMES = (
    "AttachParavirtualizedVolumeDetails",
    "ClusterNetworkPlacementConfigurationDetails",
    "ComputeInstanceDetails",
    "CreateBucketDetails",
    "CreateClusterNetworkDetails",
    "CreateClusterNetworkInstancePoolDetails",
    "CreateInstanceConfigurationDetails",
    "CreateInternetGatewayDetails",
    "CreateRouteTableDetails",
    "CreateSecurityListDetails",
    "CreateSubnetDetails",
    "CreateVcnDetails",
    "CreateVnicDetails",
    "CreateVolumeDetails",
    "EgressSecurityRule",
    "IngressSecurityRule",
    "InstanceConfigurationCreateVnicDetails",
    "InstanceConfigurationInstanceSourceViaImageDetails",
    "InstanceConfigurationLaunchInstanceDetails",
    "InstanceSourceViaImageDetails",
    "LaunchInstanceDetails",
    "PortRange",
    "PreemptibleInstanceConfigDetails",
    "RecordDetails",
    "RouteRule",
    "TcpOptions",
    "TerminatePreemptionAction",
    "UdpOptions",
    "UpdateRRSetDetails",
)

for _name in MODEL_NAMES:
    globals()[_name] = _model(_name)


class OciObject(dict):
    """
        A response resource, attribute addressable in snake_case.

        The wire is camelCase; consumers read ``instance.display_name`` and
        ``vcn.lifecycle_state``.  Absent fields read as ``None``, matching the
        SDK's models — OCI's optional fields really are absent rather than
        zero-valued, unlike the protobuf-based Google clients.
    """

    def __getattr__(self, name: str) -> Any:
        """
            Resolve a field by attribute access.

            :param name: The field name, in either spelling.

            :returns: The wrapped value, or None when absent.
        """
        if name.startswith("_") is True:
            raise AttributeError(name)

        if dict.__contains__(self, name) is True:
            rtnval = wrap(dict.__getitem__(self, name))
            return rtnval

        wanted = normalize_name(name)
        for key in dict.keys(self):
            if normalize_name(key) == wanted:
                rtnval = wrap(dict.__getitem__(self, key))
                return rtnval

        rtnval = None
        return rtnval

    def __setattr__(self, name: str, value: Any) -> None:
        """
            Set a field.

            :param name: The field name.
            :param value: The value.
        """
        if name.startswith("_") is True:
            object.__setattr__(self, name, value)
            return
        self[name] = value
        return

    def as_dict(self) -> Dict[str, Any]:
        """
            Return the underlying plain dictionary.

            :returns: The wire-shaped dictionary.
        """
        rtnval = {key: dict.__getitem__(self, key)
                  for key in dict.keys(self)}
        return rtnval


def wrap(value: Any) -> Any:
    """
        Wrap a decoded JSON value so nested objects stay addressable.

        :param value: The decoded value.

        :returns: An :class:`OciObject` for dicts, a list of wrapped values
            for lists, or the value unchanged.
    """
    if isinstance(value, OciObject) is True:
        rtnval = value
        return rtnval
    if isinstance(value, dict) is True:
        rtnval = OciObject(value)
        return rtnval
    if isinstance(value, list) is True:
        rtnval = [wrap(item) for item in value]
        return rtnval
    rtnval = value
    return rtnval


class Response:
    """
        An OCI SDK response.

        The attribute set matches ``oci.response.Response`` exactly, because
        the paginator reads several of them — ``next_page`` to decide whether
        to keep going, ``status`` and ``request`` to build the aggregated
        response it returns.

        :ivar data: The decoded payload.
        :ivar next_page: The opaque page token, or None on the last page.
    """

    def __init__(self, *, status: int = 200,
                 headers: Optional[Dict[str, Any]] = None,
                 data: Any = None, request: Any = None,
                 next_page: Any = None) -> None:
        """
            Construct a Response.

            :param status: The HTTP status code.
            :param headers: The response headers.
            :param data: The decoded payload.
            :param request: The originating request.
            :param next_page: The next-page token, or None when complete.
        """
        self.status = status
        self.headers: Dict[str, Any] = headers or {}
        self.data = data
        self.request = request
        self.next_page = next_page
        self.request_id = str(self.headers.get("opc-request-id", ""))
        return

    @property
    def has_next_page(self) -> bool:
        """
            Report whether another page follows.

            :returns: True when a next-page token is present.
        """
        rtnval = self.next_page is not None
        return rtnval
