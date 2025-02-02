# -*- coding: utf-8 -*-
#
# RERO MEF
# Copyright (C) 2021 RERO
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

"""Utilities."""

import datetime
import json
import os
from uuid import uuid4

import click
from flask import current_app

from ..utils import get_entity_classes, metadata_csv_line, \
    number_records_in_file, pidstore_csv_line, progressbar, write_link_json


def write_mef_files(pid, data, pidstore, metadata, ids):
    """Write MEF metadata, pidstore and ids file.
    
    :param pid: Pid for data.
    :param data: Corresponding data to write.
    :param pidstore: Pidstore file.
    :param metadata: Metadata file.
    :param ids: Ids file
    :returns: Next pid.
    """
    mef_uuid = str(uuid4())
    date = str(datetime.utcnow())
    pidstore.write(
        pidstore_csv_line('mef', str(pid), mef_uuid, date))
    metadata.write(metadata_csv_line(data, mef_uuid, date))
    ids.write(str(pid) + os.linesep)
    return pid + 1


def init_agent_pids(input_directory, verbose):
    """Init agent data.
    
    :param input_directory: Input directory to look for agent pidstore files.
    :param verbose: Verbose.
    :returns: Dictionary with agent name and associated pids and dictonary with 
              VIAF agent pid names.
    """
    pids = {}
    viaf_agent_pid_names = {}
    agent_classes = get_entity_classes()
    for agent, agent_classe in agent_classes.items():
        name = agent_classe.name
        viaf_pid_name = agent_classe.viaf_pid_name
        if viaf_pid_name:
            viaf_agent_pid_names[viaf_pid_name] = name
            file_name = os.path.join(input_directory, f'{agent}_pidstore.csv')
            if os.path.exists(file_name):
                if verbose:
                    click.echo(f'  Read pids from: {file_name}')
                length = number_records_in_file(file_name, 'csv')
                pids[name] = {}
                progress = progressbar(
                    items=open(file_name, 'r'),
                    length=length,
                    verbose=verbose
                )
                for line in progress:
                    pid = line.split('\t')[3]
                    pids[name][pid] = 1
    return pids, viaf_agent_pid_names


def create_mef_files(
    viaf_pidstore_file,
    input_directory,
    mef_pidstore_file_name,
    mef_metadata_file_name,
    mef_ids_file_name,
    verbose=False
):
    """Create MEF CSV file to load.

    :param viaf_pidstore_file_name: VIAF pidstore input file name.
    :param input_directory: Input directory with agent pidstore files.,
    :param mef_pidstore_file_name: MEF pidstore output file name.
    :param mef_metadata_file_name: MEF metadata output file name.
    :param mef_ids_file_name: MEF ids output file name.
    :param verbose: Verbose.
    :returns: count of processed MEF records.
    """    
    if verbose:
        click.echo('Start ***')
    pids, viaf_agent_pid_names = init_agent_pids(input_directory, verbose)

    mef_pid = 1
    corresponding_data = {}
    with open(mef_pidstore_file_name, 'w', encoding='utf-8') as pidstore, \
            open(mef_metadata_file_name, 'w', encoding='utf-8') as metadata, \
            open(mef_ids_file_name, 'w', encoding='utf-8') as ids:
        schemas = current_app.config.get('RECORDS_JSON_SCHEMA')
        base_url = current_app.config.get('RERO_MEF_APP_BASE_URL')
        schema = (f'{base_url}'
                    f'{current_app.config.get("JSONSCHEMAS_ENDPOINT")}'
                    f'{schemas["mef"]}')
        # Create MEF with VIAF
        if verbose:
            click.echo(
                f'  Create MEF with VIAF pid: {viaf_pidstore_file}'
            )
        progress = progressbar(
            items=open(str(viaf_pidstore_file), 'r', encoding='utf-8'),
            length=number_records_in_file(viaf_pidstore_file, 'csv'),
            verbose=verbose
        )
        for line in progress:
            viaf_data = json.loads(line.split('\t')[3])
            viaf_pid = viaf_data['pid']
            corresponding_data = {
                'pid': str(mef_pid),
                '$schema': schema
            }
            for viaf_pid_name, name in viaf_agent_pid_names.items():
                agent_pid = viaf_data.get(viaf_pid_name)
                if agent_pid and pids.get(name, {}).get(agent_pid):
                    corresponding_data['viaf_pid'] = viaf_pid
                    pids[name].pop(agent_pid)
                    corresponding_data[name] = {
                        '$ref': f'{base_url}/api/{name}/{agent_pid}'}
            if corresponding_data.get('viaf_pid'):
                # Write MEF with VIAF to file
                mef_pid = write_mef_files(
                    pid=mef_pid,
                    data=corresponding_data,
                    pidstore=pidstore,
                    metadata=metadata,
                    ids=ids
                )
        # Create MEF without VIAF
        length = sum([len(p) for p in pids.values()])
        if verbose:
            click.echo(f'  Create MEF without VIAF pid: {length}')
        progress = progressbar(items=pids, length=length, verbose=verbose)
        for agent in progress:
            for pid in pids[agent]:
                url = f'{base_url}/api/{agent}/{pid}'
                corresponding_data = {
                    'pid': str(mef_pid),
                    '$schema': schema,
                    agent: {'$ref': url}
                }
                mef_pid = write_mef_files(
                    pid=mef_pid,
                    data=corresponding_data,
                    pidstore=pidstore,
                    metadata=metadata,
                    ids=ids
                )
    mef_pid -= 1
    if verbose:
        click.echo(f'  MEF records created: {mef_pid}')
    return mef_pid


