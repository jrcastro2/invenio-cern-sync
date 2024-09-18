# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 CERN.
#
# Invenio-CERN-sync is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""Invenio-CERN-sync LDAP user profile mapper."""

from ..utils import first_or_default, first_or_raise


def userprofile_mapper(ldap_user):
    """Map the LDAP fields to the Invenio user profile schema.

    :param ldap_user: the ldap dict
    :param profile_schema: the Invenio user profile schema to map to
    :return: a serialized dict, containing all the keys that will appear in the
        User.profile JSON column. Any unwanted key should be removed.
    """
    return dict(
        cern_department=first_or_default(ldap_user, "division"),
        cern_group=first_or_default(ldap_user, "cernGroup"),
        cern_section=first_or_default(ldap_user, "cernSection"),
        family_name=first_or_default(ldap_user, "sn"),
        full_name=first_or_default(ldap_user, "displayName"),
        given_name=first_or_default(ldap_user, "givenName"),
        institute_abbreviation=first_or_default(ldap_user, "cernInstituteAbbreviation"),
        institute=first_or_default(ldap_user, "cernInstituteName"),
        mailbox=first_or_default(ldap_user, "postOfficeBox"),
        person_id=first_or_default(ldap_user, "employeeID"),
    )


def remoteaccount_extradata_mapper(ldap_user):
    """Map the LDAP fields to the Invenio remote account extra data.

    :param ldap_user: the ldap dict
    :return: a serialized dict, containing all the keys that will appear in the
        RemoteAccount.extra_data column. Any unwanted key should be removed.
    """
    return dict(
        person_id=first_or_raise(ldap_user, "employeeID"),
        uidNumber=first_or_raise(ldap_user, "uidNumber"),
        username=first_or_raise(ldap_user, "cn").lower(),
    )