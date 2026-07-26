"""
    .. module:: ocipagination
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The aggregating paginator, replacing
               ``oci.pagination.list_call_get_all_results``.

    The venue calls this helper directly rather than going through a client
    method, so replacing the clients alone would not have been enough — this
    is part of the SDK surface consumers depend on.

    It calls a list operation repeatedly, following ``next_page`` until the
    listing is exhausted, and returns ONE response whose ``data`` is every
    page concatenated.  That aggregation is the point: callers treat the
    result as a complete listing, and a truncated one would under-report owned
    resources, which on a teardown path means leaked infrastructure.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Callable, List

from ccai.restclient.oracle.ocimodels import Response


def list_call_get_all_results(list_func: Callable[..., Any],
                              *args: Any, **kwargs: Any) -> Response:
    """
        Call a list operation until every page has been collected.

        :param list_func: The list operation to call.
        :param args: Positional arguments forwarded to it.
        :param kwargs: Keyword arguments forwarded to it.

        :returns: A :class:`Response` whose ``data`` is every page's entries
            concatenated.

        :raises: :class:`TypeError` when the operation answers with something
            other than a list, which would otherwise silently produce a
            malformed aggregate.
    """
    collected: List[Any] = []

    call_kwargs = dict(kwargs)
    page: Any = None
    last: Any = None

    while True:
        if page is not None:
            call_kwargs["page"] = page

        result = list_func(*args, **call_kwargs)
        last = result

        data = getattr(result, "data", None)
        if data is not None:
            if isinstance(data, list) is True:
                collected.extend(data)
            else:
                err_msg = (
                    "list_call_get_all_results expects a list operation; "
                    "got {} from {!r}.".format(type(data).__name__,
                                               list_func))
                raise TypeError(err_msg)

        page = getattr(result, "next_page", None)
        if page is None:
            break

    rtnval = Response(status=getattr(last, "status", 200),
                      headers=getattr(last, "headers", None) or {},
                      data=collected,
                      request=getattr(last, "request", None),
                      next_page=None)
    return rtnval


def list_call_get_all_results_generator(list_func: Callable[..., Any],
                                        *args: Any,
                                        **kwargs: Any) -> Any:
    """
        Yield every entry across all pages.

        :param list_func: The list operation to call.
        :param args: Positional arguments forwarded to it.
        :param kwargs: Keyword arguments forwarded to it.

        :returns: A generator over the entries.
    """
    response = list_call_get_all_results(list_func, *args, **kwargs)
    for entry in response.data:
        yield entry