def create_viaf_files(
    viaf_input_file,
    viaf_pidstore_file_name,
    viaf_metadata_file_name,
    verbose=False
):
    """Create VIAF CSV file to load.
    
    :param viaf_input_file: VIAF input source file name.
    :param viaf_pidstore_file_name: VIAF pidstore output file name.
    :param viaf_metadata_file_name: VIAF metadata output file name.
    :param verbose: Verbose.
    :returns: count of processed VIAF records.
    """
    if verbose:
        click.echo('Start ***')

    agent_pid = 0
    corresponding_data = {}
    count = 0
    with open(
        viaf_pidstore_file_name, 'w', encoding='utf-8'
    ) as viaf_pidstore:
        with open(
            viaf_metadata_file_name, 'w', encoding='utf-8'
        ) as viaf_metadata:
            with open(
                str(viaf_input_file), 'r', encoding='utf-8'
            ) as viaf_in_file:
                # get first viaf_pid
                row = viaf_in_file.readline()
                fields = row.rstrip().split('\t')
                assert len(fields) == 2
                previous_viaf_pid = fields[0].split('/')[-1]
                viaf_in_file.seek(0)
                for row in viaf_in_file:
                    fields = row.rstrip().split('\t')
                    assert len(fields) == 2
                    viaf_pid = fields[0].split('/')[-1]
                    if viaf_pid != previous_viaf_pid:
                        agent_pid += 1
                        written = write_link_json(
                            agent='viaf',
                            pidstore_file=viaf_pidstore,
                            metadata_file=viaf_metadata,
                            viaf_pid=previous_viaf_pid,
                            corresponding_data=corresponding_data,
                            agent_pid=str(agent_pid),
                            verbose=verbose
                        )
                        if written:
                            count += 1
                        corresponding_data = {}
                        previous_viaf_pid = viaf_pid
                    corresponding = fields[1].split('|')
                    if len(corresponding) == 2:
                        corresponding_data[corresponding[0]] = corresponding[1]
                # save the last record
                agent_pid += 1
                written = write_link_json(
                    agent='viaf',
                    pidstore_file=viaf_pidstore,
                    metadata_file=viaf_metadata,
                    viaf_pid=previous_viaf_pid,
                    corresponding_data=corresponding_data,
                    agent_pid=str(agent_pid),
                    verbose=verbose
                )
                if written:
                    count += 1
    if verbose:
        click.echo(f'  VIAF records created: {count}')
    return count


def get_agents_endpoints():
    """Get all agents from config."""
    agents_endpoints = {}
    agents = current_app.config.get('AGENTS', [])
    endpoints = current_app.config.get('RECORDS_REST_ENDPOINTS', {})
    for endpoint, data in endpoints.items():
        if endpoint in agents:
            agents_endpoints[endpoint] = data
    return agents_endpoints
