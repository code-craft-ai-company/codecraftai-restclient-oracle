"""
    .. module:: ociclients
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The OCI service clients.

    Method and keyword names match the ``oci`` SDK's exactly — including the
    inconsistencies, which are the SDK's own: the details keyword is
    ``create_vcn_details`` for one call and ``create_instance_configuration``
    for another, and identifiers are abbreviated for some resources
    (``ig_id``, ``rt_id``) but not others (``security_list_id``).  Those are
    reproduced rather than tidied, because consumer code already passes them.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, Optional

from ccai.restclient.oracle.ocimodels import Response, serialize


CORE_API_VERSION = "20160918"

DNS_API_VERSION = "20180115"

FILE_STORAGE_API_VERSION = "20171215"


def _endpoint(*, service: str, region: str, domain: str) -> str:
    """
        Build a regional service endpoint.

        :param service: The service hostname prefix.
        :param region: The region identifier.
        :param domain: The realm domain.

        :returns: The endpoint URL.
    """
    rtnval = "https://{}.{}.{}".format(service, region, domain)
    return rtnval


class _ServiceClient:
    """
        Shared behaviour for an OCI service client.

        :cvar SERVICE: The service hostname prefix.
        :cvar API_VERSION: The path version segment.
    """

    SERVICE: str = ""
    API_VERSION: str = ""

    def __init__(self, config: Optional[Dict[str, Any]] = None, *,
                 transport: Any = None, region: str = "",
                 domain: str = "oraclecloud.com",
                 endpoint: Optional[str] = None) -> None:
        """
            Construct a service client.

            Accepts the config dict positionally, matching how the SDK
            clients were built and how the venue's session factory calls
            them.

            :param config: The OCI config dict, carrying at least ``region``.
            :param transport: The shared :class:`OciTransport`.
            :param region: The region, when not taken from the config.
            :param domain: The realm domain.
            :param endpoint: An explicit endpoint override.
        """
        settings = config or {}

        self._transport = transport
        self._region = region or str(settings.get("region", ""))
        self._domain = domain

        if endpoint is not None:
            self._endpoint = endpoint.rstrip("/")
        else:
            self._endpoint = _endpoint(service=self.SERVICE,
                                       region=self._region,
                                       domain=self._domain)
        return

    @property
    def base_url(self) -> str:
        """
            Return the endpoint this client addresses.

            :returns: The endpoint URL.
        """
        rtnval = self._endpoint
        return rtnval

    def _url(self, path: str) -> str:
        """
            Build a versioned absolute URL.

            :param path: The path below the version segment.

            :returns: The absolute URL.
        """
        rtnval = "{}/{}{}".format(self._endpoint, self.API_VERSION, path)
        return rtnval

    def _call(self, *, method: str, path: str,
              params: Optional[Dict[str, Any]] = None,
              details: Any = None) -> Response:
        """
            Perform one call against this service.

            :param method: The HTTP method.
            :param path: The path below the version segment.
            :param params: Optional query parameters.
            :param details: Optional request model, serialised to the wire.

            :returns: The :class:`Response`.
        """
        body = None
        if details is not None:
            body = serialize(details)

        rtnval = self._transport.request(method=method, url=self._url(path),
                                         params=params, body=body)
        return rtnval


class VirtualNetworkClient(_ServiceClient):
    """
        The Core Services networking client.
    """

    SERVICE = "iaas"
    API_VERSION = CORE_API_VERSION

    def create_vcn(self, *, create_vcn_details: Any) -> Response:
        """Create a VCN."""
        return self._call(method="POST", path="/vcns",
                          details=create_vcn_details)

    def delete_vcn(self, *, vcn_id: str) -> Response:
        """Delete a VCN."""
        return self._call(method="DELETE",
                          path="/vcns/{}".format(vcn_id))

    def list_vcns(self, *, compartment_id: str,
                  **filters: Any) -> Response:
        """List VCNs in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/vcns", params=params)

    def create_subnet(self, *, create_subnet_details: Any) -> Response:
        """Create a subnet."""
        return self._call(method="POST", path="/subnets",
                          details=create_subnet_details)

    def delete_subnet(self, *, subnet_id: str) -> Response:
        """Delete a subnet."""
        return self._call(method="DELETE",
                          path="/subnets/{}".format(subnet_id))

    def list_subnets(self, *, compartment_id: str,
                     **filters: Any) -> Response:
        """List subnets in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/subnets", params=params)

    def create_internet_gateway(self, *,
                                create_internet_gateway_details: Any
                                ) -> Response:
        """Create an internet gateway."""
        return self._call(method="POST", path="/internetGateways",
                          details=create_internet_gateway_details)

    def delete_internet_gateway(self, *, ig_id: str) -> Response:
        """Delete an internet gateway.  The SDK abbreviates the keyword."""
        return self._call(method="DELETE",
                          path="/internetGateways/{}".format(ig_id))

    def list_internet_gateways(self, *, compartment_id: str,
                               **filters: Any) -> Response:
        """List internet gateways in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/internetGateways",
                          params=params)

    def create_route_table(self, *,
                           create_route_table_details: Any) -> Response:
        """Create a route table."""
        return self._call(method="POST", path="/routeTables",
                          details=create_route_table_details)

    def delete_route_table(self, *, rt_id: str) -> Response:
        """Delete a route table.  The SDK abbreviates the keyword."""
        return self._call(method="DELETE",
                          path="/routeTables/{}".format(rt_id))

    def list_route_tables(self, *, compartment_id: str,
                          **filters: Any) -> Response:
        """List route tables in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/routeTables", params=params)

    def create_security_list(self, *,
                             create_security_list_details: Any) -> Response:
        """Create a security list."""
        return self._call(method="POST", path="/securityLists",
                          details=create_security_list_details)

    def delete_security_list(self, *, security_list_id: str) -> Response:
        """Delete a security list."""
        return self._call(
            method="DELETE",
            path="/securityLists/{}".format(security_list_id))

    def list_security_lists(self, *, compartment_id: str,
                            **filters: Any) -> Response:
        """List security lists in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/securityLists",
                          params=params)


