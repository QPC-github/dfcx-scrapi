"""Base for other SCRAPI classes."""

# Copyright 2022 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import json
import re

from typing import Dict, Tuple
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.protobuf import json_format  # type: ignore

from proto.marshal.collections import repeated
from proto.marshal.collections import maps
class ScrapiBase:
    """Core Class for managing Auth and other shared functions."""

    global_scopes = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/dialogflow",
    ]

    def __init__(
        self,
        creds_path: str = None,
        creds_dict: Dict[str,str] = None,
        creds: service_account.Credentials =None,
        scope=False,
        agent_id=None,
    ):

        self.scopes = ScrapiBase.global_scopes
        if scope:
            self.scopes += scope

        if creds:
            self.creds = creds
            self.creds.refresh(Request())
            self.token = self.creds.token
        elif creds_path:
            self.creds = service_account.Credentials.from_service_account_file(
                creds_path, scopes=self.scopes
            )
            self.creds.refresh(Request())
            self.token = self.creds.token
        elif creds_dict:
            self.creds = service_account.Credentials.from_service_account_info(
                creds_dict, scopes=self.scopes
            )
            self.creds.refresh(Request())
            self.token = self.creds.token
        else:
            self.creds = None
            self.token = None

        if agent_id:
            self.agent_id = agent_id

    @staticmethod
    def _set_region(item_id):
        """different regions have different API endpoints

        Args:
            item_id: agent/flow/page - any type of long path id like
                `projects/<GCP PROJECT ID>/locations/<LOCATION ID>

        Returns:
            client_options: use when instantiating other library client objects
        """
        try:
            location = item_id.split("/")[3]
        except IndexError as err:
            logging.error("IndexError - path too short? %s", item_id)
            raise err

        if location != "global":
            api_endpoint = f"{location}-dialogflow.googleapis.com:443"
            client_options = {"api_endpoint": api_endpoint}
            return client_options

        else:
            return None  # explicit None return when not required

    @staticmethod
    def pbuf_to_dict(pbuf):
        """extractor of json from a protobuf"""
        blobstr = json_format.MessageToJson(
            pbuf
        )  # i think this returns JSON as a string
        blob = json.loads(blobstr)
        return blob

    @staticmethod
    def cx_object_to_json(cx_object):
        """response objects have a magical _pb field attached"""
        return ScrapiBase.pbuf_to_dict(cx_object._pb)  # pylint: disable=W0212

    @staticmethod
    def cx_object_to_dict(cx_object):
        """response objects have a magical _pb field attached"""
        return ScrapiBase.pbuf_to_dict(cx_object._pb)  # pylint: disable=W0212

    @staticmethod
    def extract_payload(msg):
        """convert to json so we can get at the object"""
        blob = ScrapiBase.cx_object_to_dict(msg)
        return blob.get("payload")  # deref for nesting

    @staticmethod
    def _parse_resource_path(resource_type, resource_id) -> Dict[str,str]:
        """Validates the provided Resource ID against known patterns.

        Args:
          resource_type, Must be one of the following resource types:
            `agent`, `entity_type`, `environmnet`, `flow`, `intent`, `page`,
            `project`, `security_setting`, `session`, `session_entity_type`,
            `test_case`, `transition_route_group`, `version`, `webhook`
          resource_id, The CX resource ID to check against the provided
            resource_type
        """

        pattern_dict = {
            'agent': {
                'matcher': r"^projects\/(?P<project>.+?)\/locations\/(?P<location>.+?)\/agents\/(?P<agent>[\-0-9a-f]+)$",
                'pattern': '`projects/<Project ID>/locations/<Location ID>/agents/<Agent ID>`'
            },
            "environment": {
                'matcher': r"^projects/(?P<project>.+?)/locations/(?P<location>.+?)/agents/(?P<agent>.+?)/environments/(?P<environment>[\-0-9a-f]+)$",
                'pattern': '`projects/<Project ID>/locations/<Location ID>/agents/<Agent ID>/environments/<Environment ID>`'
            },
            "session": {
                "matcher": r"^projects/(?P<project>.+?)/locations/(?P<location>.+?)/agents/(?P<agent>.+?)/sessions/(?P<session>.+?)$",
                "pattern": "`projects/<Project ID>/locations/<Location ID>/agents/<Agent ID>/sessions/<Session ID>`"
            }
        }

        match_res = re.match(
            pattern_dict[resource_type]['matcher'], resource_id)
        dict_res = match_res.groupdict() if match_res else {}
        valid = False

        if dict_res:
            valid = True

        if not valid:
            raise ValueError(
                f"{resource_type.capitalize()} ID must be provided in the "\
                    f"following format: "\
                        f"{pattern_dict[resource_type]['pattern']}"
                )

        return dict_res

    def recurse_proto_repeated_composite(self, repeated_object):
        repeated_list = []
        for item in repeated_object:
            if isinstance(item, repeated.RepeatedComposite):
                item = self.recurse_proto_repeated_composite(item)
                repeated_list.append(item)
            elif isinstance(item, maps.MapComposite):
                item = self.recurse_proto_marshal_to_dict(item)
                repeated_list.append(item)
            else:
                repeated_list.append(item)

        return repeated_list

    def recurse_proto_marshal_to_dict(self, marshal_object):
        new_dict = {}
        for k,v in marshal_object.items():
            if isinstance(v, maps.MapComposite):
                v = self.recurse_proto_marshal_to_dict(v)
            elif isinstance(v, repeated.RepeatedComposite):
                v = self.recurse_proto_repeated_composite(v)
            new_dict[k] = v

        return new_dict
