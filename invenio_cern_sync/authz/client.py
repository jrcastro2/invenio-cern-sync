# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 CERN.
#
# Invenio-CERN-sync is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""Invenio-CERN-sync CERN Authorization Service client."""

import concurrent.futures
import os
import time
from urllib.parse import urlencode

import requests
from flask import current_app

from ..errors import RequestError


def request_with_retries(
    url, method="GET", payload=None, headers=None, retries=3, delay=5
):
    for attempt in range(retries):
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, data=payload, headers=headers)
            else:
                raise ValueError("Unsupported HTTP method")
            response.raise_for_status()  # Raise an error for bad status codes (4xx/5xx)
            return response
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise RequestError(url, str(e))


class KeycloakService:
    """Connect to the CERN Keycloak service."""

    def __init__(self, base_url=None, client_id=None, client_secret=None):
        """Constructor."""
        self.base_url = base_url or current_app.config["CERN_SYNC_KEYCLOAK_BASE_URL"]
        self.client_id = client_id or current_app.config["CERN_SYNC_KEYCLOAK_CLIENT_ID"]
        self.client_secret = (
            client_secret or current_app.config["CERN_SYNC_KEYCLOAK_CLIENT_SECRET"]
        )

    def get_authz_token(self):
        """Get a token to authenticate to the Authz service."""
        token_url = f"{self.base_url}/auth/realms/cern/api-access/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": "authorization-service-api",
        }
        resp = request_with_retries(url=token_url, method="POST", payload=token_data)
        return resp.json()["access_token"]


IDENTITY_FIELDS = [
    "upn",  # username <johndoe>
    "displayName",  # John Doe
    "firstName",
    "lastName",
    "personId",  # unique - never changes, only in case of mistakes
    "uid",  # computing account user id
    "gid",  # computing account group id
    "cernDepartment",  # "IT"
    "cernGroup",  # "CA"
    "cernSection",  # "IR"
    "instituteName",  # "CERN"
    "instituteAbbreviation",  # "CERN"
    "preferredCernLanguage",  # "EN"
    "orcid",
    "primaryAccountEmail",
    # "postOfficeBox",  # currently missing, maybe added later
]


GROUPS_FIELDS = [
    "groupIdentifier",
    "displayName",
    "description",
]


class AuthZService:
    """Query CERN Authz service."""

    def __init__(self, keycloak_service, base_url=None, limit=1000, max_threads=3):
        """Constructor."""
        self.keycloak_service = keycloak_service
        self.base_url = base_url or current_app.config["CERN_SYNC_AUTHZ_BASE_URL"]
        self.limit = limit
        self.max_threads = max_threads

    def _fetch_all(self, url, headers):
        """Fetch results page by page in parallel using multiple threads."""
        offset = 0
        futures = []

        # perform the first request, also to get the total number of results
        _url = f"{url}&offset={offset}"
        resp = request_with_retries(url=_url, method="GET", headers=headers)
        total = resp.json()["pagination"]["total"]
        yield resp.json()["data"]
        offset += self.limit

        max_threads = os.cpu_count()
        if not max_threads or max_threads > self.max_threads:
            max_threads = self.max_threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            while offset < total:
                _url = f"{url}&offset={offset}"
                futures.append(
                    executor.submit(
                        request_with_retries(url=_url, method="GET", headers=headers)
                    )
                )
                offset += self.limit

            for future in concurrent.futures.as_completed(futures):
                resp = future.result()
                yield resp.json()["data"]

    def get_identities(self, fields=IDENTITY_FIELDS):
        """Get all identities."""
        query_params = [("field", value) for value in IDENTITY_FIELDS]
        query_params += [
            ("limit", self.limit),
            ("filter", "type:Person"),
            ("filter", "blocked:false"),
        ]
        query_string = urlencode(query_params)

        token = self.keycloak_service.get_authz_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "application/json",
        }
        url_without_offset = f"{self.base_url}/api/v1.0/Identity?{query_string}"
        return self._fetch_all(url_without_offset, headers)

    def get_groups(self, fields=GROUPS_FIELDS):
        """Get all groups."""

        query_params = [("field", value) for value in fields]
        query_params += [
            ("limit", self.limit),
        ]
        query_string = urlencode(query_params)

        token = self.keycloak_service.get_authz_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "application/json",
        }
        url_without_offset = f"{self.base_url}/api/v1.0/Groups?{query_string}"
        return self._fetch_all(url_without_offset, headers)