class ComputeClient(_ServiceClient):
    """
        The Core Services compute client.
    """

    SERVICE = "iaas"
    API_VERSION = CORE_API_VERSION

    def launch_instance(self, *, launch_instance_details: Any) -> Response:
        """Launch an instance."""
        return self._call(method="POST", path="/instances",
                          details=launch_instance_details)

    def terminate_instance(self, *, instance_id: str,
                           **options: Any) -> Response:
        """Terminate an instance."""
        return self._call(method="DELETE",
                          path="/instances/{}".format(instance_id),
                          params=_camel_params(options))

    def list_instances(self, *, compartment_id: str,
                       **filters: Any) -> Response:
        """List instances in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/instances", params=params)

    def list_images(self, *, compartment_id: str,
                    **filters: Any) -> Response:
        """List images in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/images", params=params)

    def attach_volume(self, *, attach_volume_details: Any) -> Response:
        """Attach a volume to an instance."""
        return self._call(method="POST", path="/volumeAttachments",
                          details=attach_volume_details)


class ComputeManagementClient(_ServiceClient):
    """
        The Core Services compute-management client.
    """

    SERVICE = "iaas"
    API_VERSION = CORE_API_VERSION

    def create_instance_configuration(self, *,
                                      create_instance_configuration: Any
                                      ) -> Response:
        """
            Create an instance configuration.

            The keyword lacks the ``_details`` suffix the sibling calls use;
            that is the SDK's own inconsistency, reproduced here because
            consumer code passes it.
        """
        return self._call(method="POST", path="/instanceConfigurations",
                          details=create_instance_configuration)

    def create_cluster_network(self, *,
                               create_cluster_network_details: Any
                               ) -> Response:
        """Create a cluster network."""
        return self._call(method="POST", path="/clusterNetworks",
                          details=create_cluster_network_details)

    def terminate_cluster_network(self, *,
                                  cluster_network_id: str) -> Response:
        """Terminate a cluster network."""
        return self._call(
            method="DELETE",
            path="/clusterNetworks/{}".format(cluster_network_id))

    def list_cluster_networks(self, *, compartment_id: str,
                              **filters: Any) -> Response:
        """List cluster networks in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/clusterNetworks",
                          params=params)


class BlockstorageClient(_ServiceClient):
    """
        The Core Services block-storage client.
    """

    SERVICE = "iaas"
    API_VERSION = CORE_API_VERSION

    def create_volume(self, *, create_volume_details: Any) -> Response:
        """Create a block volume."""
        return self._call(method="POST", path="/volumes",
                          details=create_volume_details)

    def delete_volume(self, *, volume_id: str) -> Response:
        """Delete a block volume."""
        return self._call(method="DELETE",
                          path="/volumes/{}".format(volume_id))

    def list_volumes(self, *, compartment_id: str,
                     **filters: Any) -> Response:
        """List block volumes in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/volumes", params=params)


