# -*- coding: utf-8 -*-
#
# RERO MEF
# Copyright (C) 2020 RERO
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""API for manipulating IDREF agent."""

from invenio_search.api import RecordsSearch

from .fetchers import idref_id_fetcher
from .minters import idref_id_minter
from .models import AgentIdrefMetadata
from .providers import AgentIdrefProvider
from ..api import AgentIndexer, AgentRecord


class AgentIdrefSearch(RecordsSearch):
    """RecordsSearch."""

    class Meta:
        """Search only on index."""

        index = 'agents_idref'
        doc_types = None
        fields = ('*', )
        facets = {}

        default_filter = None


class AgentIdrefRecord(AgentRecord):
    """Idref agent class."""

    minter = idref_id_minter
    fetcher = idref_id_fetcher
    provider = AgentIdrefProvider
    name = 'idref'
    viaf_source_code = 'SUDOC'
    viaf_pid_name = 'idref_pid'
    model_cls = AgentIdrefMetadata

    @classmethod
    def get_online_record(cls, id, verbose=False):
        """Get online record."""
        from .tasks import idref_get_record
        return idref_get_record(id=id, verbose=verbose)


class AgentIdrefIndexer(AgentIndexer):
    """IdrefIndexer."""

    record_cls = AgentIdrefRecord

    def bulk_index(self, record_id_iterator):
        """Bulk index records.

        :param record_id_iterator: Iterator yielding record UUIDs.
        """
        self._bulk_op(record_id_iterator, op_type='index', doc_type='aidref')
