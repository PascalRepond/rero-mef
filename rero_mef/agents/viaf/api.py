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

"""API for manipulating VIAF record."""

from copy import deepcopy

import click
import requests
from elasticsearch_dsl.query import Q
from flask import current_app
from invenio_search.api import RecordsSearch

from .fetchers import viaf_id_fetcher
from .minters import viaf_id_minter
from .models import ViafMetadata
from .providers import ViafProvider
from .. import AgentGndRecord, AgentIdrefRecord, AgentMefRecord, \
    AgentReroRecord
from ..api import Action, ReroIndexer, ReroMefRecord
from ..mef.api import AgentMefRecord
from ..utils import get_entity_class
from ...filter import exists_filter
from ...utils import add_md5, get_entity_class, progressbar, \
    requests_retry_session


class AgentViafSearch(RecordsSearch):
    """RecordsSearch."""

    class Meta:
        """Search only on index."""

        index = 'viaf'
        doc_types = None
        fields = ('*', )
        facets = {}

        default_filter = None


class AgentViafRecord(ReroMefRecord):
    """VIAF agent class."""

    minter = viaf_id_minter
    fetcher = viaf_id_fetcher
    provider = ViafProvider
    name = 'viaf'
    model_cls = ViafMetadata
    search = AgentViafSearch
    # https://viaf.org/
    sources = {
        'SUDOC': {
            'name': 'idref',
            'info': 'Sudoc [ABES], France',
            'record_class': AgentIdrefRecord
        },
        'DNB': {
            'name': 'gnd',
            'info': 'German National Library',
            'record_class': AgentGndRecord
        },
        'RERO': {
            'name': 'rero',
            'info': 'RERO - Library Network of Western Switzerland',
            'record_class': AgentReroRecord
        },
        'SZ': {
            'name': 'sz',
            'info': 'Swiss National Library'
        },
        'BNE': {
            'name': 'bne',
            'info': 'National Library of Spain'
        },
        'BNF': {
            'name': 'bnf',
            'info': 'National Library of France'
        },
        'ICCU': {
            'name': 'iccu',
            'info': 'Central Institute for the Union Catalogue of the '
                    'Italian libraries'
        },
        'ISNI': {
            'name': 'isni',
            'info': 'ISNI'
        },
        'WKP': {
            'name': 'wiki',
            'info': 'Wikidata'
        },
        # 'LC': 'loc',  # Library of Congress
        # 'SELIBR': 'selibr',  # National Library of Sweden
        # 'NLA': 'nla',  # National Library of Australia
        # 'PTBNP': 'ptbnp',  # National Library of Portugal
        # 'BLBNB': 'BLBNB',  # National Library of Brazil
        # 'NKC': 'nkc',  # National Library of the Czech Republic
        # 'J9U': 'j9u',  # National Library of Israel
        # 'EGAXA': 'egaxa',  # Library of Alexandria, Egypt
        # 'BAV': 'bav',  # Vatican Library
        # 'CAOONL': 'caoonl',  # Library and Archives Canada/PFAN
        # 'JPG': 'jpg',  # Union List of Artist Names [Getty Research Institute]  # noqa
        # 'NUKAT': 'nukat',  # NUKAT Center of Warsaw University Library
        # 'NSZL': 'NSZL',  # National Széchényi Library, Hungary
        # 'VLACC': 'vlacc',  # Flemish Public Libraries National Library of Russia  # noqa
        # 'NTA': 'nta',  # National Library of Netherlands
        # 'BIBSYS': 'bibsys',  # BIBSYS
        # 'GRATEVE': 'grateve',  # National Library of Greece
        # 'ARBABN': 'arbabn',  # National Library of Argentina
        # 'W2Z': 'w2z',  # National Library of Norway
        # 'DBC': 'dbc',  # DBC (Danish Bibliographic Center)
        # 'NDL': 'ndl',  # National Diet Library, Japan
        # 'NII': 'nii',  # NII (Japan)
        # 'NLB': 'nlb',  # National Library Board, Singapore
        # 'LNB': 'lnb',  # National Library of Latvia
        # 'PLWABN': 'plwabn',  # National Library of Poland
        # 'BNC': 'BNC',  # National Library of Catalonia
        # 'LNL': 'lnl',  # Lebanese National Library
        # 'PERSEUS': 'perseus',  # Perseus Digital Library
        # 'SRP': 'srp',  # Syriac Reference Portal
        # 'N6I': 'n6i',  # National Library of Ireland
        # 'NSK': 'nsk',  # National and University Library in Zagreb
        # 'CYT': 'cyt',  # National Central Library, Taiwan
        # 'B2Q': 'b2q',  # National Library and Archives of Québec
        # 'KRLNK': 'krlnk',  # National Library of Korea
        # 'BNL': 'BNL',  # National Library of Luxembourg
        # 'BNCHL': 'bnchl',  # National Library of Chile
        # 'MRBNR': 'mrbnr',  # National Library of Morocco
        # 'XA': 'xa',  # xA Extended Authorities
        # 'XR': 'xr',  # xR Extended Relationships
        # 'FAST': 'fast',  # FAST Subjects
        # 'ERRR': 'errr',  # National Library of Estonia
        # 'UIY': 'uiy',  # National and University Library of Iceland (NULI)
        # 'NYNYRILM': 'nynyrilm',  # Repertoire International de Litterature Musicale, Inc. (RILM)  # noqa
        # 'DE663': 'de663',  # International Inventory of Musical Sources (RISM)  # noqa
        # 'SIMACOB': 'simacob',  # NUK/COBISS.SI, Slovenia
        # 'LIH': 'lih',  # National Library of Lithuania
        # 'SKMASNL': 'skmasnl',  # Slovak National Library
        # 'UAE': 'uae',  # United Arab Emirates University
    }

    def __init__(self, data, model=None, **kwargs):
        """Initialize instance with dictionary data and SQLAlchemy model.

        :param data: Dict with record metadata.
        :param model: :class:`~invenio_records.models.RecordMetadata` instance.
        """
        super().__init__(data or {}, model=model, **kwargs)
        self.sources_used = {}
        for data in self.sources.values():
            if record_class := data.get('record_class'):
                self.sources_used[data['name']] = record_class

    @classmethod
    def filters(cls):
        """Filters for sources."""
        return {
            source["name"]: exists_filter(f'{source["name"]}_pid')
            for source in cls.sources.values()
        }

    @classmethod
    def aggregations(cls):
        """Aggregations for sources."""
        return {
            source["name"]: dict(
                filter=dict(exists=dict(field=f'{source["name"]}_pid'))
            )
            for source in cls.sources.values()
        }

    def create_mef_and_agents(self, dbcommit=False, reindex=False,
                              online=None, verbose=False,
                              online_verbose=False):
        """Create MEF and agents records.

        :param dbcommit: Commit changes to DB.
        :param reindex: Reindex record.
        :param online: Search online for new VIAF record.
        :param verbose: Verbose.
        :param online_verbose: Online verbose
        :returns: Actions.
        """
        def update_online(agent_class, pid, online):
            """Update agents online.

            :param agent_class: Agent class to use.
            :param pid: Agent pid to use..
            :param online: Try to get following agent types online.
            :return: Agent record and performed action.
            """
            action = 'NOTONLINE'
            agent_record = None
            if agent_class.provider.pid_type in online:
                data, msg = agent_class.get_online_record(id=pid)
                if online_verbose:
                    click.echo(msg)
                if data and not data.get('NO TRANSFORMATION'):
                    agent_record, action = agent_class.create_or_update(
                        data=data, dbcommit=dbcommit, reindex=reindex)
                    action = action.name
            else:
                agent_record = agent_class.get_record_by_pid(pid)
            return agent_record, action

        def set_actions(actions, pid, source_name, action,
                        mef_pid=None, mef_action=None):
            """Set actions.

            :param actions: Actions dictionary to change
            :param pid: Pid to add.
            :param source_name: Source name to add
            :param action: Action to add.
            :param mef_pid: MEF pid to add (optional).
            :param mef_action: MEF action to add (optional).
            :return: actions
            """
            actions.setdefault(pid, {
                'source': source_name,
                'action': action
            })
            if mef_pid:
                mef_actions = actions.get(pid, {}).get('MEF', {})
                mef_actions[mef_pid] = mef_action
                actions[pid]['MEF'] = mef_actions
            return actions

        actions = {}
        online = online or []
        # Get all VIAF agents pids
        agent_viaf_pids = {
            data['record_class'].name: {
                'pid': data['pid'],
                'record_class': data['record_class']
            }
            for data in self.get_agents_pids()
        }
        agent_mef_pids = {}
        mef_record = None

        try:
            if mef_records := AgentMefRecord.get_mef(
                agent_pid=self.pid, agent_name=self.name
            ):
                # Get all MEF agents pids
                mef_record = mef_records[0]
                agent_mef_pids = {
                    data['record_class'].name: {
                        'pid': data['pid'],
                        'record_class': data['record_class']
                    }
                    for data in mef_record.get_agents_pids()
                }
                # clean VIAF MEF pids not changed
                for source_name in self.sources_used:
                    agent_viaf_pid = agent_viaf_pids.get(
                        source_name, {}).get('pid')
                    agent_mef_pid = agent_mef_pids.get(
                        source_name, {}).get('pid')
                    if agent_viaf_pid and agent_viaf_pid == agent_mef_pid:
                        agent_class = agent_viaf_pids[
                            source_name]['record_class']
                        _, action = update_online(
                            agent_class=agent_class,
                            pid=agent_viaf_pid,
                            online=online
                        )
                        actions = set_actions(
                            actions=actions,
                            pid=agent_viaf_pid,
                            source_name=source_name,
                            action=action,
                            mef_pid=mef_record.pid,
                            mef_action=Action.UPTODATE.name
                        )
                        agent_viaf_pids.pop(source_name, None)
                        agent_mef_pids.pop(source_name, None)
            # Update deleted
            deleted_records = []
            for source_name, info in agent_mef_pids.items():
                deleted_records.append(
                    info['record_class'].get_record_by_pid(info['pid'])
                )
                if mef_record:
                    mef_record.pop(source_name, None)
                    actions = set_actions(
                        actions=actions,
                        pid=info['pid'],
                        source_name=source_name,
                        action=Action.DISCARD.name,
                        mef_pid=mef_record.pid,
                        mef_action=Action.DELETE.name
                    )
            if agent_mef_pids:
                mef_record.update(
                    data=mef_record,
                    dbcommit=dbcommit,
                    reindex=reindex
                )
                if reindex:
                    mef_record.flush_indexes()
            # Update changed
            old_mef_records = {}
            for source_name, info in agent_viaf_pids.items():
                # Get old MEF records.
                for old_mef_record in AgentMefRecord.get_mef(
                    agent_pid=info['pid'], agent_name=source_name
                ):
                    if old_mef_record.get('viaf_pid') != self.pid:
                        old_mef_records.setdefault(
                            old_mef_record.pid, []).append(source_name)
                agent_record = None
                agent_class = info['record_class']
                pid = info['pid']
                agent_record, action = update_online(
                    agent_class=agent_class,
                    pid=pid,
                    online=online
                )
                if agent_record:
                    mef_record, mef_action = agent_record.create_or_update_mef(
                        dbcommit=dbcommit, reindex=reindex)
                    actions = set_actions(
                        actions=actions,
                        pid=pid,
                        source_name=source_name,
                        action=action,
                        mef_pid=mef_record.pid,
                        mef_action=mef_action.name
                    )
                else:
                    actions = set_actions(
                        actions=actions,
                        pid=pid,
                        source_name=source_name,
                        action='NOT FOUND',
                    )
            for deleted_record in deleted_records:
                mef_record, mef_action = deleted_record.create_or_update_mef(
                    dbcommit=dbcommit, reindex=reindex)
                actions = set_actions(
                    actions=actions,
                    pid=deleted_record.pid,
                    source_name=deleted_record.name,
                    action=Action.DELETE.name,
                    mef_pid=mef_record.pid,
                    mef_action=mef_action.name
                )
            for old_mef_record_pid, sources in old_mef_records.items():
                old_mef_record = AgentMefRecord.get_record_by_pid(
                    old_mef_record_pid)
                for source in sources:
                    old_mef_record.pop(source, None)
                old_mef_record.update(
                    data=old_mef_record,
                    dbcommit=dbcommit,
                    reindex=reindex
                )
            if verbose:
                msgs = [
                    f'{value["source"]}: {key} '
                    f'{value["action"]} MEF: {value.get("MEF")}'
                    for key, value in actions.items()
                ]
                click.echo(
                    '  Create MEF from VIAF pid: '
                    f'{self.pid:<25} '
                    f'| {"; ".join(msgs)}'
                )
            if reindex:
                AgentMefRecord.flush_indexes()
        except Exception as err:
            current_app.logger.error(
                f'{self.pid:<25} '
                f'| {err}',
                exc_info=True,
                stack_info=True
            )
            raise
        return actions

    def reindex(self, forceindex=False):
        """Reindex record."""
        result = super().reindex(forceindex=forceindex)
        self.flush_indexes()
        return result

    @classmethod
    def get_online_record(cls, viaf_source_code, pid, format=None):
        """Get VIAF record.

        Get's the VIAF record from:
        http://www.viaf.org/viaf/sourceID/{source_code}|{pid}

        :param viaf_source_code: agent source code
        :param pid: pid for agent source code
        :param format: raw = get the not transformed VIAF record
                       link = get the VIAF link record
        :returns: VIAF record as json
        """
        viaf_format = '/viaf.json'
        if format == 'link':
            viaf_format = '/justlinks.json'
            format = 'raw'
        viaf_url = current_app.config.get('RERO_MEF_VIAF_BASE_URL')
        url = f'{viaf_url}/viaf'
        if viaf_source_code.upper() == 'VIAF':
            url = f'{url}/{pid}{viaf_format}'
        else:
            url = f'{url}/sourceID/{viaf_source_code}|{pid}{viaf_format}'
        response = requests_retry_session().get(url)
        result = {}
        if response.status_code == requests.codes.ok:
            msg = f'VIAF get: {pid:<15} {url} | OK'
            if format == 'raw':
                return response.json(), msg
            data_json = response.json()
            result['pid'] = data_json.get('viafID')
            if sources := data_json.get('sources', {}).get('source'):
                if isinstance(sources, dict):
                    sources = [sources]
                for source in sources:
                    # get pid
                    text = source.get('#text', '|')
                    text = text.split('|')
                    if bib_source := cls.sources.get(text[0], {}).get('name'):
                        result[f'{bib_source}_pid'] = text[1]
                        # get URL
                        if nsid := source.get('@nsid'):
                            if nsid.startswith('http'):
                                result[bib_source] = nsid
                # get Wikipedia URLs
                x_links = data_json.get('xLinks', {}).get('xLink', [])
                if not isinstance(x_links, list):
                    x_links = [x_links]
                for x_link in x_links:
                    if isinstance(x_link, dict) and result.get('wiki_pid'):
                        text = x_link.get('#text')
                        if text and 'wikipedia' in text:
                            result.setdefault(
                                'wiki', []
                            ).append(text.replace('"', '%22'))
                if wiki_urls := result.get('wiki'):
                    result['wiki'] = sorted(wiki_urls)

        # make sure we got a VIAF with the same pid for source
        if viaf_source_code.upper() == 'VIAF':
            if result.get('pid') == pid:
                return result, msg
        elif result.get(
            f'{cls.sources.get(viaf_source_code, {}).get("name")}_pid'
        ) == pid:
            return result, msg
        return {}, f'VIAF get: {pid:<15} {url} | NO RECORD'

    def update_online(self, dbcommit=False, reindex=False):
        """Update online.

        :param dbcommit: Commit changes to DB.
        :param reindex: Reindex record.
        :returns: record and actions message.
        """
        from rero_mef.api import Action
        online_data, _ = self.get_online_record(
            viaf_source_code='VIAF',
            pid=self.pid
            )
        if online_data:
            online_data['$schema'] = self['$schema']
            online_data = add_md5(online_data)
            if online_data['md5'] == self.get('md5'):
                return self, Action.UPTODATE
            else:
                return self.replace(
                    data=online_data,
                    dbcommit=dbcommit,
                    reindex=reindex
                ), Action.UPDATE
        return None, Action.DISCARD

    @classmethod
    def get_viaf(cls, agent):
        """Get VIAF record by agent.

        :param agent: Agency do get corresponding VIAF record.
        """
        if isinstance(agent, AgentMefRecord):
            return [cls.get_record_by_pid(agent.get('viaf_pid'))]
        if isinstance(agent, AgentViafRecord):
            return [cls.get_record_by_pid(agent.get('pid'))]
        pid = agent.get('pid')
        viaf_pid_name = agent.viaf_pid_name
        query = AgentViafSearch() \
            .filter({'term': {viaf_pid_name: pid}}) \
            .params(preserve_order=True) \
            .sort({'_updated': {'order': 'desc'}})
        viaf_records = [
            cls.get_record_by_pid(hit.pid) for hit in
            query.source('pid').scan()
        ]
        if len(viaf_records) > 1:
            current_app.logger.error(
                f'MULTIPLE VIAF FOUND FOR: {agent.name} {agent.pid}'
            )
        return viaf_records

    @classmethod
    def create_or_update(cls, data, id_=None, delete_pid=True, dbcommit=False,
                         reindex=False, test_md5=False):
        """Create or update VIAF record."""
        record, action = super().create_or_update(
            data=data,
            id_=id_,
            delete_pid=delete_pid,
            dbcommit=dbcommit,
            reindex=reindex,
            test_md5=test_md5
        )
        if record:
            record.create_mef_and_agents(dbcommit=dbcommit, reindex=reindex)
        return record, action

    def delete(self, force=True, dbcommit=False, delindex=False):
        """Delete record and persistent identifier.

        :param dbcommit: Commit changes to DB.
        :param reindex: Reindex record.
        :returns: MEF actions message.
        """
        agents_records = self.get_agents_records()
        mef_records = AgentMefRecord.get_mef(
            agent_pid=self.pid, agent_name=self.name)
        # delete VIAF record
        result = super().delete(
            force=True, dbcommit=dbcommit, delindex=delindex)
        mef_actions = []
        for mef_record in mef_records:
            mef_actions.append(f'MEF: {mef_record.pid}')
            if len(agents_records):
                mef_actions.append(
                    f'{agents_records[0].name}: {agents_records[0].pid} '
                    f'MEF: {mef_record.pid} {Action.UPDATE.value}'
                )
            for agent_record in agents_records[1:]:
                mef_record.delete_ref(agent_record)
            mef_record.pop('viaf_pid', None)
            mef_record.update(data=mef_record, dbcommit=True, reindex=True)
        AgentMefRecord.flush_indexes()
        # recreate MEF records for agents
        for agent_record in agents_records[1:]:
            mef_record, mef_action = agent_record.create_or_update_mef(
                dbcommit=True, reindex=True)
            mef_actions.append(
                f'{agent_record.name}: {agent_record.pid} '
                f'MEF: {mef_record.pid} {mef_action.value}'
            )
        AgentMefRecord.flush_indexes()
        return result, Action.DELETE, mef_actions

    def get_agents_pids(self):
        """Get agent pids."""
        agents = []
        for source, record_class in self.sources_used.items():
            if source_pid := self.get(f'{source}_pid'):
                agents.append({
                    'record_class': record_class,
                    'pid': source_pid
                })
        return agents

    def get_agents_records(self, verbose=False):
        """Get agent records."""
        agent_records = []
        for agent in self.get_agents_pids():
            record_class = agent['record_class']
            if agent_record := record_class.get_record_by_pid(agent['pid']):
                agent_records.append(agent_record)
            elif verbose:
                current_app.logger.warning(
                    f'Record not found VIAF: {self.pid} '
                    f'{agent["record_class"].name}: {agent["pid"]}'
                )
        return agent_records

    @classmethod
    def get_missing_agent_pids(cls, agent, verbose=False):
        """Get all missing pids defined in VIAF.

        :param agent: Agent to search for missing pids.
        :param verbose: Verbose.
        :returns: Agent pids without VIAF, VIAF pids without agent
        """
        if record_class := get_entity_class(agent):
            if verbose:
                click.echo(f'Get pids from {agent} ...')
            progress = progressbar(
                items=record_class.get_all_pids(),
                length=record_class.count(),
                verbose=verbose
            )
            pids_db = set(progress)

            agent_pid_name = f'{record_class.name}_pid'
            if verbose:
                click.echo(f'Get pids from VIAF with {agent_pid_name} ...')
            query = AgentViafSearch() \
                .filter('bool', should=[Q('exists', field=agent_pid_name)])
            progress = progressbar(
                items=query.source(['pid', agent_pid_name]).scan(),
                length=query.count(),
                verbose=verbose
            )
            pids_viaf = []
            for hit in progress:
                viaf_pid = hit.pid
                agent_pid = hit.to_dict().get(agent_pid_name)
                if agent_pid in pids_db:
                    pids_db.discard(agent_pid)
                else:
                    pids_viaf.append(viaf_pid)
            return list(pids_db), pids_viaf
        click.secho(f'ERROR Record class not found for: {agent}', fg='red')
        return [], []

    @classmethod
    def get_pids_with_multiple_viaf(cls, verbose=False):
        """Get agent pids with multiple MEF records.

        :param verbose: Verbose.
        :returns: pids.
        """
        multiple_pids = {
            f'{source}_pid': {} for source
            in AgentViafRecord(data={}).sources_used
        }
        cleaned_pids = deepcopy(multiple_pids)
        progress = progressbar(
            items=AgentViafSearch()
            .params(preserve_order=True)
            .sort({'pid': {'order': 'asc'}})
            .scan(),
            length=AgentViafSearch().count(),
            verbose=verbose
        )
        for hit in progress:
            viaf_pid = hit.pid
            data = hit.to_dict()
            for source in multiple_pids:
                if pid := data.get(source):
                    multiple_pids[source].setdefault(pid, [])
                    multiple_pids[source][pid].append(viaf_pid)
        for source, pids in multiple_pids.items():
            for pid, viaf_pids in pids.items():
                if len(viaf_pids) > 1:
                    cleaned_pids[source][pid] = viaf_pids
        return cleaned_pids


class AgentViafIndexer(ReroIndexer):
    """Agent VIAF indexer."""

    record_cls = AgentViafRecord

    def bulk_index(self, record_id_iterator):
        """Bulk index records.

        :param record_id_iterator: Iterator yielding record UUIDs.
        """
        super().bulk_index(
            record_id_iterator,
            index=AgentViafSearch.Meta.index,
            doc_type='viaf'
        )