class ObjectStorageClient(_ServiceClient):
    """
        The Object Storage client.

        Object Storage is not versioned in its path, unlike the other
        services, so the version segment is empty.
    """

    SERVICE = "objectstorage"
    API_VERSION = ""

    def _url(self, path: str) -> str:
        """
            Build an absolute URL without a version segment.

            :param path: The path.

            :returns: The absolute URL.
        """
        rtnval = "{}{}".format(self._endpoint, path)
        return rtnval

    def get_namespace(self, **options: Any) -> Response:
        """Return the tenancy's Object Storage namespace."""
        return self._call(method="GET", path="/n/",
                          params=_camel_params(options))

    def create_bucket(self, *, namespace_name: str,
                      create_bucket_details: Any) -> Response:
        """Create a bucket."""
        return self._call(method="POST",
                          path="/n/{}/b/".format(namespace_name),
                          details=create_bucket_details)

    def get_bucket(self, *, namespace_name: str,
                   bucket_name: str) -> Response:
        """Fetch a bucket."""
        return self._call(
            method="GET",
            path="/n/{}/b/{}/".format(namespace_name, bucket_name))

    def delete_bucket(self, *, namespace_name: str,
                      bucket_name: str) -> Response:
        """Delete a bucket."""
        return self._call(
            method="DELETE",
            path="/n/{}/b/{}/".format(namespace_name, bucket_name))

    def list_buckets(self, *, namespace_name: str, compartment_id: str,
                     **filters: Any) -> Response:
        """List buckets in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET",
                          path="/n/{}/b/".format(namespace_name),
                          params=params)


class DnsClient(_ServiceClient):
    """
        The DNS client.
    """

    SERVICE = "dns"
    API_VERSION = DNS_API_VERSION

    def update_rr_set(self, *, zone_name_or_id: str, domain: str,
                      rtype: str, update_rr_set_details: Any,
                      **options: Any) -> Response:
        """Replace a record set."""
        return self._call(
            method="PUT",
            path="/zones/{}/records/{}/{}".format(zone_name_or_id, domain,
                                                  rtype),
            params=_camel_params(options),
            details=update_rr_set_details)

    def delete_rr_set(self, *, zone_name_or_id: str, domain: str,
                      rtype: str, **options: Any) -> Response:
        """Delete a record set."""
        return self._call(
            method="DELETE",
            path="/zones/{}/records/{}/{}".format(zone_name_or_id, domain,
                                                  rtype),
            params=_camel_params(options))

    def list_zones(self, *, compartment_id: str,
                   **filters: Any) -> Response:
        """List DNS zones in a compartment."""
        params = {"compartmentId": compartment_id}
        params.update(_camel_params(filters))
        return self._call(method="GET", path="/zones", params=params)


class FileStorageClient(_ServiceClient):
    """
        The File Storage client.
    """

    SERVICE = "filestorage"
    API_VERSION = FILE_STORAGE_API_VERSION

    def get_file_system(self, *, file_system_id: str) -> Response:
        """Fetch a file system."""
        return self._call(
            method="GET", path="/fileSystems/{}".format(file_system_id))


def _camel_params(values: Dict[str, Any]) -> Dict[str, Any]:
    """
        Render filter keywords as the camelCase query parameters OCI expects.

        :param values: The snake_case keywords.

        :returns: The camelCase parameters.
    """
    from ccai.restclient.oracle.ocimodels import to_camel

    rtnval = {to_camel(name): value for name, value in values.items()}
    return rtnval


def build_clients(*, transport: Any, region: str,
                  domain: str = "oraclecloud.com") -> Dict[str, Any]:
    """
        Build every service client over one transport.

        :param transport: The shared :class:`OciTransport`.
        :param region: The region identifier.
        :param domain: The realm domain.

        :returns: A dict keyed the way the venue's session factory keyed it.
    """
    kwargs = {"transport": transport, "region": region, "domain": domain}

    rtnval = {
        "virtual_network": VirtualNetworkClient(**kwargs),
        "compute": ComputeClient(**kwargs),
        "compute_management": ComputeManagementClient(**kwargs),
        "blockstorage": BlockstorageClient(**kwargs),
        "object_storage": ObjectStorageClient(**kwargs),
        "dns": DnsClient(**kwargs),
        "file_storage": FileStorageClient(**kwargs),
    }
    return rtnval
